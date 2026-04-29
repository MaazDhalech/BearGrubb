from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


HALAL_NOTE = "Note: classifications are ingredient-based and intended as a guide, not a religious ruling."

HALL_ALIASES = {
    "crossroads": "Crossroads",
    "cafe 3": "Cafe 3",
    "cafe3": "Cafe 3",
    "clark kerr": "Clark Kerr",
    "foothill": "Foothill",
}

HALL_DISPLAY_ORDER = ["Cafe 3", "Crossroads", "Foothill", "Clark Kerr"]

CROSSROADS_HOURS = "Crossroads runs Brunch from 10:30am to 3:00pm and Dinner from 4:30pm to 9:00pm."

MEAT_TERMS = {
    "beef",
    "chicken",
    "turkey",
    "lamb",
    "kofta",
    "fajita",
    "steak",
    "meat",
    "sausage",
}

DEFAULT_EXCLUDED_CATEGORIES = {
    "salad",
    "dressing",
    "dessert",
    "bread",
    "bakery",
    "soup",
    "beverage",
    "condiment",
}

DEFAULT_EXCLUDED_ITEM_PHRASES = {
    "assorted dinner rolls",
    "chive",
    "chives",
    "curly parsley",
    "italian parsley",
    "cherry pepper",
    "nutritional yeast",
    "pumpkin seeds",
    "shredded vegan mozzarella cheese",
    "sour cream",
}

STOPWORDS = {
    "a",
    "all",
    "and",
    "any",
    "are",
    "at",
    "cal",
    "calories",
    "can",
    "crossroads",
    "dinner",
    "for",
    "from",
    "hall",
    "halal",
    "had",
    "have",
    "how",
    "i",
    "in",
    "is",
    "me",
    "many",
    "menu",
    "much",
    "of",
    "on",
    "options",
    "oz",
    "serving",
    "the",
    "there",
    "tonight",
    "today",
    "vegan",
    "vegetarian",
    "what",
    "what's",
}

OUT_OF_SCOPE_PATTERNS = [
    (
        re.compile(r"\b(is|are)\b.+\bgood\b|\btaste\b", re.I),
        "I can tell you the ingredients and nutrition for that item, but I can't speak to taste — that's subjective. Want the nutrition info?",
        "taste",
    ),
    (
        re.compile(r"\b(best dining hall|dining hall is best)\b", re.I),
        "That's a matter of personal preference. I can help you find the best options for your dietary needs at any of the 4 dining halls tonight.",
        "preference",
    ),
    (
        re.compile(r"\b(recipe|cook|make)\b", re.I),
        "I can only help with what's available at Berkeley dining halls today. Want me to show you the halal chicken options tonight?",
        "recipe",
    ),
    (
        re.compile(r"\b(how do i get to|directions?|route)\b", re.I),
        "I can only help with dining information like menus, nutrition, and dietary restrictions. For directions, Google Maps would be your best bet.",
        "directions",
    ),
]


@dataclass(frozen=True)
class RuleBasedResponse:
    content: str
    disclaimer_used: bool = False
    guardrail: str = "menu_answer"


@dataclass(frozen=True)
class MenuItem:
    name: str
    hall: str
    meal: str
    category: str
    halal_status: str
    halal_reason: str
    is_vegan: bool
    is_vegetarian: bool
    contains_shellfish: bool
    shellfish_note: str
    ingredients: str
    allergens_present: tuple[str, ...]
    calories: float | None
    serving_size: float | None
    serving_unit: str
    calories_per_oz: float | None
    protein: float | None
    fat: float | None
    carbs: float | None
    fiber: float | None
    sodium: float | None
    cholesterol: float | None


def build_pre_context_response(content: str) -> RuleBasedResponse | None:
    q = content.lower()
    if re.fullmatch(r"\s*(hi|hello|hey|yo|sup|salam|assalamu alaikum)\s*[!.?]*\s*", q):
        return RuleBasedResponse(
            "Hi — I can help with Berkeley dining menus, halal status, dietary filters, allergens, and nutrition for today's dining hall options.",
            guardrail="greeting",
        )
    if re.search(r"\bnext\s+week\b|\bfuture\b", q):
        return RuleBasedResponse(
            "I only have access to today's menu data. I'm not able to show future menus.",
            guardrail="unsupported_future_menu",
        )
    if re.search(r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\byesterday\b|\bhistorical\b", q):
        return RuleBasedResponse(
            "I only have access to today's menu. Historical menus aren't available yet.",
            guardrail="unsupported_historical_menu",
        )
    if asks_for_hours(content):
        hall = parse_hall(content)
        if hall == "Crossroads" or hall is None:
            return RuleBasedResponse(CROSSROADS_HOURS, guardrail="hours")
    for pattern, response, guardrail in OUT_OF_SCOPE_PATTERNS:
        if pattern.search(content):
            return RuleBasedResponse(response, guardrail=guardrail)
    return None


def build_menu_response(
    content: str,
    docs: list[Any],
    menu_date: str,
    include_halal_disclaimer: bool = False,
) -> RuleBasedResponse | None:
    items = [item for item in (item_from_doc(doc) for doc in docs) if item.name]
    if not items:
        return None

    builders = [
        build_crossroads_lunch_response,
        build_pork_response,
        build_allergy_response,
        build_item_availability_response,
        build_halal_status_response,
        build_optimization_response,
        build_portion_calorie_response,
        build_nutrition_response,
        build_dietary_list_response,
    ]
    for builder in builders:
        response = builder(content, items, menu_date, include_halal_disclaimer)
        if response is not None:
            return response
    return None


def build_crossroads_lunch_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    if parse_hall(content) == "Crossroads" and parse_meal(content) == "Lunch":
        return RuleBasedResponse(
            f"{CROSSROADS_HOURS} Would you like to see halal options for brunch or dinner?",
            guardrail="unsupported_meal_period",
        )
    return None


def build_item_availability_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    q = content.lower().strip()
    if not re.match(r"^(is|are)\s+there\b", q):
        return None
    if re.search(r"\b(anything|options?|meals?|can i eat)\b", q):
        return None
    item_terms = item_query_terms(content)
    if not item_terms:
        return None
    hall = parse_hall(content)
    meal = parse_meal(content) or default_meal(content)
    scoped = filter_scope(items, hall=hall, meal=meal)
    match = best_item_match(content, scoped, strict=True)
    requested_name = clean_requested_item_name(content)
    location = hall or default_hall(scoped or items)
    if match is None:
        return RuleBasedResponse(
            f"I don't see {requested_name} on today's menu at {location}.",
            guardrail="item_availability",
        )
    meal_text = f" for {match.meal.lower()}" if match.meal else ""
    return RuleBasedResponse(
        f"Yes — {match.name} is on today's menu at {match.hall}{meal_text}.",
        guardrail="item_availability",
    )


def build_dietary_list_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    filters = requested_dietary_filters(content)
    if not filters or is_halal_status_question(content) or is_nutrition_question(content):
        return None
    if not looks_like_option_request(content):
        return None

    hall = parse_hall(content)
    meal = parse_meal(content) or default_meal(content)
    if hall and hall not in present_halls(items):
        return RuleBasedResponse(missing_hall_response(hall, items, filters), guardrail="missing_hall")

    scope_items = filter_scope(items, hall=hall, meal=meal)
    scope_items = [item for item in scope_items if matches_dietary_filters(item, filters)]
    scope_items = filter_default_menu_items(scope_items, content)
    scope_items = unique_items(scope_items)

    if not scope_items:
        label = dietary_label(filters)
        location = hall or default_hall(items)
        meal_text = f" for {meal.lower()}" if meal else ""
        return RuleBasedResponse(
            f"I couldn't find any {label} options at {location}{meal_text} today.",
            guardrail="no_matching_dietary_items",
        )

    if "halal" in filters:
        if "vegan" in filters:
            content_text = format_halal_vegan_options(content, scope_items, hall, meal)
            return RuleBasedResponse(
                content_text,
                disclaimer_used=False,
                guardrail="halal_vegan_options",
            )
        content_text = format_halal_options(content, scope_items, hall, meal, include_halal_disclaimer)
        return RuleBasedResponse(
            content_text,
            disclaimer_used=include_halal_disclaimer,
            guardrail="halal_options",
        )

    label = "Vegan" if filters == ["vegan"] else "Vegetarian"
    location = hall or default_hall(items)
    meal_text = f" for {meal.lower()}" if meal else ""
    lines = [f"{label} options at {location}{meal_text}:", ""]
    lines.extend(format_basic_item_line(item) for item in sort_by_name(scope_items))
    return RuleBasedResponse("\n".join(lines), guardrail=f"{filters[0]}_options")


def build_optimization_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    q = content.lower()
    filters = requested_dietary_filters(content)
    if not filters:
        return None

    hall = parse_hall(content)
    location = hall or default_hall(items)
    meal = parse_meal(content) or default_meal(content)
    scope_items = filter_scope(items, hall=hall, meal=meal)
    scope_items = [item for item in scope_items if matches_dietary_filters(item, filters)]
    scope_items = filter_default_menu_items(unique_items(scope_items), content)

    if "high protein" in q and "low carb" in q:
        candidates = [item for item in scope_items if item.protein is not None and item.carbs is not None]
        if not candidates:
            return None
        best = sorted(candidates, key=lambda item: (-(item.protein or 0), item.carbs or 0))[0]
        return RuleBasedResponse(
            f"Best {dietary_label(filters)} high protein low carb option at {location} tonight is "
            f"{best.name} — {format_grams(best.protein)}g protein, {format_grams(best.carbs)}g carbs "
            f"per {format_serving(best)}.",
            guardrail="high_protein_low_carb",
        )

    if "high protein" in q or "highest protein" in q:
        candidates = [item for item in scope_items if item.protein is not None]
        if not candidates:
            return None
        candidates = sorted(candidates, key=lambda item: item.protein or 0, reverse=True)
        if "highest" in q and "option" in q and "options" not in q:
            best = candidates[0]
            return RuleBasedResponse(
                f"The highest protein {dietary_label(filters)} option at {location} tonight is "
                f"{best.name} with {format_grams(best.protein)}g of protein per {format_serving(best)}.",
                guardrail="highest_protein",
            )
        lines = [f"Highest protein {dietary_label(filters)} options at {location} tonight:", ""]
        lines.extend(
            f"✅ {item.name} — {format_grams(item.protein)}g protein per {format_serving(item)}"
            for item in candidates[:8]
        )
        return RuleBasedResponse("\n".join(lines), guardrail="high_protein_options")

    if "lowest calorie" in q and "vegan" in filters:
        candidates = [item for item in scope_items if item.calories is not None]
        if not candidates:
            return None
        lowest = sorted(candidates, key=lambda item: item.calories or 0)[0]
        protein_pick = next(
            (
                item
                for item in sorted(candidates, key=lambda item: item.protein or 0, reverse=True)
                if item.name != lowest.name and item.protein is not None
            ),
            None,
        )
        response = (
            f"The lowest calorie substantial vegan option at {location} for {meal.lower() if meal else 'today'} "
            f"is {lowest.name} at {format_calories(lowest.calories)} cal per {format_serving(lowest)}."
        )
        if protein_pick:
            response += (
                f" If you want more protein, {protein_pick.name} is "
                f"{format_calories(protein_pick.calories)} cal per {format_serving(protein_pick)} "
                f"with {format_grams(protein_pick.protein)}g protein."
            )
        return RuleBasedResponse(response, guardrail="lowest_calorie_vegan")

    calorie_limit = extract_calorie_limit(content)
    if calorie_limit is not None:
        candidates = [
            item for item in scope_items if item.calories is not None and item.calories <= calorie_limit
        ]
        if not candidates:
            return None
        lines = [f"{dietary_label(filters).capitalize()} options at {location} under {calorie_limit} calories:", ""]
        lines.extend(f"✅ {item.name} — {format_calories(item.calories)} cal per {format_serving(item)}" for item in candidates)
        return RuleBasedResponse("\n".join(lines), guardrail="calorie_limit")

    if "calorie dense" in q or "calorie-dense" in q:
        candidates = [item for item in scope_items if item.calories_per_oz is not None]
        if not candidates:
            return None
        best = sorted(candidates, key=lambda item: item.calories_per_oz or 0, reverse=True)[0]
        return RuleBasedResponse(
            f"The most calorie dense {dietary_label(filters)} option at {location} tonight is "
            f"{best.name} at {format_calories(best.calories)} calories per {format_serving(best)} "
            f"({format_grams(best.calories_per_oz)} cal/oz).",
            guardrail="calorie_density",
        )

    return None


def build_halal_status_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    if not is_halal_status_question(content):
        return None
    item = best_item_match(content, items)
    if item is None:
        return None
    status = item.halal_status
    if status == "HALAL":
        response = f"✅ HALAL — {halal_positive_reason(item)}"
    elif status == "NOT_HALAL":
        response = f"❌ NOT HALAL — {halal_negative_reason(item)}"
    else:
        reason = normalize_reason(item.halal_reason or "classification is uncertain")
        response = f"⚠️ UNCERTAIN — {reason}. Use your own judgment."

    notes = halal_notes(item)
    if notes:
        response += f" Note: {' '.join(notes)}"
    return RuleBasedResponse(response, guardrail="halal_status")


def build_nutrition_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    if not is_nutrition_question(content) or is_portion_question(content):
        return None
    item = best_item_match(content, items)
    if item is None:
        return None
    q = content.lower()
    if "macro" in q:
        return RuleBasedResponse(format_macros(item), guardrail="macros")
    if "protein" in q:
        return RuleBasedResponse(
            f"{item.name} has {format_grams(item.protein)}g of protein per serving ({format_serving(item, include_word=False)}).",
            guardrail="protein",
        )
    if "sodium" in q:
        suffix = " — notably high." if item.sodium is not None and item.sodium >= 1000 else "."
        return RuleBasedResponse(
            f"{item.name} has {format_mg(item.sodium)}mg of sodium per serving ({format_serving(item, include_word=False)}){suffix}",
            guardrail="sodium",
        )
    if "fiber" in q:
        return RuleBasedResponse(
            f"{item.name} has {format_grams(item.fiber)}g of fiber per serving ({format_serving(item, include_word=False)}).",
            guardrail="fiber",
        )
    if "cholesterol" in q:
        return RuleBasedResponse(
            f"{item.name} has {format_mg(item.cholesterol)}mg of cholesterol per serving ({format_serving(item, include_word=False)}).",
            guardrail="cholesterol",
        )
    if "carbon footprint" in q:
        return None
    if "calorie" in q:
        extra = ""
        if item.protein is not None and ("vegan" in item.name.lower() or item.is_vegan):
            extra = f" with {format_grams(item.protein)}g protein"
        return RuleBasedResponse(
            f"{item.name} is {format_calories(item.calories)} calories per serving ({format_serving(item, include_word=False)}){extra}.",
            guardrail="calories",
        )
    return None


def build_portion_calorie_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    if not is_portion_question(content) or "calorie" not in content.lower():
        return None
    item = best_item_match(content, items)
    if item is None or item.calories is None or item.serving_size is None:
        return None
    oz = extract_oz_amount(content)
    descriptor = None
    if oz is None:
        fraction = extract_serving_fraction(content)
        if fraction is None:
            return None
        oz = item.serving_size * fraction
        descriptor = fraction_descriptor(fraction)
    if item.calories_per_oz is not None:
        total = item.calories_per_oz * oz
    else:
        total = item.calories * (oz / item.serving_size)
    base = f"{item.name} is {format_calories(item.calories)} cal per {format_serving(item)}."
    if descriptor:
        return RuleBasedResponse(
            f"{base} {descriptor} ({format_number(oz)}oz) is approximately {round(total)} calories.",
            guardrail="portion_calories",
        )
    return RuleBasedResponse(
        f"{base} At {format_number(oz)}oz that's approximately {round(total)} calories.",
        guardrail="portion_calories",
    )


def build_pork_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    if "pork" not in content.lower() or not re.search(r"\b(is|are|anything|there)\b", content.lower()):
        return None
    hall = parse_hall(content) or default_hall(items)
    meal = parse_meal(content) or default_meal(content)
    candidates = [
        item
        for item in filter_scope(items, hall=hall, meal=meal)
        if re.search(r"\b(pork|bacon|ham|pepperoni|salami)\b", f"{item.name} {item.ingredients}", re.I)
    ]
    if not candidates:
        return RuleBasedResponse(f"I don't see pork listed at {hall} tonight.", guardrail="pork")
    joined = ", ".join(f"{item.name} ({item.category})" for item in unique_items(candidates))
    return RuleBasedResponse(
        f"Yes, the following items at {hall} contain pork: {joined}.",
        guardrail="pork",
    )


def build_allergy_response(
    content: str,
    items: list[MenuItem],
    menu_date: str,
    include_halal_disclaimer: bool,
) -> RuleBasedResponse | None:
    allergen = parse_allergen(content)
    if allergen is None:
        return None
    hall = parse_hall(content) or default_hall(items)
    meal = parse_meal(content) or default_meal(content)
    scope = filter_scope(items, hall=hall, meal=meal)

    filters = requested_dietary_filters(content)
    if filters:
        safe = [
            item
            for item in scope
            if matches_dietary_filters(item, filters) and not has_allergen(item, allergen)
        ]
        safe = filter_default_menu_items(unique_items(safe), content)
        if not safe:
            return RuleBasedResponse(
                f"I couldn't find {dietary_label(filters)} items without {allergen} flagged in today's menu.",
                guardrail="allergy_filter",
            )
        lines = [f"{dietary_label(filters).capitalize()} options without {allergen} flagged:", ""]
        lines.extend(format_basic_item_line(item) for item in safe)
        return RuleBasedResponse("\n".join(lines), guardrail="allergy_filter")

    avoid = [item for item in scope if has_allergen(item, allergen)]
    if avoid:
        names = ", ".join(item.name for item in unique_items(avoid))
        return RuleBasedResponse(
            f"The following items at {hall} contain {allergen} and should be avoided: {names}. "
            f"All other items on tonight's menu do not list {allergen} as an allergen.",
            guardrail="allergy",
        )
    return RuleBasedResponse(
        f"I don't see {allergen} flagged as an allergen for items at {hall} tonight.",
        guardrail="allergy",
    )


def item_from_doc(doc: Any) -> MenuItem:
    metadata = getattr(doc, "metadata", {}) or {}
    content = getattr(doc, "page_content", "")
    return MenuItem(
        name=str(metadata.get("short_name") or extract_line(content, "Item") or "").strip(),
        hall=str(metadata.get("dining_hall") or extract_line(content, "Dining Hall") or "").strip(),
        meal=str(metadata.get("meal_period") or extract_line(content, "Meal") or "").strip(),
        category=str(metadata.get("category") or extract_line(content, "Category") or "").strip(),
        halal_status=str(metadata.get("halal_status") or "UNCERTAIN").upper(),
        halal_reason=str(metadata.get("halal_reason") or extract_line(content, "Halal Reason") or "").strip(),
        is_vegan=bool(metadata.get("is_vegan", False)),
        is_vegetarian=bool(metadata.get("is_vegetarian", False)),
        contains_shellfish=bool(metadata.get("contains_shellfish", False)),
        shellfish_note=str(metadata.get("shellfish_note") or extract_line(content, "Shellfish Note") or "").strip(),
        ingredients=str(metadata.get("ingredients") or extract_line(content, "Ingredients") or "").strip(),
        allergens_present=parse_allergens(metadata.get("allergens_present") or extract_line(content, "Allergens")),
        calories=float_or_none(metadata.get("calories")),
        serving_size=float_or_none(metadata.get("serving_size")),
        serving_unit=str(metadata.get("serving_size_unit") or "oz").strip() or "oz",
        calories_per_oz=float_or_none(metadata.get("calories_per_oz")),
        protein=float_or_none(metadata.get("protein")),
        fat=float_or_none(metadata.get("fat")),
        carbs=float_or_none(metadata.get("carbs")),
        fiber=float_or_none(metadata.get("fiber")),
        sodium=float_or_none(metadata.get("sodium")),
        cholesterol=float_or_none(metadata.get("cholesterol")),
    )


def extract_line(content: str, label: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", content or "", re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_allergens(value: Any) -> tuple[str, ...]:
    if value in (None, "", "None"):
        return ()
    if isinstance(value, (list, tuple, set)):
        parts = value
    else:
        parts = re.split(r"[,|;]", str(value))
    return tuple(part.strip() for part in parts if part and part.strip() and part.strip() != "None")


def float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_hall(content: str) -> str | None:
    q = content.lower()
    for alias, hall in HALL_ALIASES.items():
        if alias in q:
            return hall
    return None


def parse_meal(content: str) -> str | None:
    q = content.lower()
    if "brunch" in q or "breakfast" in q:
        return "Brunch"
    if "lunch" in q:
        return "Lunch"
    if "dinner" in q or "tonight" in q or "right now" in q:
        return "Dinner"
    return None


def default_meal(content: str) -> str | None:
    return "Dinner" if re.search(r"\b(today|now|available|options|meal|meals|anything|what's)\b", content.lower()) else None


def requested_dietary_filters(content: str) -> list[str]:
    q = content.lower()
    filters: list[str] = []
    if "halal" in q:
        filters.append("halal")
    if "vegan" in q and not re.search(r"\binclud(?:e|ing)\s+vegan\b", q):
        filters.append("vegan")
    if "vegetarian" in q or "veggie" in q:
        filters.append("vegetarian")
    return filters


def looks_like_option_request(content: str) -> bool:
    q = content.lower()
    return bool(
        re.search(r"\b(what's|what|any|show|list|options?|meals?|anything|where|which|can i eat)\b", q)
    )


def is_halal_status_question(content: str) -> bool:
    q = content.lower().strip()
    return (
        "halal" in q
        and bool(re.match(r"^(is|are)\b", q))
        and "anything" not in q
        and not re.match(r"^(is|are)\s+there\b", q)
    )


def is_nutrition_question(content: str) -> bool:
    return bool(
        re.search(
            r"\b(calorie|calories|macro|macros|protein|sodium|fiber|cholesterol|carbon footprint)\b",
            content.lower(),
        )
    )


def is_portion_question(content: str) -> bool:
    q = content.lower()
    return bool(
        re.search(r"\b\d+(?:\.\d+)?\s*oz\b", q)
        or "half a serving" in q
        or "quarter serving" in q
        or "serving and a half" in q
        or "one and a half serving" in q
    )


def asks_for_hours(content: str) -> bool:
    return bool(re.search(r"\b(open|hours?|time does .* open|when does .* open)\b", content.lower()))


def present_halls(items: list[MenuItem]) -> set[str]:
    return {item.hall for item in items if item.hall}


def default_hall(items: list[MenuItem]) -> str:
    halls = sorted(present_halls(items))
    return halls[0] if len(halls) == 1 else "all dining halls"


def missing_hall_response(hall: str, items: list[MenuItem], filters: list[str]) -> str:
    halls = sorted(present_halls(items))
    available = ", ".join(halls) if halls else "no dining halls"
    fallback = halls[0] if len(halls) == 1 else None
    if fallback:
        return (
            f"I don't have menu data for {hall} for today. I currently have data for {fallback}. "
            f"Would you like to see {dietary_label(filters)} options there instead?"
        )
    return f"I don't have menu data for {hall} for today. I currently have data for {available}."


def filter_scope(
    items: list[MenuItem],
    hall: str | None = None,
    meal: str | None = None,
) -> list[MenuItem]:
    scoped = items
    if hall:
        scoped = [item for item in scoped if item.hall == hall]
    if meal:
        scoped = [item for item in scoped if item.meal == meal]
    return scoped


def matches_dietary_filters(item: MenuItem, filters: list[str]) -> bool:
    for requested_filter in filters:
        if requested_filter == "halal" and item.halal_status != "HALAL":
            return False
        if requested_filter == "vegan" and item.is_vegan is not True:
            return False
        if requested_filter == "vegetarian" and item.is_vegetarian is not True:
            return False
    return True


def filter_default_menu_items(items: list[MenuItem], content: str) -> list[MenuItem]:
    q = content.lower()
    if any(category in q for category in DEFAULT_EXCLUDED_CATEGORIES) or asks_for_all_categories(q):
        return items
    return [item for item in items if not is_default_excluded(item)]


def asks_for_all_categories(content: str) -> bool:
    q = content.lower()
    return bool(
        re.search(r"\b(show|list|give me|include)\s+all\s+(items|categories|menu|foods?|options?)\b", q)
        or re.search(r"\ball\s+(items|categories|menu|foods?)\b", q)
    )


def is_default_excluded(item: MenuItem) -> bool:
    haystack = f"{item.category} {item.name}".lower()
    if any(term in haystack for term in DEFAULT_EXCLUDED_CATEGORIES):
        return True
    if item.serving_size is not None and item.serving_size <= 0.5:
        return True
    if item.calories is not None and item.calories <= 10:
        return True
    return any(phrase in item.name.lower() for phrase in DEFAULT_EXCLUDED_ITEM_PHRASES)


def unique_items(items: list[MenuItem]) -> list[MenuItem]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[MenuItem] = []
    for item in items:
        key = (item.hall, item.meal, item.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def sort_by_name(items: list[MenuItem]) -> list[MenuItem]:
    return sorted(items, key=lambda item: item.name.lower())


def format_halal_options(
    content: str,
    items: list[MenuItem],
    hall: str | None,
    meal: str | None,
    include_halal_disclaimer: bool,
) -> str:
    across_all = hall is None and len({item.hall for item in items if item.hall}) > 1
    if across_all:
        lines: list[str] = ["Halal options across all dining halls tonight:"]
        for hall_name in ordered_halls(items):
            hall_items = [item for item in items if item.hall == hall_name]
            lines.extend(["", f"{hall_name}:", *format_halal_groups(hall_items)])
    else:
        location = hall or default_hall(items)
        meal_text = f" for {meal.lower()}" if meal else ""
        tonight = " tonight" if meal == "Dinner" or "tonight" in content.lower() else ""
        lines = [f"Here are the halal options at {location}{meal_text}{tonight}:", *format_halal_groups(items)]
    if include_halal_disclaimer:
        lines.extend(["", HALAL_NOTE])
    return "\n".join(lines)


def format_halal_vegan_options(
    content: str,
    items: list[MenuItem],
    hall: str | None,
    meal: str | None,
) -> str:
    location = hall or default_hall(items)
    meal_text = f" for {meal.lower()}" if meal else ""
    tonight = " tonight" if meal == "Dinner" or "tonight" in content.lower() else ""
    lines = [
        f"Yes, all vegan options shown here are classified halal. Here are the vegan options at {location}{meal_text}{tonight}:",
        "",
    ]
    lines.extend(format_basic_item_line(item, include_diet=False) for item in sort_by_name(items))
    return "\n".join(lines)


def format_halal_groups(items: list[MenuItem]) -> list[str]:
    proteins = [item for item in items if is_protein_item(item)]
    veg = [item for item in items if not is_protein_item(item) and (item.is_vegan or item.is_vegetarian)]
    other = [item for item in items if item not in proteins and item not in veg]

    lines: list[str] = []
    if proteins:
        lines.extend(["Proteins:", ""])
        lines.extend(f"✅ {format_basic_item_line(item, include_diet=False)}" for item in proteins)
    if veg:
        if lines:
            lines.append("")
        lines.extend(["Vegan/Vegetarian (halal):", ""])
        lines.extend(format_basic_item_line(item, include_diet=True) for item in veg)
    if other:
        if lines:
            lines.append("")
        lines.extend(["Other:", ""])
        lines.extend(format_basic_item_line(item, include_diet=False) for item in other)
    return lines


def ordered_halls(items: list[MenuItem]) -> list[str]:
    present = {item.hall for item in items if item.hall}
    ordered = [hall for hall in HALL_DISPLAY_ORDER if hall in present]
    ordered.extend(sorted(present - set(HALL_DISPLAY_ORDER)))
    return ordered


def is_protein_item(item: MenuItem) -> bool:
    if item.is_vegan or item.is_vegetarian:
        return False
    haystack = f"{item.name} {item.category} {item.ingredients}".lower()
    return any(term in haystack for term in MEAT_TERMS)


def dietary_label(filters: list[str]) -> str:
    return " and ".join(filters)


def format_basic_item_line(item: MenuItem, include_diet: bool = False) -> str:
    diet = ""
    if include_diet:
        if item.is_vegan:
            diet = " (vegan)"
        elif item.is_vegetarian:
            diet = " (vegetarian)"
    if item.calories is None:
        return f"{item.name}{diet}"
    return f"{item.name}{diet} — {format_calories(item.calories)} cal per {format_serving(item)}"


def format_serving(item: MenuItem, include_word: bool = True) -> str:
    if item.serving_size is None:
        return "serving" if include_word else "serving"
    unit = item.serving_unit or "oz"
    serving = f"{format_number(item.serving_size)}{unit}"
    return f"{serving} serving" if include_word else serving


def format_calories(value: float | None) -> str:
    return str(round(value)) if value is not None else "unknown"


def format_grams(value: float | None) -> str:
    return format_number(value) if value is not None else "unknown"


def format_mg(value: float | None) -> str:
    if value is None:
        return "unknown"
    rounded = round(value, 2)
    if rounded.is_integer():
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def format_number(value: float | None) -> str:
    if value is None:
        return "unknown"
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def format_macros(item: MenuItem) -> str:
    return (
        f"{item.name} ({format_serving(item)}): {format_calories(item.calories)} cal | "
        f"{format_grams(item.protein)}g protein | {format_grams(item.fat)}g fat | "
        f"{format_grams(item.carbs)}g carbs | {format_mg(item.sodium)}mg sodium."
    )


def halal_positive_reason(item: MenuItem) -> str:
    halal_segment = find_halal_ingredient_segment(item.ingredients)
    if halal_segment:
        return f"contains '{halal_segment}' explicitly labeled in ingredients."
    if item.is_vegan:
        return "marked vegan, contains no meat or forbidden ingredients."
    if item.is_vegetarian:
        return "marked vegetarian, contains no meat or forbidden ingredients."
    reason = normalize_reason(item.halal_reason)
    return reason if reason else "contains no forbidden or ambiguous ingredients."


def halal_negative_reason(item: MenuItem) -> str:
    reason = normalize_reason(item.halal_reason)
    if reason:
        return reason
    return "contains a forbidden or non-halal ingredient."


def normalize_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        return ""
    reason = reason[0].lower() + reason[1:]
    return reason.rstrip(".")


def find_halal_ingredient_segment(ingredients: str) -> str | None:
    for segment in re.split(r"[;|]", ingredients or ""):
        if "halal" in segment.lower():
            return segment.strip()
    return None


def halal_notes(item: MenuItem) -> list[str]:
    notes: list[str] = []
    if item.contains_shellfish:
        shellfish = item.shellfish_note or "shellfish"
        notes.append(f"contains {shellfish.lower()} (shellfish).")
    if has_allergen(item, "fish"):
        notes.append("also contains fish allergen.")
    if has_allergen(item, "sesame"):
        notes.append("contains sesame allergen.")
    return notes


def parse_allergen(content: str) -> str | None:
    q = content.lower()
    if "tree nut" in q or "tree nuts" in q:
        return "tree nuts"
    if "gluten" in q or "wheat" in q:
        return "gluten"
    if "shellfish" in q:
        return "shellfish"
    if "fish" in q:
        return "fish"
    if "sesame" in q:
        return "sesame"
    return None


def has_allergen(item: MenuItem, allergen: str) -> bool:
    haystack = " ".join(item.allergens_present).lower()
    if allergen == "gluten":
        return "gluten" in haystack or "wheat" in haystack
    if allergen == "tree nuts":
        return "tree nut" in haystack or "tree nuts" in haystack
    if allergen == "shellfish":
        return "shellfish" in haystack or item.contains_shellfish
    return allergen in haystack


def best_item_match(content: str, items: list[MenuItem], strict: bool = False) -> MenuItem | None:
    query_terms = item_query_terms(content)
    if not query_terms:
        return None

    def score(item: MenuItem) -> tuple[int, int, int, int]:
        name_terms = terms(item.name)
        overlap = len(query_terms & name_terms)
        phrase_bonus = 5 if item.name.lower() in content.lower() else 0
        ingredient_bonus = 1 if query_terms & terms(item.ingredients) else 0
        missing_terms = len(query_terms - name_terms - terms(item.ingredients))
        return overlap + phrase_bonus + ingredient_bonus, overlap, -missing_terms, len(name_terms)

    best = sorted(items, key=score, reverse=True)[0]
    best_score = score(best)
    if best_score[0] <= 0 or best_score[1] <= 0:
        return None
    if strict and best_score[2] < 0:
        return None
    if len(query_terms) >= 3 and best_score[1] / len(query_terms) < 0.67:
        return None
    return best


def item_query_terms(content: str) -> set[str]:
    return {
        term
        for term in terms(content)
        if term not in STOPWORDS
        and not term.isdigit()
        and not re.fullmatch(r"\d+(?:\.\d+)?oz", term)
    }


def clean_requested_item_name(content: str) -> str:
    cleaned = re.sub(r"^\s*(is|are)\s+there\s+", "", content, flags=re.I)
    cleaned = re.sub(r"\b(at|for)\s+(crossroads|cafe\s*3|clark\s+kerr|foothill|brunch|lunch|dinner|today|tonight)\b.*$", "", cleaned, flags=re.I)
    cleaned = cleaned.strip(" ?!.")
    return cleaned or "that item"


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def extract_oz_amount(content: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*oz\b", content.lower())
    return float(match.group(1)) if match else None


def extract_serving_fraction(content: str) -> float | None:
    q = content.lower()
    if "half a serving" in q:
        return 0.5
    if "quarter serving" in q or "a quarter" in q:
        return 0.25
    if "serving and a half" in q or "one and a half serving" in q:
        return 1.5
    return None


def fraction_descriptor(fraction: float) -> str:
    if fraction == 0.5:
        return "Half a serving"
    if fraction == 0.25:
        return "A quarter serving"
    if fraction == 1.5:
        return "One and a half servings"
    return f"{format_number(fraction)} servings"


def extract_calorie_limit(content: str) -> int | None:
    match = re.search(r"\bunder\s+(\d+)\s*(?:cal|calories)?\b", content.lower())
    return int(match.group(1)) if match else None

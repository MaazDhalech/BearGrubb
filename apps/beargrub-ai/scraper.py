from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlencode

from config import DINING_HALLS, DINING_MENU_ENDPOINT, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

DIRECT_XML_MENU_BASE = "https://dining.berkeley.edu/wp-content/uploads/menus-exportimport"
DIRECT_XML_FILES = {
    "crossroads": "Crossroads",
    "cafe3": "Cafe_3",
    "clark-kerr": "Clark_Kerr_Campus",
    "foothill": "Foothill",
}

NUTRIENT_FIELDS = [
    "calories",
    "fat",
    "sat_fat",
    "trans_fat",
    "cholesterol",
    "sodium",
    "carbs",
    "fiber",
    "sugar",
    "protein",
]


def build_menu_url(location_id: str, menu_date: str) -> str:
    query = urlencode({"location": location_id, "date": menu_date})
    return f"{DINING_MENU_ENDPOINT}?{query}"


def build_direct_xml_url(location_id: str, menu_date: str) -> str:
    filename = DIRECT_XML_FILES[location_id]
    compact_date = menu_date.replace("-", "")
    return f"{DIRECT_XML_MENU_BASE}/{filename}_{compact_date}.xml"


def fetch_all(menu_date: str, hall: str = "ALL", session: Any | None = None) -> list[dict[str, Any]]:
    """Fetch and parse menus for one hall or all supported Berkeley dining halls."""
    items: list[dict[str, Any]] = []
    for dining_hall, location_id in _selected_halls(hall).items():
        root = fetch_menu_xml(location_id, menu_date, session=session)
        if root is None:
            continue
        items.extend(parse_menu(root, dining_hall=dining_hall, menu_date=menu_date))
    return items


def fetch_menu_xml(location_id: str, menu_date: str, session: Any | None = None) -> ET.Element | None:
    url = build_menu_url(location_id, menu_date)
    if session is None:
        import requests

        session = requests

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("Failed to fetch dining menu for %s on %s", location_id, menu_date)
        return None

    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        if status_code == 404:
            fallback_root = fetch_direct_menu_xml(location_id, menu_date, session=session)
            if fallback_root is not None:
                return fallback_root
        logger.error(
            "Dining menu fetch failed for %s on %s with status %s",
            location_id,
            menu_date,
            status_code,
        )
        return None

    try:
        return parse_response_content(response.content)
    except (ET.ParseError, ValueError, TypeError):
        logger.exception("Failed to parse dining menu response for %s on %s", location_id, menu_date)
        return None


def fetch_direct_menu_xml(location_id: str, menu_date: str, session: Any | None = None) -> ET.Element | None:
    if location_id not in DIRECT_XML_FILES:
        return None
    if session is None:
        import requests

        session = requests

    url = build_direct_xml_url(location_id, menu_date)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("Failed to fetch direct dining XML for %s on %s", location_id, menu_date)
        return None

    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        logger.error(
            "Direct dining XML fetch failed for %s on %s with status %s",
            location_id,
            menu_date,
            status_code,
        )
        return None

    try:
        return parse_response_content(response.content)
    except (ET.ParseError, ValueError, TypeError):
        logger.exception("Failed to parse direct dining XML for %s on %s", location_id, menu_date)
        return None


def parse_response_content(content: bytes | str) -> ET.Element:
    """Parse XML directly, or unwrap a JSON response containing an XML string."""
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content

    stripped = text.strip()
    if stripped.startswith("<"):
        return ET.fromstring(stripped)

    payload = json.loads(stripped)
    xml_text = _find_xml_string(payload)
    if not xml_text:
        raise ValueError("Response did not contain XML menu data")
    return ET.fromstring(xml_text)


def parse_menu(root: ET.Element, dining_hall: str, menu_date: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for menu in root.findall(".//menu"):
        meal_period = normalize_meal_period(
            menu.attrib.get("mealperiodname") or menu.attrib.get("name") or ""
        )
        recipes = menu.find("recipes")
        if recipes is None or len(recipes) == 0:
            continue

        for recipe in recipes.findall("recipe"):
            parsed.append(parse_recipe(recipe, dining_hall, meal_period, menu_date))
    return parsed


def parse_recipe(
    recipe: ET.Element,
    dining_hall: str,
    meal_period: str,
    menu_date: str,
) -> dict[str, Any]:
    nutrients = parse_nutrients(recipe.attrib.get("nutrients", ""))
    serving_size = _float_or_none(recipe.attrib.get("servingSize"))
    calories = nutrients.get("calories")
    calories_per_oz = None
    if calories is not None and serving_size and serving_size > 0:
        calories_per_oz = calories / serving_size

    allergens = parse_named_children(recipe.find("allergens"), "allergen")
    dietary_choices = parse_named_children(recipe.find("dietaryChoices"), "dietaryChoice")

    return {
        "date": menu_date,
        "recipe_id": recipe.attrib.get("id", ""),
        "dining_hall": dining_hall,
        "meal_period": meal_period,
        "category": recipe.attrib.get("category", ""),
        "description": recipe.attrib.get("description", ""),
        "short_name": recipe.attrib.get("shortName", ""),
        "serving_size": serving_size,
        "serving_size_unit": recipe.attrib.get("servingSizeUnit", ""),
        "nutrients_raw": recipe.attrib.get("nutrients", ""),
        "ingredients": (recipe.findtext("ingredients") or "").strip(),
        "allergens": allergens,
        "allergens_present": [
            name for name, value in allergens.items() if str(value).strip().lower() == "yes"
        ],
        "dietary_choices": dietary_choices,
        "is_vegan": dietary_choices.get("Vegan Option") == "Yes",
        "is_vegetarian": dietary_choices.get("Vegetarian Option") == "Yes"
        or dietary_choices.get("Vegan Option") == "Yes",
        **nutrients,
        "calories_per_oz": calories_per_oz,
    }


def normalize_meal_period(raw_meal_period: str) -> str:
    meal_period = (raw_meal_period or "").strip()
    lower = meal_period.lower()
    if "brunch" in lower:
        return "Brunch"
    if "breakfast" in lower:
        return "Brunch"
    if "lunch" in lower:
        return "Lunch"
    if "dinner" in lower:
        return "Dinner"
    return meal_period


def parse_nutrients(raw: str) -> dict[str, float | None]:
    values = raw.split("|") if raw else []
    parsed: dict[str, float | None] = {}
    for index, field in enumerate(NUTRIENT_FIELDS):
        parsed[field] = _float_or_none(values[index]) if index < len(values) else None
    return parsed


def parse_named_children(parent: ET.Element | None, child_tag: str) -> dict[str, str]:
    if parent is None:
        return {}
    return {
        child.attrib.get("id", ""): (child.text or "").strip()
        for child in parent.findall(child_tag)
        if child.attrib.get("id")
    }


def _selected_halls(hall: str) -> dict[str, str]:
    if hall == "ALL":
        return dict(DINING_HALLS)
    if hall in DINING_HALLS:
        return {hall: DINING_HALLS[hall]}
    for dining_hall, location_id in DINING_HALLS.items():
        if hall == location_id:
            return {dining_hall: location_id}
    raise ValueError(f"Unsupported dining hall: {hall}")


def _find_xml_string(value: Any) -> str | None:
    if isinstance(value, str) and "<menu" in value:
        return value
    if isinstance(value, dict):
        for child in value.values():
            found = _find_xml_string(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_xml_string(child)
            if found:
                return found
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(fetch_all(str(date.today())), indent=2))

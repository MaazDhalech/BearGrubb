from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from typing import Any

from config import CACHE_PATH, OPENAI_MODEL

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """
You are determining halal status for a UC Berkeley dining item.
Classify based on ingredients only. Use these rules strictly:

NOT_HALAL if:
- Contains pork, lard, bacon, ham, gelatin (unless 'halal gelatin')
- Contains alcohol: wine, beer, spirits, cooking wine, sherry
- Contains vanilla extract (always contains alcohol)
- Contains beef/chicken/lamb/turkey/duck NOT labeled HALAL in ingredient name

UNCERTAIN if:
- 'Natural flavors' with unknown source - quote exact ingredient
- 'Enzymes' with unknown source - quote exact ingredient
- Any additive where halal status is unknowable from ingredients alone
- Ambiguous sauces or bases where meat source is unclear

HALAL if:
- All meat explicitly labeled HALAL in ingredient name
- No forbidden or ambiguous ingredients

SHELLFISH: halal - do not mark NOT_HALAL for shellfish.
Always flag if shellfish present.

Return JSON only, no markdown:
{
  "status": "HALAL" | "NOT_HALAL" | "UNCERTAIN",
  "reason": "one sentence, quote the specific ingredient causing the decision",
  "contains_shellfish": true | false,
  "shellfish_note": "specific shellfish ingredient name" | null
}
"""

FORBIDDEN_PATTERNS = [
    (r"\bPORK\b", "pork"),
    (r"\bLARD\b", "lard"),
    (r"\bBACON\b", "bacon"),
    (r"\bHAM\b", "ham"),
    (r"\bGELATIN\b", "gelatin"),
    (r"\bWINE\b", "wine"),
    (r"\bBEER\b", "beer"),
    (r"\bSHERRY\b", "sherry"),
    (r"\bALCOHOL\b", "alcohol"),
    (r"\bSPIRITS\b", "spirits"),
    (r"\bVANILLA EXTRACT\b", "vanilla extract"),
]

MEATS = ["BEEF", "CHICKEN", "LAMB", "TURKEY", "VEAL", "DUCK"]

SHELLFISH_TERMS = [
    "SHELLFISH",
    "SHRIMP",
    "PRAWN",
    "CRAB",
    "LOBSTER",
    "OYSTER",
    "CLAM",
    "MUSSEL",
    "SCALLOP",
]

AMBIGUOUS_PATTERNS = [
    (r"\bNATURAL FLAVORS?\b", "natural flavors with unknown source"),
    (r"\bENZYMES?\b", "enzymes with unknown source"),
]

GPT_REVIEW_PATTERNS = [
    r"\bBASE\b",
    r"\bDEMI GLACE\b",
]

VALID_STATUSES = {"HALAL", "NOT_HALAL", "UNCERTAIN"}


def load_cache(path: str = CACHE_PATH) -> dict[str, dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache: dict[str, dict[str, Any]], path: str = CACHE_PATH) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def normalize(ingredients: str) -> str:
    """Normalize before any string matching or hashing."""
    s = (ingredients or "").upper()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_cache_key(ingredients: str) -> str:
    normalized = normalize(ingredients)
    return hashlib.md5(normalized.encode()).hexdigest()


def deterministic_classify(normalized: str, ingredients: str = "") -> dict[str, Any] | None:
    contains_shellfish, shellfish_note = detect_shellfish(normalized)

    if not normalized:
        return _result(
            "UNCERTAIN",
            "No ingredient data available",
            contains_shellfish=contains_shellfish,
            shellfish_note=shellfish_note,
        )

    for pattern, label in FORBIDDEN_PATTERNS:
        if pattern == r"\bGELATIN\b":
            if re.search(pattern, normalized) and "HALAL GELATIN" not in normalized:
                return _result(
                    "NOT_HALAL",
                    f"Contains {label}",
                    contains_shellfish=contains_shellfish,
                    shellfish_note=shellfish_note,
                )
        elif re.search(pattern, normalized):
            return _result(
                "NOT_HALAL",
                f"Contains {label}",
                contains_shellfish=contains_shellfish,
                shellfish_note=shellfish_note,
            )

    for segment in normalized_ingredient_segments(ingredients or normalized):
        for meat in MEATS:
            if re.search(rf"\b{meat}\b", segment) and "HALAL" not in segment:
                return _result(
                    "NOT_HALAL",
                    f"Contains {meat.lower()} not labeled halal",
                    contains_shellfish=contains_shellfish,
                    shellfish_note=shellfish_note,
                )

    for pattern, reason in AMBIGUOUS_PATTERNS:
        if re.search(pattern, normalized):
            return _result(
                "UNCERTAIN",
                f"Contains {reason}",
                contains_shellfish=contains_shellfish,
                shellfish_note=shellfish_note,
            )

    if any(re.search(pattern, normalized) for pattern in GPT_REVIEW_PATTERNS):
        return None

    return _result(
        "HALAL",
        "No forbidden or ambiguous ingredients found",
        contains_shellfish=contains_shellfish,
        shellfish_note=shellfish_note,
    )


def classify(
    item: dict[str, Any],
    cache: dict[str, dict[str, Any]] | None = None,
    openai_client: Any | None = None,
    cache_path: str | None = CACHE_PATH,
) -> dict[str, Any]:
    ingredients = item.get("ingredients") or ""
    normalized = normalize(ingredients)
    key = get_cache_key(ingredients)
    active_cache = cache if cache is not None else load_cache(cache_path or CACHE_PATH)

    if key in active_cache:
        return deepcopy(_coerce_result(active_cache[key]))

    result = deterministic_classify(normalized, ingredients)
    if result is None:
        result = gpt_classify(ingredients, normalized, openai_client=openai_client)

    active_cache[key] = result
    if cache_path is not None:
        save_cache(active_cache, cache_path)
    return deepcopy(result)


def classify_all(
    raw_items: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]] | None = None,
    openai_client: Any | None = None,
    cache_path: str | None = CACHE_PATH,
) -> list[dict[str, Any]]:
    active_cache = cache if cache is not None else load_cache(cache_path or CACHE_PATH)
    classified: list[dict[str, Any]] = []
    for item in raw_items:
        result = classify(
            item,
            cache=active_cache,
            openai_client=openai_client,
            cache_path=cache_path,
        )
        enriched = dict(item)
        enriched.update(
            {
                "halal_status": result["status"],
                "halal_reason": result["reason"],
                "contains_shellfish": result["contains_shellfish"],
                "shellfish_note": result["shellfish_note"],
            }
        )
        classified.append(enriched)
    return classified


def gpt_classify(
    ingredients: str,
    normalized: str,
    openai_client: Any | None = None,
) -> dict[str, Any]:
    contains_shellfish, shellfish_note = detect_shellfish(normalized)
    if openai_client is None:
        try:
            from openai import OpenAI

            openai_client = OpenAI()
        except ImportError:
            logger.warning("OpenAI package is not installed; returning UNCERTAIN classification")
            return _result(
                "UNCERTAIN",
                "Unable to classify ambiguous ingredients without OpenAI client",
                contains_shellfish=contains_shellfish,
                shellfish_note=shellfish_note,
            )

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": CLASSIFICATION_PROMPT},
            {"role": "user", "content": f"Ingredients: {ingredients}"},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        logger.warning("OpenAI classification returned invalid JSON: %r", content)
        parsed = {
            "status": "UNCERTAIN",
            "reason": "Classifier returned invalid JSON",
        }
    result = _coerce_result(parsed)

    if contains_shellfish:
        result["contains_shellfish"] = True
        result["shellfish_note"] = shellfish_note
    return result


def normalized_ingredient_segments(ingredients: str) -> list[str]:
    return [normalize(segment) for segment in (ingredients or "").split(";") if normalize(segment)]


def detect_shellfish(normalized: str) -> tuple[bool, str | None]:
    for term in SHELLFISH_TERMS:
        if re.search(rf"\b{term}\b", normalized):
            return True, term.title()
    return False, None


def _coerce_result(value: dict[str, Any]) -> dict[str, Any]:
    status = str(value.get("status", "UNCERTAIN")).upper()
    if status not in VALID_STATUSES:
        status = "UNCERTAIN"
    reason = str(value.get("reason") or "No reason provided")
    contains_shellfish = bool(value.get("contains_shellfish", False))
    shellfish_note = value.get("shellfish_note")
    if not contains_shellfish:
        shellfish_note = None
    return _result(status, reason, contains_shellfish, shellfish_note)


def _result(
    status: str,
    reason: str,
    contains_shellfish: bool = False,
    shellfish_note: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "contains_shellfish": contains_shellfish,
        "shellfish_note": shellfish_note if contains_shellfish else None,
    }

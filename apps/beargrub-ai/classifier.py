from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from typing import Any

from config import CACHE_PATH, OPENAI_MODEL
from prompts import CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

SHELLFISH_TERMS = [
    "SHELLFISH", "SHRIMP", "PRAWN", "CRAB", "LOBSTER",
    "OYSTER", "CLAM", "MUSSEL", "SCALLOP",
]

VALID_STATUSES = {"HALAL", "NOT_HALAL", "UNCERTAIN"}
CLASSIFICATION_CACHE_VERSION = "v3"


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
    s = (ingredients or "").upper()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_cache_key(ingredients: str) -> str:
    normalized = normalize(ingredients)
    return hashlib.md5(f"{CLASSIFICATION_CACHE_VERSION}:{normalized}".encode()).hexdigest()


def detect_shellfish(normalized: str) -> tuple[bool, str | None]:
    for term in SHELLFISH_TERMS:
        if re.search(rf"\b{term}\b", normalized):
            return True, term.title()
    return False, None


def classify(
    item: dict[str, Any],
    cache: dict[str, dict[str, Any]] | None = None,
    openai_client: Any | None = None,
    cache_path: str | None = CACHE_PATH,
) -> dict[str, Any]:
    ingredients = item.get("ingredients") or ""
    key = get_cache_key(ingredients)
    active_cache = cache if cache is not None else load_cache(cache_path or CACHE_PATH)

    if key in active_cache:
        return deepcopy(_coerce_result(active_cache[key]))

    result = gpt_classify(ingredients, openai_client=openai_client)

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
    openai_client: Any | None = None,
) -> dict[str, Any]:
    normalized = normalize(ingredients)
    contains_shellfish, shellfish_note = detect_shellfish(normalized)

    if openai_client is None:
        try:
            from openai import OpenAI
            openai_client = OpenAI()
        except ImportError:
            logger.warning("OpenAI package not installed; returning UNCERTAIN")
            return _result("UNCERTAIN", "Cannot classify without OpenAI client", contains_shellfish, shellfish_note)

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
        logger.warning("GPT classification returned invalid JSON: %r", content)
        parsed = {"status": "UNCERTAIN", "reason": "Classifier returned invalid JSON"}

    result = _coerce_result(parsed)
    if contains_shellfish:
        result["contains_shellfish"] = True
        result["shellfish_note"] = shellfish_note
    return result


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

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from classifier import classify_all
from config import DINING_HALLS
from rag import embed_menu
from scraper import fetch_all

logger = logging.getLogger(__name__)

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_menu",
            "description": (
                "Manually refresh the dining hall menu. "
                "Only call if the user explicitly asks to refresh "
                "or if data seems incorrect for today."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dining_hall": {
                        "type": "string",
                        "enum": ["Crossroads", "Cafe 3", "Clark Kerr", "Foothill", "ALL"],
                    },
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["dining_hall", "date"],
            },
        },
    }
]


def handle_tool_call(
    name: str,
    args: dict[str, Any],
    db: Any,
    cache: dict[str, dict[str, Any]] | None = None,
) -> Any:
    if name != "get_menu":
        raise ValueError(f"Unsupported MCP tool: {name}")

    dining_hall = args.get("dining_hall")
    menu_date = args.get("date")
    _validate_get_menu_args(dining_hall, menu_date)

    raw = fetch_all(menu_date, hall=dining_hall)
    if not raw:
        logger.warning(
            "Manual menu refresh returned no items for %s on %s; keeping existing store",
            dining_hall,
            menu_date,
        )
        return db

    classified = classify_all(raw, cache=cache)
    return embed_menu(classified)


def _validate_get_menu_args(dining_hall: Any, menu_date: Any) -> None:
    allowed_halls = set(DINING_HALLS) | {"ALL"}
    if dining_hall not in allowed_halls:
        raise ValueError(f"Unsupported dining hall for get_menu: {dining_hall}")

    if not isinstance(menu_date, str):
        raise ValueError("get_menu date must be a YYYY-MM-DD string")

    try:
        date.fromisoformat(menu_date)
    except ValueError as exc:
        raise ValueError("get_menu date must use YYYY-MM-DD format") from exc

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Any

from classifier import classify_all, load_cache
from config import OPENAI_MODEL, POSTHOG_API_KEY
from menu_answers import build_menu_response, build_pre_context_response
from mcp_tools import MCP_TOOLS, handle_tool_call
from prompts import SYSTEM_PROMPT
from rag import embed_menu, is_stale, list_documents, retrieve
from scraper import fetch_all

logger = logging.getLogger(__name__)


try:
    if os.getenv("BEARGRUB_TEST_MODE") == "1":
        raise ImportError
    import chainlit as cl
except ImportError:
    cl = None

try:
    import posthog
except ImportError:
    posthog = None


class _FallbackUserSession:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value


class _FallbackMessage:
    def __init__(self, content: str = "") -> None:
        self.content = content
        self.sent = False

    async def stream_token(self, token: str) -> None:
        self.content += token

    async def send(self) -> None:
        self.sent = True


class _FallbackChainlit:
    user_session = _FallbackUserSession()
    Message = _FallbackMessage

    @staticmethod
    def on_chat_start(func=None):
        if func is None:
            def decorator(inner_func):
                return inner_func

            return decorator
        return func

    @staticmethod
    def on_message(func):
        return func


if cl is None:
    cl = _FallbackChainlit()


client = None
db = None
cache: dict[str, dict[str, Any]] = {}

HALAL_DISCLAIMER = (
    "Classifications are ingredient-based and intended as a guide, not a religious ruling."
)

UNSUPPORTED_DATE_TERMS = {
    "tomorrow",
    "week",
    "weekly",
    "weekend",
    "wek",
    "yesterday",
}

DIETARY_OPTION_TERMS = {
    "any",
    "available",
    "dish",
    "dishes",
    "find",
    "meal",
    "meals",
    "option",
    "options",
    "serve",
    "served",
    "serves",
    "serving",
    "show",
}


def configure_posthog() -> None:
    if posthog is not None and POSTHOG_API_KEY:
        posthog.api_key = POSTHOG_API_KEY


def get_distinct_id() -> str | None:
    distinct_id = cl.user_session.get("id")
    return str(distinct_id) if distinct_id else None


def capture_event(event: str, properties: dict[str, Any] | None = None) -> bool:
    if posthog is None:
        return False
    if not (POSTHOG_API_KEY or getattr(posthog, "api_key", None)):
        return False
    distinct_id = get_distinct_id()
    if not distinct_id:
        logger.info("Skipping PostHog event %s because Chainlit session id is unavailable", event)
        return False
    safe_properties = sanitize_event_properties(properties or {})
    posthog.capture(event=event, distinct_id=distinct_id, properties=safe_properties)
    return True


def sanitize_event_properties(properties: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {"content", "message", "query", "prompt", "response", "history", "context"}
    sanitized: dict[str, Any] = {}
    for key, value in properties.items():
        if key.lower() in blocked_keys:
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            sanitized[key] = value
    return sanitized


def get_openai_client():
    global client
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    return client


def init(menu_date: str | None = None) -> Any:
    """Server startup path. Loads cache, fetches today's menus, classifies, and embeds."""
    global db, cache
    menu_date = menu_date or str(date.today())
    cache = load_cache()
    db = refresh_menu(menu_date, existing_db=db)
    return db


def refresh_menu(menu_date: str, existing_db: Any = None) -> Any:
    raw = fetch_all(menu_date)
    if not raw:
        logger.warning("Initial or stale menu refresh returned no items for %s", menu_date)
        return existing_db if existing_db is not None else embed_menu([])
    classified = classify_all(raw, cache)
    return embed_menu(classified)


def ensure_fresh_menu(menu_date: str | None = None) -> Any:
    global db
    menu_date = menu_date or str(date.today())
    if db is None or is_stale(db):
        db = refresh_menu(menu_date, existing_db=db)
    return db


def build_context(chunks: list[Any]) -> str:
    return "\n\n".join(getattr(chunk, "page_content", str(chunk)) for chunk in chunks)


def build_messages(
    user_content: str,
    context: str,
    history: list[dict[str, str]],
    menu_date: str | None = None,
    include_halal_disclaimer_instruction: bool = False,
) -> list[dict[str, str]]:
    menu_date = menu_date or str(date.today())
    trimmed_history = trim_history(history)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(date=menu_date)},
        {"role": "system", "content": f"Menu context:\n{context}"},
    ]
    if include_halal_disclaimer_instruction:
        messages.append(
            {
                "role": "system",
                "content": (
                    "This is the first halal query in this session. Include the halal "
                    "classification disclaimer exactly once in this response."
                ),
            }
        )
    messages.extend(trimmed_history)
    messages.append({"role": "user", "content": user_content})
    return messages


def trim_history(history: list[dict[str, str]], limit: int = 10) -> list[dict[str, str]]:
    return list(history or [])[-limit:]


def append_history(
    history: list[dict[str, str]],
    user_content: str,
    assistant_content: str,
    limit: int = 10,
) -> list[dict[str, str]]:
    updated = list(history or [])
    updated.append({"role": "user", "content": user_content})
    updated.append({"role": "assistant", "content": assistant_content})
    return trim_history(updated, limit=limit)


def is_halal_query(content: str) -> bool:
    return "halal" in content.lower()


def should_show_halal_disclaimer(content: str) -> bool:
    return is_halal_query(content) and not cl.user_session.get("halal_disclaimer_shown", False)


def resolve_followup_content(user_content: str, history: list[dict[str, str]]) -> str:
    q = user_content.lower().strip()
    if not re.search(r"\b(sort|group|organize)\b.*\b(dining hall|hall)\b", q):
        return user_content
    previous_user_messages = [
        message.get("content", "")
        for message in reversed(history)
        if message.get("role") == "user"
    ]
    previous_dietary_query = next(
        (
            message
            for message in previous_user_messages
            if any(term in message.lower() for term in ["halal", "vegan", "vegetarian", "veggie"])
        ),
        "",
    )
    if not previous_dietary_query:
        return user_content
    if "halal" in previous_dietary_query.lower():
        return "show halal options across all dining halls for dinner grouped by dining hall"
    if "vegan" in previous_dietary_query.lower():
        return "show vegan options across all dining halls for dinner grouped by dining hall"
    if "vegetarian" in previous_dietary_query.lower() or "veggie" in previous_dietary_query.lower():
        return "show vegetarian options across all dining halls for dinner grouped by dining hall"
    return user_content


def tokenize(content: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", content.lower()))


def asks_for_unsupported_date_range(content: str) -> bool:
    tokens = tokenize(content)
    if tokens & UNSUPPORTED_DATE_TERMS:
        return True
    return bool(re.search(r"\bnext\s+(week|mon|monday|tue|tuesday|wed|wednesday|thu|thursday|fri|friday|sat|saturday|sun|sunday)\b", content.lower()))


def build_unsupported_date_range_response(content: str, menu_date: str) -> str | None:
    if not asks_for_unsupported_date_range(content):
        return None
    return (
        f"I only have today's Berkeley Dining menu loaded for {menu_date}. "
        "I can't answer weekly, future, or past menu requests yet. "
        "Ask for today's options or a specific item from today's menu."
    )


def requested_dietary_filters(content: str) -> list[str]:
    q = content.lower()
    filters: list[str] = []
    if "halal" in q:
        filters.append("halal")
    if "vegan" in q:
        filters.append("vegan")
    if "vegetarian" in q or "veggie" in q:
        filters.append("vegetarian")
    return filters


def is_dietary_options_query(content: str) -> bool:
    filters = requested_dietary_filters(content)
    if not filters:
        return False
    q = content.lower()
    return bool(
        tokenize(content) & DIETARY_OPTION_TERMS
        or re.search(r"\b(what(?:'s| is)?|whats)\b.*\b(at|for|today|tonight|brunch|lunch|dinner)\b", q)
    )


def retrieval_limit(content: str) -> int:
    return 24 if is_dietary_options_query(content) else 8


def doc_matches_dietary_filters(doc: Any, filters: list[str]) -> bool:
    metadata = getattr(doc, "metadata", {}) or {}
    for requested_filter in filters:
        if requested_filter == "halal" and metadata.get("halal_status") != "HALAL":
            return False
        if requested_filter == "vegan" and metadata.get("is_vegan") is not True:
            return False
        if requested_filter == "vegetarian" and metadata.get("is_vegetarian") is not True:
            return False
    return True


def dietary_filter_label(filters: list[str]) -> str:
    labels = {"halal": "halal", "vegan": "vegan", "vegetarian": "vegetarian"}
    return " and ".join(labels[requested_filter] for requested_filter in filters)


def extract_doc_name(doc: Any) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    short_name = str(metadata.get("short_name") or "").strip()
    if short_name:
        return short_name
    match = re.search(r"^Item:\s*(.+)$", getattr(doc, "page_content", ""), re.MULTILINE)
    return match.group(1).strip() if match else "Unnamed item"


def format_dietary_option_line(doc: Any, filters: list[str]) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    hall = str(metadata.get("dining_hall") or "Unknown dining hall").strip()
    meal = str(metadata.get("meal_period") or "").strip()
    name = extract_doc_name(doc)
    details: list[str] = []
    if meal:
        details.append(meal)
    if "halal" in filters and metadata.get("contains_shellfish") is True:
        details.append("contains shellfish")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"- {hall}: {name}{suffix}"


def unique_docs_by_item(docs: list[Any]) -> list[Any]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Any] = []
    for doc in docs:
        metadata = getattr(doc, "metadata", {}) or {}
        key = (
            str(metadata.get("dining_hall") or ""),
            str(metadata.get("meal_period") or ""),
            extract_doc_name(doc),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


def build_dietary_options_response(
    content: str,
    chunks: list[Any],
    menu_date: str,
    include_halal_disclaimer: bool = False,
) -> tuple[str, bool] | None:
    if not is_dietary_options_query(content):
        return None

    filters = requested_dietary_filters(content)
    matching_docs = [
        doc for doc in unique_docs_by_item(chunks) if doc_matches_dietary_filters(doc, filters)
    ]
    label = dietary_filter_label(filters)
    lines: list[str] = []
    disclaimer_used = include_halal_disclaimer and "halal" in filters
    if disclaimer_used:
        lines.append(HALAL_DISCLAIMER)

    if not matching_docs:
        lines.append(f"I couldn't find any {label} options in today's menu for {menu_date}.")
        lines.append("Try a dining hall, meal period, or item name to narrow the search.")
        return "\n".join(lines), disclaimer_used

    matching_docs = sorted(
        matching_docs,
        key=lambda doc: (
            str((getattr(doc, "metadata", {}) or {}).get("dining_hall") or ""),
            str((getattr(doc, "metadata", {}) or {}).get("meal_period") or ""),
            extract_doc_name(doc),
        ),
    )
    lines.append(f"Today's {label} options I found for {menu_date}:")
    lines.extend(format_dietary_option_line(doc, filters) for doc in matching_docs)
    return "\n".join(lines), disclaimer_used


def build_no_context_response(
    content: str,
    menu_date: str,
    include_halal_disclaimer: bool = False,
) -> tuple[str, bool]:
    lines: list[str] = []
    disclaimer_used = include_halal_disclaimer and is_halal_query(content)
    if disclaimer_used:
        lines.append(HALAL_DISCLAIMER)
    lines.append(
        f"I couldn't find matching items in today's Berkeley Dining menu for {menu_date}. "
        "Try a dining hall, meal period, or exact menu item."
    )
    return "\n".join(lines), disclaimer_used


def is_refresh_request(content: str) -> bool:
    q = content.lower()
    return "refresh" in q or "reload" in q or "update menu" in q


async def send_static_response(
    user_content: str,
    assistant_content: str,
    history: list[dict[str, str]],
    disclaimer_used: bool = False,
    guardrail: str | None = None,
) -> None:
    msg = cl.Message(content=assistant_content)
    await msg.send()
    cl.user_session.set("history", append_history(history, user_content, msg.content))
    if disclaimer_used:
        cl.user_session.set("halal_disclaimer_shown", True)
    capture_event(
        "response_sent",
        {
            "response_length": len(msg.content),
            "tool_call_count": 0,
            "halal_disclaimer_shown": bool(disclaimer_used),
            "deterministic_response": True,
            "guardrail": guardrail,
        },
    )


def create_completion(openai_client: Any, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None):
    kwargs: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
    return openai_client.chat.completions.create(**kwargs)


async def stream_completion(response: Any, msg: Any) -> list[dict[str, str]]:
    tool_calls: dict[int, dict[str, str]] = {}
    for chunk in response:
        if not getattr(chunk, "choices", None):
            continue
        delta = getattr(chunk.choices[0], "delta", None)
        if delta is None:
            continue

        content = getattr(delta, "content", None)
        if content:
            await msg.stream_token(content)

        for call in getattr(delta, "tool_calls", None) or []:
            index = getattr(call, "index", 0)
            entry = tool_calls.setdefault(index, {"name": "", "arguments": ""})
            function = getattr(call, "function", None)
            if function is None:
                continue
            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", None)
            if name:
                entry["name"] += name
            if arguments:
                entry["arguments"] += arguments

    return [tool_calls[index] for index in sorted(tool_calls)]


def run_tool_calls(tool_calls: list[dict[str, str]]) -> None:
    global db
    for tool_call in tool_calls:
        name = tool_call["name"]
        arguments = json.loads(tool_call["arguments"] or "{}")
        db = handle_tool_call(name, arguments, db, cache=cache)


@cl.on_chat_start
async def on_start():
    cl.user_session.set("history", [])
    cl.user_session.set("halal_disclaimer_shown", False)
    capture_event("session_started")


@cl.on_message
async def on_message(message):
    global db
    user_content = message.content
    menu_date = str(date.today())
    history = cl.user_session.get("history", [])
    effective_user_content = resolve_followup_content(user_content, history)
    disclaimer_needed = should_show_halal_disclaimer(effective_user_content)
    capture_event(
        "message_received",
        {
            "message_length": len(user_content),
            "halal_query": is_halal_query(effective_user_content),
            "history_length": len(history),
        },
    )

    pre_context_response = build_pre_context_response(effective_user_content)
    if pre_context_response:
        await send_static_response(
            user_content,
            pre_context_response.content,
            history,
            disclaimer_used=pre_context_response.disclaimer_used,
            guardrail=pre_context_response.guardrail,
        )
        return

    unsupported_date_response = build_unsupported_date_range_response(effective_user_content, menu_date)
    if unsupported_date_response:
        await send_static_response(
            user_content,
            unsupported_date_response,
            history,
            guardrail="unsupported_date_range",
        )
        return

    active_db = ensure_fresh_menu(menu_date)
    all_docs = list_documents(active_db)

    menu_response = build_menu_response(
        effective_user_content,
        all_docs,
        menu_date,
        include_halal_disclaimer=disclaimer_needed,
    )
    if menu_response:
        await send_static_response(
            user_content,
            menu_response.content,
            history,
            disclaimer_used=menu_response.disclaimer_used,
            guardrail=menu_response.guardrail,
        )
        return

    chunks = retrieve(active_db, effective_user_content, n_results=retrieval_limit(effective_user_content))

    if is_dietary_options_query(effective_user_content):
        menu_response = build_menu_response(
            effective_user_content,
            chunks,
            menu_date,
            include_halal_disclaimer=disclaimer_needed,
        )
        if menu_response:
            await send_static_response(
                user_content,
                menu_response.content,
                history,
                disclaimer_used=menu_response.disclaimer_used,
                guardrail=menu_response.guardrail,
            )
            return

    dietary_options_response = build_dietary_options_response(
        effective_user_content,
        chunks,
        menu_date,
        include_halal_disclaimer=disclaimer_needed,
    )
    if dietary_options_response:
        response_content, disclaimer_used = dietary_options_response
        await send_static_response(
            user_content,
            response_content,
            history,
            disclaimer_used=disclaimer_used,
            guardrail="dietary_options",
        )
        return

    if not chunks and not is_refresh_request(effective_user_content):
        response_content, disclaimer_used = build_no_context_response(
            effective_user_content,
            menu_date,
            include_halal_disclaimer=disclaimer_needed,
        )
        await send_static_response(
            user_content,
            response_content,
            history,
            disclaimer_used=disclaimer_used,
            guardrail="empty_retrieval",
        )
        return

    context = build_context(chunks)
    messages = build_messages(
        effective_user_content,
        context,
        history,
        menu_date=menu_date,
        include_halal_disclaimer_instruction=disclaimer_needed,
    )

    openai_client = get_openai_client()
    response = create_completion(openai_client, messages, tools=MCP_TOOLS)
    msg = cl.Message(content="")
    tool_calls = await stream_completion(response, msg)

    if tool_calls:
        run_tool_calls(tool_calls)
        refreshed_chunks = retrieve(db, effective_user_content)
        refreshed_context = build_context(refreshed_chunks)
        refreshed_messages = build_messages(
            effective_user_content,
            refreshed_context,
            history,
            menu_date=menu_date,
            include_halal_disclaimer_instruction=disclaimer_needed,
        )
        refreshed_messages.append(
            {"role": "system", "content": "The menu data was refreshed for this request."}
        )
        refreshed_response = create_completion(openai_client, refreshed_messages, tools=None)
        await stream_completion(refreshed_response, msg)

    await msg.send()

    cl.user_session.set("history", append_history(history, user_content, msg.content))
    if disclaimer_needed:
        cl.user_session.set("halal_disclaimer_shown", True)
    capture_event(
        "response_sent",
        {
            "response_length": len(msg.content),
            "tool_call_count": len(tool_calls),
            "halal_disclaimer_shown": bool(disclaimer_needed),
        },
    )


if os.getenv("BEARGRUB_AUTO_INIT", "1") == "1":
    configure_posthog()
    try:
        init()
    except Exception:
        logger.exception("BearGrub startup initialization failed")
        db = embed_menu([])

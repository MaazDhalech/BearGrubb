from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

from classifier import classify_all, load_cache
from config import OPENAI_MODEL, POSTHOG_API_KEY
from mcp_tools import MCP_TOOLS, handle_tool_call
from prompts import SYSTEM_PROMPT
from rag import embed_menu, is_stale, retrieve
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


def configure_posthog() -> None:
    if posthog is not None and POSTHOG_API_KEY:
        posthog.api_key = POSTHOG_API_KEY


def get_distinct_id() -> str | None:
    distinct_id = cl.user_session.get("id")
    return str(distinct_id) if distinct_id else None


def capture_event(event: str, properties: dict[str, Any] | None = None) -> bool:
    if posthog is None:
        return False
    distinct_id = get_distinct_id()
    if not distinct_id:
        logger.info("Skipping PostHog event %s because Chainlit session id is unavailable", event)
        return False
    safe_properties = sanitize_event_properties(properties or {})
    posthog.capture(distinct_id, event, safe_properties)
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
    disclaimer_needed = should_show_halal_disclaimer(user_content)
    capture_event(
        "message_received",
        {
            "message_length": len(user_content),
            "halal_query": is_halal_query(user_content),
            "history_length": len(history),
        },
    )

    active_db = ensure_fresh_menu(menu_date)
    chunks = retrieve(active_db, user_content)
    context = build_context(chunks)
    messages = build_messages(
        user_content,
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
        refreshed_chunks = retrieve(db, user_content)
        refreshed_context = build_context(refreshed_chunks)
        refreshed_messages = build_messages(
            user_content,
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

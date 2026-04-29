from __future__ import annotations

import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["BEARGRUB_AUTO_INIT"] = "0"
os.environ["BEARGRUB_TEST_MODE"] = "1"

import app
import rag


def reload_app():
    os.environ["BEARGRUB_AUTO_INIT"] = "0"
    os.environ["BEARGRUB_TEST_MODE"] = "1"
    return importlib.reload(app)


def chunk(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=None),
            )
        ]
    )


class PosthogTests(unittest.TestCase):
    def setUp(self):
        self.app = reload_app()
        self.app.cl.user_session.values.clear()

    def test_capture_event_uses_chainlit_session_id(self):
        fake_posthog = Mock()
        self.app.posthog = fake_posthog
        self.app.cl.user_session.set("id", "session-123")

        captured = self.app.capture_event("session_started", {"message_length": 12})

        self.assertTrue(captured)
        fake_posthog.capture.assert_called_once_with(
            "session-123",
            "session_started",
            {"message_length": 12},
        )

    def test_capture_event_skips_without_session_id_instead_of_using_anonymous(self):
        fake_posthog = Mock()
        self.app.posthog = fake_posthog

        captured = self.app.capture_event("session_started")

        self.assertFalse(captured)
        fake_posthog.capture.assert_not_called()

    def test_sanitize_event_properties_strips_sensitive_text_fields(self):
        sanitized = self.app.sanitize_event_properties(
            {
                "message": "what did I ask?",
                "query": "is chicken halal?",
                "response": "answer text",
                "context": "retrieved menu context",
                "history": ["old"],
                "message_length": 18,
                "halal_query": True,
                "nested": {"raw": "ignored"},
            }
        )

        self.assertEqual(sanitized, {"message_length": 18, "halal_query": True})

    def test_on_start_captures_session_started(self):
        self.app.cl.user_session.set("id", "session-456")
        self.app.posthog = Mock()

        asyncio.run(self.app.on_start())

        self.app.posthog.capture.assert_called_once_with("session-456", "session_started", {})

    def test_on_message_captures_only_safe_message_and_response_metadata(self):
        self.app.cl.user_session.set("id", "session-789")
        self.app.posthog = Mock()
        menu_doc = rag.MenuDocument("Item: Halal Chicken", {"date": "2026-04-29"})
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=Mock(return_value=[chunk("Answer text")]))
            )
        )

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(return_value=[menu_doc])),
            patch.object(self.app, "get_openai_client", Mock(return_value=fake_client)),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="Is chicken halal?")))

        calls = self.app.posthog.capture.call_args_list
        self.assertEqual([call.args[1] for call in calls], ["message_received", "response_sent"])
        for call in calls:
            properties = call.args[2]
            self.assertNotIn("message", properties)
            self.assertNotIn("query", properties)
            self.assertNotIn("response", properties)
            self.assertNotIn("context", properties)
        self.assertEqual(calls[0].args[2]["message_length"], len("Is chicken halal?"))
        self.assertTrue(calls[0].args[2]["halal_query"])
        self.assertEqual(calls[1].args[2]["response_length"], len("Answer text"))


if __name__ == "__main__":
    unittest.main()

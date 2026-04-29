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

import app
import rag


def reload_app():
    os.environ["BEARGRUB_AUTO_INIT"] = "0"
    return importlib.reload(app)


def chunk(content: str | None = None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ]
    )


def tool_call(name: str | None = None, arguments: str | None = None, index: int = 0):
    return SimpleNamespace(
        index=index,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeCompletionClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create),
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = reload_app()
        self.app.cl.user_session.values.clear()

    def test_auto_init_is_disabled_for_tests(self):
        self.assertIsNone(self.app.db)
        self.assertEqual(self.app.cache, {})

    def test_on_start_resets_session_state(self):
        self.app.cl.user_session.set("history", [{"role": "user", "content": "old"}])
        self.app.cl.user_session.set("halal_disclaimer_shown", True)

        asyncio.run(self.app.on_start())

        self.assertEqual(self.app.cl.user_session.get("history"), [])
        self.assertFalse(self.app.cl.user_session.get("halal_disclaimer_shown"))

    def test_build_messages_trims_history_and_adds_context(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
            for i in range(14)
        ]

        messages = self.app.build_messages(
            "What is halal?",
            "Item: Test",
            history,
            menu_date="2026-04-29",
            include_halal_disclaimer_instruction=True,
        )

        self.assertIn("Today's date: 2026-04-29", messages[0]["content"])
        self.assertEqual(messages[1], {"role": "system", "content": "Menu context:\nItem: Test"})
        self.assertIn("first halal query", messages[2]["content"])
        self.assertEqual(len([m for m in messages if m["content"].startswith("message")]), 10)
        self.assertEqual(messages[-1], {"role": "user", "content": "What is halal?"})

    def test_append_history_keeps_last_ten_messages(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
            for i in range(10)
        ]

        updated = self.app.append_history(history, "new user", "new assistant")

        self.assertEqual(len(updated), 10)
        self.assertEqual(updated[0]["content"], "message 2")
        self.assertEqual(updated[-2:], [
            {"role": "user", "content": "new user"},
            {"role": "assistant", "content": "new assistant"},
        ])

    def test_ensure_fresh_menu_refreshes_stale_db(self):
        existing_db = object()
        refreshed_db = object()
        self.app.db = existing_db

        with (
            patch.object(self.app, "is_stale", Mock(return_value=True)) as stale_mock,
            patch.object(self.app, "refresh_menu", Mock(return_value=refreshed_db)) as refresh_mock,
        ):
            result = self.app.ensure_fresh_menu("2026-04-29")

        self.assertIs(result, refreshed_db)
        self.assertIs(self.app.db, refreshed_db)
        stale_mock.assert_called_once_with(existing_db)
        refresh_mock.assert_called_once_with("2026-04-29", existing_db=existing_db)

    def test_on_message_streams_response_and_updates_history(self):
        menu_doc = rag.MenuDocument("Item: Beet Red", {"date": "2026-04-29"})
        fake_client = FakeCompletionClient([[chunk("Beet"), chunk(" Red is vegan.")]])

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(return_value=[menu_doc])) as retrieve_mock,
            patch.object(self.app, "get_openai_client", Mock(return_value=fake_client)),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="What is vegan?")))

        retrieve_mock.assert_called_once()
        history = self.app.cl.user_session.get("history")
        self.assertEqual(history[-2]["content"], "What is vegan?")
        self.assertEqual(history[-1]["content"], "Beet Red is vegan.")
        self.assertNotIn("tools", fake_client.calls[-1] if len(fake_client.calls) > 1 else {})

    def test_on_message_sets_halal_disclaimer_flag_once(self):
        menu_doc = rag.MenuDocument("Item: Halal Chicken", {"date": "2026-04-29"})
        fake_client = FakeCompletionClient([[chunk("Disclaimer. Halal Chicken is halal.")]])

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(return_value=[menu_doc])),
            patch.object(self.app, "get_openai_client", Mock(return_value=fake_client)),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="Is chicken halal?")))

        self.assertTrue(self.app.cl.user_session.get("halal_disclaimer_shown"))
        first_call_messages = fake_client.calls[0]["messages"]
        self.assertTrue(any("first halal query" in m["content"] for m in first_call_messages))

    def test_stream_completion_collects_fragmented_tool_call_arguments(self):
        msg = self.app.cl.Message(content="")
        response = [
            chunk(tool_calls=[tool_call(name="get_menu", arguments='{"dining_hall": "ALL"', index=0)]),
            chunk(tool_calls=[tool_call(arguments=', "date": "2026-04-29"}', index=0)]),
        ]

        calls = asyncio.run(self.app.stream_completion(response, msg))

        self.assertEqual(
            calls,
            [{"name": "get_menu", "arguments": '{"dining_hall": "ALL", "date": "2026-04-29"}'}],
        )

    def test_on_message_handles_tool_call_and_retrieves_again_after_refresh(self):
        initial_doc = rag.MenuDocument("Item: Old", {"date": "2026-04-29"})
        refreshed_doc = rag.MenuDocument("Item: New", {"date": "2026-04-29"})
        fake_client = FakeCompletionClient(
            [
                [
                    chunk(
                        tool_calls=[
                            tool_call(
                                name="get_menu",
                                arguments='{"dining_hall": "ALL", "date": "2026-04-29"}',
                            )
                        ]
                    )
                ],
                [chunk("Menu refreshed.")],
            ]
        )
        refreshed_db = object()

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(side_effect=[[initial_doc], [refreshed_doc]])) as retrieve_mock,
            patch.object(self.app, "handle_tool_call", Mock(return_value=refreshed_db)) as tool_mock,
            patch.object(self.app, "get_openai_client", Mock(return_value=fake_client)),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="Refresh the menu")))

        self.assertEqual(retrieve_mock.call_count, 2)
        tool_mock.assert_called_once()
        self.assertIs(self.app.db, refreshed_db)
        self.assertEqual(self.app.cl.user_session.get("history")[-1]["content"], "Menu refreshed.")
        self.assertEqual(len(fake_client.calls), 2)
        self.assertNotIn("tools", fake_client.calls[1])


if __name__ == "__main__":
    unittest.main()

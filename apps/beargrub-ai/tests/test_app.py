from __future__ import annotations

import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

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


def menu_doc(name: str, **metadata):
    base_metadata = {
        "date": "2026-04-29",
        "dining_hall": "Crossroads",
        "meal_period": "Dinner",
        "short_name": name,
        "halal_status": "HALAL",
        "is_vegan": False,
        "is_vegetarian": False,
        "contains_shellfish": False,
    }
    base_metadata.update(metadata)
    return rag.MenuDocument(f"Item: {name}", base_metadata)


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

    def test_on_message_rejects_week_query_without_model_call(self):
        ensure_mock = Mock()
        retrieve_mock = Mock()
        openai_mock = Mock()

        with (
            patch.object(self.app, "ensure_fresh_menu", ensure_mock),
            patch.object(self.app, "retrieve", retrieve_mock),
            patch.object(self.app, "get_openai_client", openai_mock),
        ):
            asyncio.run(
                self.app.on_message(
                    SimpleNamespace(content="what are the halal meal options for this wek?")
                )
            )

        ensure_mock.assert_not_called()
        retrieve_mock.assert_not_called()
        openai_mock.assert_not_called()
        response = self.app.cl.user_session.get("history")[-1]["content"]
        self.assertIn("today's Berkeley Dining menu", response)
        self.assertIn("weekly", response)
        self.assertFalse(self.app.cl.user_session.get("halal_disclaimer_shown", False))

    def test_on_message_dietary_options_excludes_non_matching_halal_statuses(self):
        docs = [
            menu_doc("Halal Rosemary Chicken"),
            menu_doc(
                "Turkey Sandwich",
                dining_hall="Foothill",
                halal_status="NOT_HALAL",
            ),
            menu_doc(
                "Vegan Lentil Soup",
                dining_hall="Cafe 3",
                meal_period="Lunch",
                is_vegan=True,
                is_vegetarian=True,
            ),
        ]
        openai_mock = Mock()

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(return_value=docs)) as retrieve_mock,
            patch.object(self.app, "get_openai_client", openai_mock),
        ):
            asyncio.run(
                self.app.on_message(
                    SimpleNamespace(content="what halal options are available today?")
                )
            )

        retrieve_mock.assert_called_once_with(
            ANY,
            "what halal options are available today?",
            n_results=24,
        )
        openai_mock.assert_not_called()
        response = self.app.cl.user_session.get("history")[-1]["content"]
        self.assertIn("classifications are ingredient-based", response)
        self.assertIn("Halal Rosemary Chicken", response)
        self.assertNotIn("Turkey Sandwich", response)
        self.assertNotIn("Vegan Lentil Soup", response)
        self.assertNotIn("NOT_HALAL", response)
        self.assertTrue(self.app.cl.user_session.get("halal_disclaimer_shown"))

    def test_on_message_formats_retrieved_halal_lunch_options_deterministically(self):
        docs = [
            menu_doc(
                "Halal Blue Sage Beef Burger",
                dining_hall="Clark Kerr",
                meal_period="Lunch",
                ingredients="Beef HALAL",
                calories=933.1,
                serving_size=8.51,
                serving_size_unit="oz",
                protein=56.94,
            ),
            menu_doc(
                "Braised Mung Bean",
                dining_hall="Clark Kerr",
                meal_period="Lunch",
                is_vegan=True,
                is_vegetarian=True,
                calories=126,
                serving_size=4.16,
                serving_size_unit="oz",
            ),
            menu_doc(
                "Southwestern Corn Chowder",
                dining_hall="Clark Kerr",
                meal_period="Lunch",
                category="Soup",
                is_vegetarian=True,
                calories=167,
                serving_size=8,
                serving_size_unit="oz",
            ),
        ]
        openai_mock = Mock()

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "list_documents", Mock(return_value=[])),
            patch.object(self.app, "retrieve", Mock(return_value=docs)) as retrieve_mock,
            patch.object(self.app, "get_openai_client", openai_mock),
        ):
            asyncio.run(
                self.app.on_message(
                    SimpleNamespace(content="whats halal for lunch today at clark kerr")
                )
            )

        retrieve_mock.assert_called_once_with(
            ANY,
            "whats halal for lunch today at clark kerr",
            n_results=24,
        )
        openai_mock.assert_not_called()
        response = self.app.cl.user_session.get("history")[-1]["content"]
        self.assertIn("Here are the halal options at Clark Kerr for lunch:", response)
        self.assertIn("Proteins:", response)
        self.assertIn("✅ Halal Blue Sage Beef Burger — 933 cal per 8.51oz serving", response)
        self.assertIn("Vegan/Vegetarian (halal):", response)
        self.assertIn("Braised Mung Bean (vegan) — 126 cal per 4.16oz serving", response)
        self.assertNotIn("Serving Size:", response)
        self.assertNotIn("Southwestern Corn Chowder", response)

    def test_on_message_resolves_sort_by_hall_followup_to_previous_halal_query(self):
        docs = [
            menu_doc("Halal Rosemary Chicken"),
            menu_doc("Halal Ground Beef", dining_hall="Clark Kerr"),
        ]
        self.app.cl.user_session.set(
            "history",
            [
                {"role": "user", "content": "give me halal meal options for today"},
                {"role": "assistant", "content": "Halal options across all dining halls tonight:"},
            ],
        )
        openai_mock = Mock()

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "list_documents", Mock(return_value=docs)),
            patch.object(self.app, "get_openai_client", openai_mock),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="sort by dining hall")))

        openai_mock.assert_not_called()
        response = self.app.cl.user_session.get("history")[-1]["content"]
        self.assertIn("Halal options across all dining halls tonight:", response)
        self.assertIn("Crossroads:", response)
        self.assertIn("Clark Kerr:", response)

    def test_on_message_empty_retrieval_returns_no_context_without_model_call(self):
        openai_mock = Mock()

        with (
            patch.object(self.app, "ensure_fresh_menu", Mock(return_value=object())),
            patch.object(self.app, "retrieve", Mock(return_value=[])),
            patch.object(self.app, "get_openai_client", openai_mock),
        ):
            asyncio.run(self.app.on_message(SimpleNamespace(content="Tell me about pizza.")))

        openai_mock.assert_not_called()
        response = self.app.cl.user_session.get("history")[-1]["content"]
        self.assertIn("couldn't find matching items", response)
        self.assertIn("today's Berkeley Dining menu", response)

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

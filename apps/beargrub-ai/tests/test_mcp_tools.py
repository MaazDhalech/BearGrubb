from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import mcp_tools


class McpToolsTests(unittest.TestCase):
    def test_tool_schema_exposes_get_menu_with_required_args(self):
        tool = mcp_tools.MCP_TOOLS[0]

        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["function"]["name"], "get_menu")
        self.assertEqual(
            tool["function"]["parameters"]["properties"]["dining_hall"]["enum"],
            ["Crossroads", "Cafe 3", "Clark Kerr", "Foothill", "ALL"],
        )
        self.assertEqual(tool["function"]["parameters"]["required"], ["dining_hall", "date"])

    def test_handle_get_menu_fetches_classifies_and_embeds(self):
        existing_db = object()
        new_db = object()
        raw_items = [{"short_name": "Beet Red", "ingredients": "Beet Red"}]
        classified_items = [{"short_name": "Beet Red", "halal_status": "HALAL"}]
        cache = {}

        with (
            patch.object(mcp_tools, "fetch_all", Mock(return_value=raw_items)) as fetch_mock,
            patch.object(mcp_tools, "classify_all", Mock(return_value=classified_items)) as classify_mock,
            patch.object(mcp_tools, "embed_menu", Mock(return_value=new_db)) as embed_mock,
        ):
            result = mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "Cafe 3", "date": "2026-04-27"},
                existing_db,
                cache=cache,
            )

        self.assertIs(result, new_db)
        fetch_mock.assert_called_once_with("2026-04-27", hall="Cafe 3")
        classify_mock.assert_called_once_with(raw_items, cache=cache)
        embed_mock.assert_called_once_with(classified_items)

    def test_handle_get_menu_keeps_existing_db_when_fetch_returns_empty(self):
        existing_db = object()

        with (
            patch.object(mcp_tools, "fetch_all", Mock(return_value=[])) as fetch_mock,
            patch.object(mcp_tools, "classify_all", Mock()) as classify_mock,
            patch.object(mcp_tools, "embed_menu", Mock()) as embed_mock,
        ):
            result = mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "ALL", "date": "2026-04-27"},
                existing_db,
            )

        self.assertIs(result, existing_db)
        fetch_mock.assert_called_once_with("2026-04-27", hall="ALL")
        classify_mock.assert_not_called()
        embed_mock.assert_not_called()

    def test_handle_tool_call_rejects_unknown_tools(self):
        with self.assertRaisesRegex(ValueError, "Unsupported MCP tool"):
            mcp_tools.handle_tool_call("delete_menu", {"dining_hall": "ALL", "date": "2026-04-27"}, object())

    def test_handle_get_menu_validates_args(self):
        with self.assertRaisesRegex(ValueError, "Unsupported dining hall"):
            mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "Unit 3", "date": "2026-04-27"},
                object(),
            )

        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "ALL", "date": "04/27/2026"},
                object(),
            )


if __name__ == "__main__":
    unittest.main()

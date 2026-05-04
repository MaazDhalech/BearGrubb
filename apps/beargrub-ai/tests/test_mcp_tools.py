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

    def test_handle_get_menu_refreshes_store_through_refresh_boundary(self):
        existing_db = object()
        new_db = object()
        cache = {}
        summary = Mock(success=True)

        with patch.object(
            mcp_tools,
            "refresh_menu_store",
            Mock(return_value=Mock(store=new_db, summary=summary)),
        ) as refresh_mock:
            result = mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "Cafe 3", "date": "2026-04-27"},
                existing_db,
                cache=cache,
            )

        self.assertIs(result, new_db)
        refresh_mock.assert_called_once_with(
            menu_date="2026-04-27",
            hall="Cafe 3",
            existing_db=existing_db,
            cache=cache,
            build_empty_store_on_total_failure=False,
            persist_snapshot=True,
        )

    def test_handle_get_menu_keeps_existing_db_when_fetch_returns_empty(self):
        existing_db = object()
        summary = Mock(success=False)

        with patch.object(
            mcp_tools,
            "refresh_menu_store",
            Mock(return_value=Mock(store=existing_db, summary=summary)),
        ) as refresh_mock:
            result = mcp_tools.handle_tool_call(
                "get_menu",
                {"dining_hall": "ALL", "date": "2026-04-27"},
                existing_db,
            )

        self.assertIs(result, existing_db)
        refresh_mock.assert_called_once()

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

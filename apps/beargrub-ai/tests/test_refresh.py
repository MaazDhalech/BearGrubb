from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import refresh


def item(name: str, hall: str = "Crossroads", status: str = "HALAL") -> dict[str, object]:
    return {
        "short_name": name,
        "dining_hall": hall,
        "ingredients": name,
        "halal_status": status,
    }


class RefreshTests(unittest.TestCase):
    def test_refresh_all_halls_fetches_classifies_and_embeds_with_summary(self):
        raw_by_hall = {
            "Crossroads": [item("Halal Chicken", "Crossroads")],
            "Cafe 3": [item("Vegan Tofu", "Cafe 3")],
            "Clark Kerr": [item("Pork Loin", "Clark Kerr", "NOT_HALAL")],
            "Foothill": [item("Ambiguous Soup", "Foothill", "UNCERTAIN")],
        }

        def fetcher(menu_date, hall):
            return raw_by_hall[hall]

        def classifier(raw_items, cache=None):
            return list(raw_items)

        embedded_store = object()
        embedder = Mock(return_value=embedded_store)

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            fetcher=fetcher,
            classifier=classifier,
            embedder=embedder,
        )

        self.assertIs(result.store, embedded_store)
        self.assertTrue(result.summary.success)
        self.assertEqual(result.summary.raw_item_count, 4)
        self.assertEqual(result.summary.classification_counts["HALAL"], 2)
        self.assertEqual(result.summary.classification_counts["NOT_HALAL"], 1)
        self.assertEqual(result.summary.classification_counts["UNCERTAIN"], 1)
        self.assertEqual(result.summary.failed_halls, [])
        embedder.assert_called_once()

    def test_successful_refresh_can_persist_snapshot(self):
        storage_backend = Mock()
        storage_backend.save_snapshot.return_value = Mock(snapshot_dir="/tmp/menu-snapshot")

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            hall="Crossroads",
            fetcher=Mock(return_value=[item("Halal Chicken")]),
            classifier=lambda raw_items, cache=None: list(raw_items),
            embedder=Mock(return_value=object()),
            persist_snapshot=True,
            storage_backend=storage_backend,
        )

        self.assertTrue(result.summary.success)
        self.assertTrue(result.summary.snapshot_saved)
        self.assertEqual(result.summary.snapshot_path, "/tmp/menu-snapshot")
        storage_backend.save_snapshot.assert_called_once()

    def test_snapshot_failure_is_reported_without_discarding_embedded_store(self):
        embedded_store = object()
        storage_backend = Mock()
        storage_backend.save_snapshot.side_effect = OSError("disk full")

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            hall="Crossroads",
            fetcher=Mock(return_value=[item("Halal Chicken")]),
            classifier=lambda raw_items, cache=None: list(raw_items),
            embedder=Mock(return_value=embedded_store),
            persist_snapshot=True,
            storage_backend=storage_backend,
        )

        self.assertIs(result.store, embedded_store)
        self.assertTrue(result.summary.success)
        self.assertFalse(result.summary.snapshot_saved)
        self.assertTrue(any("snapshot persistence failed" in error for error in result.summary.errors))

    def test_partial_hall_failure_still_embeds_available_items(self):
        def fetcher(menu_date, hall):
            if hall == "Cafe 3":
                return []
            if hall == "Foothill":
                raise RuntimeError("network timeout")
            return [item(f"{hall} Item", hall)]

        embedded_store = object()

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            fetcher=fetcher,
            classifier=lambda raw_items, cache=None: list(raw_items),
            embedder=Mock(return_value=embedded_store),
        )

        self.assertIs(result.store, embedded_store)
        self.assertTrue(result.summary.success)
        self.assertEqual(result.summary.fetched_halls, ["Crossroads", "Clark Kerr"])
        self.assertEqual(result.summary.failed_halls, ["Cafe 3", "Foothill"])
        self.assertTrue(any("fetched 0 items" in error for error in result.summary.errors))
        self.assertTrue(any("network timeout" in error for error in result.summary.errors))

    def test_total_empty_refresh_keeps_existing_store_and_skips_classify_embed(self):
        existing_store = object()
        classifier = Mock()
        embedder = Mock()

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            existing_db=existing_store,
            fetcher=Mock(return_value=[]),
            classifier=classifier,
            embedder=embedder,
        )

        self.assertIs(result.store, existing_store)
        self.assertFalse(result.summary.success)
        self.assertTrue(result.summary.total_failure)
        self.assertTrue(result.summary.kept_existing_store)
        classifier.assert_not_called()
        embedder.assert_not_called()

    def test_classification_failure_keeps_existing_store(self):
        existing_store = object()
        embedder = Mock()

        def classifier(raw_items, cache=None):
            raise RuntimeError("classifier unavailable")

        result = refresh.refresh_menu_store(
            menu_date="2026-04-29",
            existing_db=existing_store,
            hall="Crossroads",
            fetcher=Mock(return_value=[item("Soup")]),
            classifier=classifier,
            embedder=embedder,
        )

        self.assertIs(result.store, existing_store)
        self.assertFalse(result.summary.success)
        self.assertTrue(result.summary.kept_existing_store)
        self.assertIn("classification failed", result.summary.errors[0])
        embedder.assert_not_called()

    def test_cli_returns_nonzero_when_refresh_totally_fails(self):
        original = refresh.refresh_menu_store
        refresh.refresh_menu_store = Mock(
            return_value=refresh.RefreshResult(
                store=None,
                summary=refresh.RefreshSummary(
                    menu_date="2026-04-29",
                    requested_hall="ALL",
                    failed_halls=["Crossroads", "Cafe 3", "Clark Kerr", "Foothill"],
                    errors=["all halls empty"],
                ),
            )
        )
        try:
            exit_code = refresh.main(["--date", "2026-04-29", "--json"])
        finally:
            refresh.refresh_menu_store = original

        self.assertEqual(exit_code, 1)

    def test_selected_halls_rejects_unknown_hall(self):
        with self.assertRaisesRegex(ValueError, "Unsupported dining hall"):
            refresh.selected_halls("Unit 3")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import storage


class StorageTests(unittest.TestCase):
    def test_save_snapshot_writes_raw_classified_summary_and_latest_pointer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = storage.LocalMenuStorage(tmpdir)

            record = store.save_snapshot(
                menu_date="2026-04-29",
                requested_hall="Cafe 3",
                raw_items=[{"short_name": "Raw Tofu"}],
                classified_items=[{"short_name": "Classified Tofu", "halal_status": "HALAL"}],
                summary={"success": True},
            )

            snapshot_dir = Path(record.snapshot_dir)
            self.assertTrue((snapshot_dir / "raw_items.json").exists())
            self.assertTrue((snapshot_dir / "classified_items.json").exists())
            self.assertTrue((snapshot_dir / "summary.json").exists())
            self.assertEqual(store.load_latest_record(), record)
            self.assertEqual(
                store.load_classified_items(),
                [{"halal_status": "HALAL", "short_name": "Classified Tofu"}],
            )

    def test_load_specific_snapshot_returns_empty_for_missing_or_corrupt_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = storage.LocalMenuStorage(tmpdir)
            missing = store.load_classified_items("2026-04-29", "Crossroads")
            self.assertEqual(missing, [])

            path = store.snapshot_dir("2026-04-29", "Crossroads")
            path.mkdir(parents=True)
            (path / "classified_items.json").write_text("{not json", encoding="utf-8")

            self.assertEqual(store.load_classified_items("2026-04-29", "Crossroads"), [])

    def test_safe_component_normalizes_hall_names_for_paths(self):
        self.assertEqual(storage.safe_component("Cafe 3"), "cafe-3")
        self.assertEqual(storage.safe_component(" Clark Kerr "), "clark-kerr")
        self.assertEqual(storage.safe_component(""), "all")


if __name__ == "__main__":
    unittest.main()

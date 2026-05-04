from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import classifier


def item(ingredients: str, **overrides):
    base = {
        "short_name": "Test Item",
        "ingredients": ingredients,
        "description": "",
        "dining_hall": "Crossroads",
        "meal_period": "Dinner",
    }
    base.update(overrides)
    return base


def fake_client(status: str, reason: str, contains_shellfish: bool = False, shellfish_note=None):
    payload = {
        "status": status,
        "reason": reason,
        "contains_shellfish": contains_shellfish,
        "shellfish_note": shellfish_note,
    }

    class _FakeClient:
        def __init__(self):
            self.calls = 0
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create),
            )

        def _create(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

    return _FakeClient()


class ClassifierTests(unittest.TestCase):
    def test_normalize_strips_punctuation_and_collapses_whitespace(self):
        self.assertEqual(classifier.normalize(" Chicken;   HALAL! "), "CHICKEN HALAL")

    def test_gpt_is_called_for_every_uncached_item(self):
        client = fake_client("HALAL", "No forbidden ingredients")
        result = classifier.classify(item("Brown Rice; Olive Oil"), cache={}, openai_client=client, cache_path=None)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result["status"], "HALAL")

    def test_cache_hit_skips_gpt(self):
        client = fake_client("HALAL", "Cached")
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = str(Path(tmpdir) / "cache.json")
            cache = {}
            classifier.classify(item("Beet Red"), cache=cache, openai_client=client, cache_path=cache_path)
            classifier.classify(item("Beet Red"), cache=cache, openai_client=client, cache_path=cache_path)
        self.assertEqual(client.calls, 1)

    def test_cache_key_normalizes_whitespace_and_punctuation(self):
        client = fake_client("HALAL", "No forbidden ingredients")
        cache = {}
        classifier.classify(item("Beet Red"), cache=cache, openai_client=client, cache_path=None)
        classifier.classify(item("Beet   Red!!!"), cache=cache, openai_client=client, cache_path=None)
        self.assertEqual(client.calls, 1)

    def test_unlabeled_meat_classified_not_halal_by_gpt(self):
        client = fake_client("NOT_HALAL", "Contains chicken not labeled halal")
        result = classifier.classify(item("Chicken Diced Dark Meat; Oil"), cache={}, openai_client=client, cache_path=None)
        self.assertEqual(result["status"], "NOT_HALAL")

    def test_halal_labeled_meat_classified_halal_by_gpt(self):
        client = fake_client("HALAL", "Meat is explicitly labeled halal")
        result = classifier.classify(item("Chicken HALAL; Oil"), cache={}, openai_client=client, cache_path=None)
        self.assertEqual(result["status"], "HALAL")

    def test_uncertain_status_passed_through(self):
        client = fake_client("UNCERTAIN", "Contains ambiguous natural flavors")
        result = classifier.classify(item("Natural flavors; sugar"), cache={}, openai_client=client, cache_path=None)
        self.assertEqual(result["status"], "UNCERTAIN")

    def test_shellfish_flag_overrides_gpt_shellfish_field(self):
        client = fake_client("HALAL", "No forbidden ingredients", contains_shellfish=False)
        result = classifier.classify(item("Oyster sauce; soy sauce"), cache={}, openai_client=client, cache_path=None)
        self.assertTrue(result["contains_shellfish"])
        self.assertEqual(result["shellfish_note"], "Oyster")

    def test_invalid_gpt_status_coerced_to_uncertain(self):
        payload = {"status": "MAYBE", "reason": "Bad response", "contains_shellfish": False}

        class _BadClient:
            chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
                    )
                )
            )

        result = classifier.classify(item("Brown Rice"), cache={}, openai_client=_BadClient(), cache_path=None)
        self.assertEqual(result["status"], "UNCERTAIN")

    def test_classify_all_enriches_items_with_halal_fields(self):
        client = fake_client("HALAL", "No forbidden ingredients")
        results = classifier.classify_all(
            [item("Beet Red", short_name="Beet Red")],
            cache={},
            openai_client=client,
            cache_path=None,
        )
        self.assertEqual(results[0]["short_name"], "Beet Red")
        self.assertIn(results[0]["halal_status"], {"HALAL", "NOT_HALAL", "UNCERTAIN"})
        self.assertIn("halal_reason", results[0])
        self.assertIn("contains_shellfish", results[0])

    def test_detect_shellfish_finds_shrimp(self):
        found, note = classifier.detect_shellfish("SHRIMP SCAMPI OIL GARLIC")
        self.assertTrue(found)
        self.assertEqual(note, "Shrimp")

    def test_detect_shellfish_returns_false_for_no_shellfish(self):
        found, note = classifier.detect_shellfish("CHICKEN RICE OIL")
        self.assertFalse(found)
        self.assertIsNone(note)


if __name__ == "__main__":
    unittest.main()

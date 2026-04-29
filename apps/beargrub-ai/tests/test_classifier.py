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


class FakeOpenAIClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create),
        )

    def _create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.payload)),
                )
            ]
        )


class ClassifierTests(unittest.TestCase):
    def classify_uncached(self, ingredients: str):
        return classifier.classify(item(ingredients), cache={}, cache_path=None)

    def test_normalize_strips_punctuation_and_collapses_whitespace(self):
        self.assertEqual(classifier.normalize(" Chicken;   HALAL! "), "CHICKEN HALAL")

    def test_halal_labeled_meat_is_halal(self):
        result = self.classify_uncached("Chicken Diced Dark Meat HALAL; Oil Cooking Blend")
        self.assertEqual(result["status"], "HALAL")

    def test_unlabeled_meat_is_not_halal(self):
        result = self.classify_uncached("Chicken Diced Dark Meat; Oil Cooking Blend")
        self.assertEqual(result["status"], "NOT_HALAL")
        self.assertIn("chicken not labeled halal", result["reason"])

    def test_alcohol_in_sauce_is_not_halal(self):
        result = self.classify_uncached("Tomato sauce; cooking wine; garlic")
        self.assertEqual(result["status"], "NOT_HALAL")
        self.assertIn("wine", result["reason"])

    def test_vanilla_extract_is_not_halal(self):
        result = self.classify_uncached("Rice; Sugar; Vanilla Extract")
        self.assertEqual(result["status"], "NOT_HALAL")
        self.assertIn("vanilla extract", result["reason"])

    def test_anchovy_paste_is_not_halal(self):
        result = self.classify_uncached("Anchovy paste; Oil")
        self.assertEqual(result["status"], "NOT_HALAL")
        self.assertIn("anchovy paste", result["reason"])

    def test_vegan_item_with_alcohol_allergen_is_uncertain(self):
        result = classifier.classify(
            item("Corn; Coconut Milk", is_vegan=True, allergens_present=["Alcohol"]),
            cache={},
            cache_path=None,
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertIn("alcohol", result["reason"].lower())

    def test_shellfish_is_halal_with_note(self):
        result = self.classify_uncached("Oyster sauce; soy sauce; sugar")
        self.assertEqual(result["status"], "HALAL")
        self.assertTrue(result["contains_shellfish"])
        self.assertEqual(result["shellfish_note"], "Oyster")

    def test_non_halal_gelatin_is_not_halal(self):
        result = self.classify_uncached("Sugar; Beef Gelatin; Food Coloring")
        self.assertEqual(result["status"], "NOT_HALAL")
        self.assertIn("gelatin", result["reason"])

    def test_halal_gelatin_is_halal(self):
        result = self.classify_uncached("Sugar; Halal Gelatin; Food Coloring")
        self.assertEqual(result["status"], "HALAL")

    def test_empty_ingredients_are_uncertain(self):
        result = self.classify_uncached("")
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(result["reason"], "No ingredient data available")

    def test_natural_flavors_are_uncertain(self):
        result = self.classify_uncached("Natural flavors (including milk); sugar")
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertIn("natural flavors", result["reason"])

    def test_single_ingredient_produce_is_halal(self):
        result = self.classify_uncached("Beet Red")
        self.assertEqual(result["status"], "HALAL")

    def test_halal_label_in_description_is_ignored(self):
        result = classifier.classify(
            item(
                "Chicken Diced Dark Meat; Oil Cooking Blend",
                description="Topping Chicken Rosemary Diced AF HALAL",
            ),
            cache={},
            cache_path=None,
        )
        self.assertEqual(result["status"], "NOT_HALAL")

    def test_gpt_fallback_is_used_for_ambiguous_base(self):
        fake_client = FakeOpenAIClient(
            {
                "status": "UNCERTAIN",
                "reason": "Contains savory base with unclear source",
                "contains_shellfish": False,
                "shellfish_note": None,
            }
        )

        result = classifier.classify(
            item("Savory base; carrots; celery"),
            cache={},
            openai_client=fake_client,
            cache_path=None,
        )

        self.assertEqual(fake_client.calls, 1)
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertIn("savory base", result["reason"])

    def test_cache_key_is_normalized_and_cache_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = str(Path(tmpdir) / "classification_cache.json")
            cache = {}

            first = classifier.classify(item("Beet Red"), cache=cache, cache_path=cache_path)
            loaded = classifier.load_cache(cache_path)
            second = classifier.classify(item("Beet   Red!!!"), cache=loaded, cache_path=cache_path)

        self.assertEqual(first["status"], "HALAL")
        self.assertEqual(second["status"], "HALAL")
        self.assertEqual(len(loaded), 1)

    def test_classify_all_enriches_items(self):
        results = classifier.classify_all(
            [item("Beet Red", short_name="Beet Red")],
            cache={},
            cache_path=None,
        )

        self.assertEqual(results[0]["short_name"], "Beet Red")
        self.assertEqual(results[0]["halal_status"], "HALAL")
        self.assertEqual(results[0]["halal_reason"], "No forbidden or ambiguous ingredients found")


if __name__ == "__main__":
    unittest.main()

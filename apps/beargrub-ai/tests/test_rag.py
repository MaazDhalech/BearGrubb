from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import rag


def menu_item(**overrides):
    base = {
        "date": str(date.today()),
        "dining_hall": "Crossroads",
        "meal_period": "Dinner",
        "category": "Entree",
        "short_name": "Halal Rosemary Chicken",
        "serving_size": 3.94,
        "serving_size_unit": "oz",
        "ingredients": "Chicken Diced Dark Meat HALAL; Oil Cooking Blend",
        "allergens_present": [],
        "halal_status": "HALAL",
        "halal_reason": "No forbidden or ambiguous ingredients found",
        "is_vegan": False,
        "is_vegetarian": False,
        "contains_shellfish": False,
        "shellfish_note": None,
        "calories": 153.21,
        "protein": 20.85,
        "fat": 7.06,
        "carbs": 0.06,
        "fiber": 0.04,
        "sodium": 300.97,
        "calories_per_oz": 38.885786802030456,
    }
    base.update(overrides)
    return base


class RagTests(unittest.TestCase):
    def test_extract_filters_combines_diet_hall_and_meal_period(self):
        filters = rag.extract_filters("Any halal dinner at cafe3?")

        self.assertEqual(
            filters,
            {
                "dining_hall": "Cafe 3",
                "halal_status": "HALAL",
                "meal_period": "Dinner",
            },
        )

    def test_extract_filters_handles_vegan_vegetarian_and_brunch_mapping(self):
        vegan_filters = rag.extract_filters("vegan breakfast near crossroads")
        veggie_filters = rag.extract_filters("veggie lunch at clark")

        self.assertEqual(
            vegan_filters,
            {
                "dining_hall": "Crossroads",
                "is_vegan": True,
                "meal_period": "Brunch",
            },
        )
        self.assertEqual(
            veggie_filters,
            {
                "dining_hall": "Clark Kerr",
                "is_vegetarian": True,
                "meal_period": "Lunch",
            },
        )

    def test_build_document_contains_human_readable_doc_and_metadata(self):
        doc = rag.build_document(menu_item())

        self.assertIn("Item: Halal Rosemary Chicken", doc.page_content)
        self.assertIn("Calories Per Oz:", doc.page_content)
        self.assertEqual(doc.metadata["halal_status"], "HALAL")
        self.assertEqual(doc.metadata["category"], "Entree")
        self.assertEqual(doc.metadata["ingredients"], "Chicken Diced Dark Meat HALAL; Oil Cooking Blend")
        self.assertEqual(doc.metadata["serving_size"], 3.94)
        self.assertAlmostEqual(doc.metadata["calories_per_oz"], 38.885786802030456)

    def test_retrieve_applies_structured_filters_before_search(self):
        db = rag.embed_menu(
            [
                menu_item(short_name="Halal Rosemary Chicken"),
                menu_item(
                    dining_hall="Cafe 3",
                    short_name="Vegan Lentil Soup",
                    ingredients="Lentils; Tomato; Onion",
                    halal_status="HALAL",
                    is_vegan=True,
                    is_vegetarian=True,
                    meal_period="Lunch",
                ),
                menu_item(
                    dining_hall="Foothill",
                    short_name="Turkey Sandwich",
                    ingredients="Turkey; Bread",
                    halal_status="NOT_HALAL",
                    halal_reason="Contains turkey not labeled halal",
                    meal_period="Dinner",
                ),
            ],
            use_chroma=False,
        )

        results = rag.retrieve(db, "vegan lunch at cafe 3", n_results=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata["short_name"], "Vegan Lentil Soup")
        self.assertEqual(results[0].metadata["dining_hall"], "Cafe 3")

    def test_retrieve_all_dining_halls_query_does_not_apply_hall_filter(self):
        db = rag.embed_menu(
            [
                menu_item(dining_hall="Crossroads", short_name="Halal Rosemary Chicken"),
                menu_item(dining_hall="Foothill", short_name="Halal Lamb Stew"),
            ],
            use_chroma=False,
        )

        results = rag.retrieve(db, "what's halal across all dining halls", n_results=5)

        self.assertEqual({doc.metadata["dining_hall"] for doc in results}, {"Crossroads", "Foothill"})
        self.assertIsNone(rag.extract_filters("what's open across all dining halls"))

    def test_is_stale_false_for_today_and_true_for_old_or_empty_store(self):
        fresh = rag.embed_menu([menu_item()], use_chroma=False)
        stale = rag.embed_menu(
            [menu_item(date=str(date.today() - timedelta(days=1)))],
            use_chroma=False,
        )
        empty = rag.embed_menu([], use_chroma=False)

        self.assertFalse(rag.is_stale(fresh))
        self.assertTrue(rag.is_stale(stale))
        self.assertTrue(rag.is_stale(empty))

    def test_list_documents_returns_stored_menu_documents(self):
        db = rag.embed_menu([menu_item(short_name="Halal Rosemary Chicken")], use_chroma=False)

        docs = rag.list_documents(db)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["short_name"], "Halal Rosemary Chicken")
        self.assertIn("Item: Halal Rosemary Chicken", docs[0].page_content)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import menu_answers
import rag


def doc(name: str, **overrides):
    metadata = {
        "date": "2026-04-29",
        "dining_hall": "Crossroads",
        "meal_period": "Dinner",
        "category": "Entree",
        "short_name": name,
        "halal_status": "HALAL",
        "halal_reason": "No forbidden or ambiguous ingredients found",
        "is_vegan": False,
        "is_vegetarian": False,
        "contains_shellfish": False,
        "shellfish_note": "",
        "ingredients": "",
        "allergens_present": "",
        "calories": 100.0,
        "serving_size": 4.0,
        "serving_size_unit": "oz",
        "calories_per_oz": 25.0,
        "protein": 10.0,
        "fat": 3.0,
        "carbs": 5.0,
        "fiber": 1.0,
        "sodium": 200.0,
        "cholesterol": 0.0,
    }
    metadata.update(overrides)
    return rag.MenuDocument(f"Item: {name}", metadata)


class MenuAnswerTests(unittest.TestCase):
    def test_halal_crossroads_dinner_groups_proteins_and_vegan_items(self):
        docs = [
            doc(
                "Beef Kofta",
                category="Center Plate",
                ingredients="Beef Ground HALAL",
                calories=311,
                serving_size=4,
                protein=19.94,
            ),
            doc(
                "Halal Rosemary Chicken",
                category="Center Plate",
                ingredients="Chicken Diced Dark Meat HALAL",
                calories=153,
                serving_size=3.94,
                protein=20.85,
            ),
            doc(
                "Braised Mung Bean",
                is_vegan=True,
                is_vegetarian=True,
                calories=126,
                serving_size=4.16,
                protein=8.66,
            ),
            doc(
                "Ranch Dressing",
                category="Dressing",
                ingredients="Dressing Ranch HALAL",
                calories=90,
            ),
        ]

        response = menu_answers.build_menu_response(
            "What's halal at Crossroads tonight?",
            docs,
            "2026-04-29",
            include_halal_disclaimer=True,
        )

        self.assertIsNotNone(response)
        text = response.content
        self.assertIn("Here are the halal options at Crossroads for dinner tonight:", text)
        self.assertIn("Proteins:", text)
        self.assertIn("✅ Beef Kofta — 311 cal per 4oz serving", text)
        self.assertIn("Vegan/Vegetarian (halal):", text)
        self.assertIn("Braised Mung Bean (vegan) — 126 cal per 4.16oz serving", text)
        self.assertNotIn("Ranch Dressing", text)
        self.assertTrue(text.endswith(menu_answers.HALAL_NOTE))

    def test_missing_hall_names_available_hall(self):
        response = menu_answers.build_menu_response(
            "Any vegan options at Cafe 3 for dinner?",
            [doc("Braised Mung Bean", is_vegan=True, is_vegetarian=True)],
            "2026-04-29",
        )

        self.assertIsNotNone(response)
        self.assertEqual(
            response.content,
            "I don't have menu data for Cafe 3 for today. I currently have data for Crossroads. "
            "Would you like to see vegan options there instead?",
        )

    def test_high_protein_halal_options_are_sorted_by_protein(self):
        docs = [
            doc("Halal Beef Fajitas", ingredients="Beef HALAL", protein=12.83, calories=94, serving_size=3.18),
            doc("Halal Rosemary Chicken", ingredients="Chicken HALAL", protein=20.85, calories=153, serving_size=3.94),
            doc("Beef Kofta", ingredients="Beef HALAL", protein=19.94, calories=311, serving_size=4),
        ]

        response = menu_answers.build_menu_response(
            "Any high protein halal options tonight?",
            docs,
            "2026-04-29",
        )

        self.assertIsNotNone(response)
        lines = response.content.splitlines()
        self.assertIn("Highest protein halal options at Crossroads tonight:", lines[0])
        chicken_index = response.content.index("Halal Rosemary Chicken")
        kofta_index = response.content.index("Beef Kofta")
        fajita_index = response.content.index("Halal Beef Fajitas")
        self.assertLess(chicken_index, kofta_index)
        self.assertLess(kofta_index, fajita_index)

    def test_halal_and_vegan_query_lists_vegan_items_only(self):
        docs = [
            doc("Halal Rosemary Chicken", ingredients="Chicken HALAL"),
            doc("Braised Mung Bean", is_vegan=True, is_vegetarian=True, calories=126, serving_size=4.16),
        ]

        response = menu_answers.build_menu_response(
            "Is there anything halal and vegan at Crossroads tonight?",
            docs,
            "2026-04-29",
        )

        self.assertIsNotNone(response)
        self.assertIn("Yes, all vegan options shown here are classified halal", response.content)
        self.assertIn("Braised Mung Bean", response.content)
        self.assertNotIn("Halal Rosemary Chicken", response.content)

    def test_halal_under_calories_including_vegan_keeps_halal_proteins(self):
        docs = [
            doc("Halal Beef Fajitas", ingredients="Beef HALAL", calories=94, serving_size=3.18),
            doc("Beef Kofta", ingredients="Beef HALAL", calories=311, serving_size=4),
            doc("Braised Mung Bean", is_vegan=True, is_vegetarian=True, calories=126, serving_size=4.16),
        ]

        response = menu_answers.build_menu_response(
            "What's halal at Crossroads and under 200 calories including vegan options?",
            docs,
            "2026-04-29",
        )

        self.assertIsNotNone(response)
        self.assertIn("Halal Beef Fajitas", response.content)
        self.assertIn("Braised Mung Bean", response.content)
        self.assertNotIn("Beef Kofta", response.content)

    def test_halal_status_uses_classification_reason_and_shellfish_note(self):
        response = menu_answers.build_menu_response(
            "Is the Thai BBQ chicken halal?",
            [
                doc(
                    "Thai BBQ Chicken",
                    ingredients="Chicken Thigh Boneless HALAL; Oyster Sauce",
                    contains_shellfish=True,
                    shellfish_note="Oyster",
                )
            ],
            "2026-04-29",
        )

        self.assertIsNotNone(response)
        self.assertEqual(
            response.content,
            "✅ HALAL — contains 'Chicken Thigh Boneless HALAL' explicitly labeled in ingredients. "
            "Note: contains oyster (shellfish).",
        )

    def test_nutrition_and_portion_calculation_use_serving_metadata(self):
        docs = [
            doc(
                "Halal Rosemary Chicken",
                calories=153,
                serving_size=3.94,
                calories_per_oz=153 / 3.94,
                protein=20.85,
            )
        ]

        serving_response = menu_answers.build_menu_response(
            "How many calories in a serving of halal rosemary chicken?",
            docs,
            "2026-04-29",
        )
        portion_response = menu_answers.build_menu_response(
            "I had 6oz of halal rosemary chicken, how many calories?",
            docs,
            "2026-04-29",
        )

        self.assertEqual(
            serving_response.content,
            "Halal Rosemary Chicken is 153 calories per serving (3.94oz).",
        )
        self.assertEqual(
            portion_response.content,
            "Halal Rosemary Chicken is 153 cal per 3.94oz serving. At 6oz that's approximately 233 calories.",
        )

    def test_pork_and_tree_nut_responses_use_ingredients_and_allergens(self):
        docs = [
            doc("Roasted Pork Loin", category="Center Plate", ingredients="Pork Loin"),
            doc("Assorted Mini Muffins", category="Bakery", allergens_present="Tree Nuts"),
            doc("Halal Rosemary Chicken", ingredients="Chicken HALAL"),
        ]

        pork_response = menu_answers.build_menu_response(
            "Is there pork at Crossroads tonight?",
            docs,
            "2026-04-29",
        )
        allergy_response = menu_answers.build_menu_response(
            "I'm allergic to tree nuts, what can I eat at Crossroads tonight?",
            docs,
            "2026-04-29",
        )

        self.assertIn("Roasted Pork Loin (Center Plate)", pork_response.content)
        self.assertIn("Assorted Mini Muffins", allergy_response.content)
        self.assertIn("All other items on tonight's menu do not list tree nuts", allergy_response.content)

    def test_out_of_scope_and_hours_responses_do_not_need_menu_context(self):
        self.assertEqual(
            menu_answers.build_pre_context_response("Can you recommend a good recipe using chicken?").content,
            "I can only help with what's available at Berkeley dining halls today. "
            "Want me to show you the halal chicken options tonight?",
        )
        self.assertEqual(
            menu_answers.build_pre_context_response("What time does Crossroads open?").content,
            "Crossroads runs Brunch from 10:30am to 3:00pm and Dinner from 4:30pm to 9:00pm.",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import classifier
import prompts


class PromptTests(unittest.TestCase):
    def test_system_prompt_formats_current_date_without_losing_dining_halls(self):
        rendered = prompts.SYSTEM_PROMPT.format(date="2026-04-29")

        self.assertIn("Today's date: 2026-04-29", rendered)
        self.assertIn("Crossroads, Cafe 3, Clark Kerr, Foothill", rendered)

    def test_system_prompt_contains_core_nutrition_rules(self):
        prompt = prompts.SYSTEM_PROMPT

        self.assertIn("Never estimate", prompt)
        self.assertIn("calories_per_oz", prompt)
        self.assertIn("total_calories = calories_per_oz * user_oz", prompt)
        self.assertIn("sum all items and show breakdown then total", prompt)

    def test_system_prompt_contains_core_dietary_rules(self):
        prompt = prompts.SYSTEM_PROMPT

        self.assertIn("Only surface halal status when the user asks about halal", prompt)
        self.assertIn("Classifications are ingredient-based", prompt)
        self.assertIn("Never invent menu items", prompt)

    def test_classification_prompt_requires_json_and_shellfish_handling(self):
        prompt = prompts.CLASSIFICATION_PROMPT

        self.assertIn("Return JSON only", prompt)
        self.assertIn('"status": "HALAL" | "NOT_HALAL" | "UNCERTAIN"', prompt)
        self.assertIn("SHELLFISH: halal", prompt)
        self.assertIn("do not mark NOT_HALAL for shellfish", prompt)

    def test_classifier_uses_shared_classification_prompt(self):
        self.assertIs(classifier.CLASSIFICATION_PROMPT, prompts.CLASSIFICATION_PROMPT)


if __name__ == "__main__":
    unittest.main()

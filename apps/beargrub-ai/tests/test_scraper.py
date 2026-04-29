from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import scraper


SAMPLE_XML = b"""
<root>
  <menu mealperiodname="Dinner">
    <recipes>
      <recipe id="1333" category="Allergen Friendly"
        description="Topping Chicken Rosemary Diced AF HALAL"
        shortName="Halal Rosemary Chicken"
        servingSize="3.94" servingSizeUnit="oz"
        nutrients="153.21|7.06|1.43|0.02|99.03|300.97|0.06|0.04|0|20.85">
        <allergens>
          <allergen id="Shellfish">No</allergen>
          <allergen id="Pork">No</allergen>
        </allergens>
        <dietaryChoices>
          <dietaryChoice id="Halal">Yes</dietaryChoice>
          <dietaryChoice id="Vegan Option">No</dietaryChoice>
          <dietaryChoice id="Vegetarian Option">No</dietaryChoice>
        </dietaryChoices>
        <ingredients><![CDATA[Chicken Diced Dark Meat HALAL; Oil Cooking Blend]]></ingredients>
      </recipe>
      <recipe id="2000" category="Produce" shortName="Beet Red"
        servingSize="0.25" servingSizeUnit="oz"
        nutrients="10|0|0|0|0|1|2|1|1|0">
        <allergens />
        <dietaryChoices>
          <dietaryChoice id="Vegan Option">Yes</dietaryChoice>
          <dietaryChoice id="Vegetarian Option">Yes</dietaryChoice>
        </dietaryChoices>
        <ingredients>Beet Red</ingredients>
      </recipe>
    </recipes>
  </menu>
</root>
"""


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class FakeSession:
    def __init__(self, status_by_location: dict[str, int] | None = None):
        self.status_by_location = status_by_location or {}
        self.urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.urls.append(url)
        location = parse_qs(urlparse(url).query)["location"][0]
        status = self.status_by_location.get(location, 200)
        return FakeResponse(SAMPLE_XML, status_code=status)


class ScraperTests(unittest.TestCase):
    def test_parse_menu_extracts_fields_and_calories_per_oz(self):
        root = scraper.parse_response_content(SAMPLE_XML)

        items = scraper.parse_menu(root, dining_hall="Crossroads", menu_date="2026-04-27")

        self.assertEqual(len(items), 2)
        chicken = items[0]
        self.assertEqual(chicken["short_name"], "Halal Rosemary Chicken")
        self.assertEqual(chicken["meal_period"], "Dinner")
        self.assertEqual(chicken["dining_hall"], "Crossroads")
        self.assertAlmostEqual(chicken["calories_per_oz"], 153.21 / 3.94)
        self.assertEqual(chicken["protein"], 20.85)
        self.assertFalse(chicken["is_vegan"])

    def test_parse_menu_handles_small_serving_size_and_reliable_dietary_tags(self):
        root = scraper.parse_response_content(SAMPLE_XML)

        beet = scraper.parse_menu(root, dining_hall="Cafe 3", menu_date="2026-04-27")[1]

        self.assertEqual(beet["short_name"], "Beet Red")
        self.assertAlmostEqual(beet["calories_per_oz"], 40.0)
        self.assertTrue(beet["is_vegan"])
        self.assertTrue(beet["is_vegetarian"])

    def test_fetch_all_loops_all_halls_and_continues_after_fetch_failure(self):
        session = FakeSession(status_by_location={"cafe3": 500})

        items = scraper.fetch_all("2026-04-27", session=session)

        self.assertEqual(len(session.urls), 4)
        self.assertEqual(len(items), 6)
        self.assertNotIn("Cafe 3", {item["dining_hall"] for item in items})

    def test_fetch_all_single_hall_uses_expected_location_and_date(self):
        session = FakeSession()

        items = scraper.fetch_all("2026-04-27", hall="Clark Kerr", session=session)

        self.assertEqual(len(items), 2)
        self.assertEqual(len(session.urls), 1)
        parsed_url = urlparse(session.urls[0])
        query = parse_qs(parsed_url.query)
        self.assertEqual(query["location"], ["clark-kerr"])
        self.assertEqual(query["date"], ["2026-04-27"])


if __name__ == "__main__":
    unittest.main()

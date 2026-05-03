"""
100-case end-to-end pipeline eval.
Scrapes today's menu, embeds it, runs every prompt through retrieve → GPT,
and checks responses against expected signals derived from today's actual data.

Run: .venv/bin/python tests/eval_pipeline.py
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["BEARGRUB_AUTO_INIT"] = "0"
os.environ["BEARGRUB_TEST_MODE"] = "1"

from datetime import date

from classifier import classify_all, load_cache
from prompts import SYSTEM_PROMPT
from rag import embed_menu, retrieve
from scraper import fetch_all

MENU_DATE = str(date.today())


# ---------------------------------------------------------------------------
# Test cases — derived from today's scraped and classified menu (2026-05-03)
#
# Each tuple: (label, prompt, must_contain, must_not_contain)
# must_contain: ALL must appear in response (case-insensitive)
# must_not_contain: NONE may appear in response (case-insensitive)
# ---------------------------------------------------------------------------
CASES = [

    # ── CATEGORY 1: Halal list queries (one per hall × meal) ────────────────
    ("C1-01 Cafe 3 brunch halal list",
     "what halal options are at cafe 3 for brunch?",
     ["Halal Chicken Tenders", "Halal Chicken Breast"],
     []),

    ("C1-02 Cafe 3 dinner halal list",
     "what halal options are at cafe 3 for dinner?",
     ["Halal Mediterranean", "Halal Chicken Breast"],
     []),

    ("C1-03 Clark Kerr brunch halal list",
     "what halal options are at clark kerr for brunch?",
     ["Halal Ground Beef", "Halal Rosemary"],
     []),

    ("C1-04 Clark Kerr dinner halal list",
     "what halal options are at clark kerr for dinner?",
     ["Halal Honey Mustard", "Halal Ground Beef"],
     []),

    ("C1-05 Crossroads brunch halal list",
     "show me halal options at crossroads for brunch",
     ["Halal North African", "HALAL"],
     []),

    ("C1-06 Crossroads dinner halal list",
     "show me halal options at crossroads for dinner",
     ["Halal Chicken Thigh", "Halal Ground Beef"],
     []),

    ("C1-07 Foothill brunch halal list",
     "what halal food is at foothill for brunch?",
     ["Halal Chicken Breast"],
     []),

    ("C1-08 Foothill dinner halal list",
     "what halal food is at foothill for dinner?",
     ["Halal Beef Mushroom Burger"],
     []),

    # ── CATEGORY 2: Specific item — confirmed HALAL ─────────────────────────
    ("C2-01 Halal Chicken Tenders status",
     "is the halal chicken tenders at cafe 3 halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-02 Halal Chicken Breast cafe 3 dinner",
     "is the halal chicken breast at cafe 3 dinner halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-03 Halal Honey Mustard Chicken Thigh",
     "is the halal honey mustard baked chicken thigh at clark kerr halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-04 Halal Ground Beef clark kerr",
     "is the halal ground beef at clark kerr halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-05 Halal Rosemary Chicken Thigh",
     "is the halal rosemary roasted chicken thigh at clark kerr halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-06 Halal North African Chicken crossroads",
     "is the halal north african style roasted chicken at crossroads halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-07 Halal Chicken Thigh crossroads dinner",
     "is the halal chicken thigh at crossroads dinner halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-08 Halal Beef Mushroom Burger foothill",
     "is the halal beef mushroom burger at foothill halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-09 Halal Chicken Breast foothill brunch",
     "is the halal chicken breast at foothill brunch halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-10 Scrambled Eggs",
     "are the scrambled eggs halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-11 Halal Ground Beef crossroads dinner",
     "is the halal ground beef at crossroads dinner halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    ("C2-12 Halal Mediterranean Chicken cafe 3",
     "is the halal mediterranean style roasted chicken at cafe 3 halal?",
     ["HALAL"],
     ["NOT HALAL", "❌"]),

    # ── CATEGORY 3: Specific item — confirmed NOT HALAL ─────────────────────
    ("C3-01 Pork Sausage Link crossroads",
     "is the pork sausage link at crossroads halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-02 Pepperoni Pizza crossroads",
     "is the pepperoni pizza at crossroads halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-03 Baked Pork Bacon foothill",
     "is the baked pork bacon at foothill halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-04 Ham and Artichoke Pizza foothill",
     "is the ham and artichoke pizza at foothill halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-05 Korean BBQ Chicken Tenders crossroads",
     "is the korean bbq style chicken tenders at crossroads halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-06 Pork Potstickers crossroads",
     "is the pork potstickers at crossroads halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-07 Turkey Sausage Patty cafe 3",
     "is the turkey sausage patty at cafe 3 halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    ("C3-08 Caesar Dressing foothill",
     "is the caesar dressing at foothill halal?",
     ["NOT HALAL", "❌"],
     ["✅ HALAL"]),

    # ── CATEGORY 4: Specific item — UNCERTAIN ───────────────────────────────
    ("C4-01 Fried Orange Tofu uncertain",
     "is the fried orange tofu at clark kerr halal?",
     ["UNCERTAIN", "natural flavors"],
     ["✅ HALAL", "NOT HALAL"]),

    ("C4-02 Vegan Oatmeal Raisin Cookie alcohol allergen",
     "is the vegan oatmeal raisin cookie at cafe 3 halal?",
     ["UNCERTAIN", "alcohol"],
     ["✅ HALAL", "NOT HALAL"]),

    ("C4-03 Vegan Chocolate Chip Cookie alcohol allergen foothill",
     "is the vegan chocolate chip cookie at foothill halal?",
     ["UNCERTAIN", "alcohol"],
     ["✅ HALAL", "NOT HALAL"]),

    ("C4-04 Broccoli Cheddar Soup enzymes",
     "is the broccoli cheddar soup at cafe 3 halal?",
     ["UNCERTAIN", "enzymes"],
     ["✅ HALAL", "NOT HALAL"]),

    ("C4-05 Ranch Dressing natural flavors foothill",
     "is the ranch dressing at foothill halal?",
     ["UNCERTAIN"],
     ["✅ HALAL", "NOT HALAL"]),

    ("C4-06 Marinara Sauce crossroads",
     "is the marinara sauce at crossroads dinner halal?",
     ["UNCERTAIN"],
     ["✅ HALAL", "NOT HALAL"]),

    # ── CATEGORY 5: Vegan list queries ──────────────────────────────────────
    ("C5-01 Cafe 3 brunch vegan list",
     "what vegan options are at cafe 3 for brunch?",
     ["Potato Wedges", "Roasted Carrots"],
     []),

    ("C5-02 Cafe 3 dinner vegan list",
     "what vegan options are at cafe 3 for dinner?",
     ["Roasted Brussels Sprouts"],
     []),

    ("C5-03 Clark Kerr brunch vegan list",
     "what vegan options are at clark kerr for brunch?",
     ["Potato Wedges"],
     []),

    ("C5-04 Clark Kerr dinner vegan list",
     "what vegan options are at clark kerr for dinner?",
     ["Sauteed Green Beans", "Roasted Red Potatoes"],
     []),

    ("C5-05 Crossroads brunch vegan list",
     "what vegan options are at crossroads for brunch?",
     ["Citrus Basmati Rice", "Roasted Carrot"],
     []),

    ("C5-06 Crossroads dinner vegan list",
     "what vegan options are at crossroads for dinner?",
     ["Stir Fried Cabbage", "Bean Sprout Banchan"],
     []),

    ("C5-07 Foothill brunch vegan list",
     "what vegan options are at foothill for brunch?",
     ["Gold Beets", "Shredded Carrots"],
     []),

    ("C5-08 Foothill dinner vegan list",
     "what vegan options are at foothill for dinner?",
     ["Gold Beets", "Shredded Carrots"],
     []),

    # ── CATEGORY 6: Calorie queries ─────────────────────────────────────────
    ("C6-01 Calories Halal Honey Mustard Chicken",
     "how many calories are in the halal honey mustard baked chicken thigh at clark kerr?",
     ["150"],
     ["I don't know", "not available"]),

    ("C6-02 Calories Halal Ground Beef crossroads dinner",
     "how many calories are in the halal ground beef at crossroads dinner?",
     ["300"],
     ["I don't know", "not available"]),

    ("C6-03 Calories Halal Beef Mushroom Burger foothill",
     "how many calories are in the halal beef mushroom burger at foothill?",
     ["578"],
     ["I don't know", "not available"]),

    ("C6-04 Calories Halal Chicken Breast cafe 3",
     "how many calories are in the halal chicken breast at cafe 3?",
     ["136"],
     ["I don't know", "not available"]),

    ("C6-05 Calories Halal Chicken Tenders cafe 3",
     "how many calories are in the halal chicken tenders at cafe 3?",
     ["241"],
     ["I don't know", "not available"]),

    ("C6-06 Calories Halal North African Chicken crossroads",
     "how many calories are in the halal north african style roasted chicken at crossroads brunch?",
     ["327"],
     ["I don't know", "not available"]),

    ("C6-07 Calories Halal Rosemary Chicken clark kerr",
     "how many calories are in the halal rosemary roasted chicken thigh at clark kerr?",
     ["153"],
     ["I don't know", "not available"]),

    ("C6-08 Calories Scrambled Eggs",
     "how many calories are in the scrambled eggs?",
     ["184"],
     ["I don't know", "not available"]),

    ("C6-09 Calories Halal Chicken Thigh clark kerr dinner",
     "how many calories are in the halal chicken thigh at clark kerr dinner?",
     ["150"],
     ["I don't know", "not available"]),

    ("C6-10 Calories Halal Mediterranean Chicken cafe 3 dinner",
     "how many calories are in the halal mediterranean style roasted chicken at cafe 3 dinner?",
     ["328"],
     ["I don't know", "not available"]),

    # ── CATEGORY 7: Portion calculations ────────────────────────────────────
    # Halal Ground Beef CK dinner: 300.03 cal / 4.08 oz = 73.54 cal/oz → 8oz ≈ 588
    ("C7-01 Portion 8oz halal ground beef clark kerr",
     "how many calories are in 8 oz of the halal ground beef at clark kerr dinner?",
     ["588"],
     ["I don't know"]),

    # Halal Chicken Breast: 136.27 / 3.75 = 36.34 cal/oz → 6oz ≈ 218
    ("C7-02 Portion 6oz halal chicken breast cafe 3",
     "how many calories are in 6 oz of the halal chicken breast at cafe 3?",
     ["218"],
     ["I don't know"]),

    # Halal Beef Mushroom Burger: 578.14 / 10.6 = 54.54 cal/oz → 3oz ≈ 163
    ("C7-03 Portion 3oz halal beef mushroom burger foothill",
     "how many calories are in 3 oz of the halal beef mushroom burger at foothill?",
     ["163"],
     ["I don't know"]),

    # Halal Honey Mustard Chicken: 150.53 / 4.26 = 35.33 cal/oz → 10oz ≈ 353
    ("C7-04 Portion 10oz halal honey mustard chicken",
     "how many calories are in 10 oz of the halal honey mustard baked chicken thigh at clark kerr?",
     ["150.53", "4.26"],
     ["I don't know"]),

    # Halal North African Chicken crossroads brunch: 327.52 / 4.15 = 78.92 cal/oz → 5oz ≈ 394
    ("C7-05 Portion 5oz halal north african chicken crossroads",
     "how many calories are in 5 oz of the halal north african style roasted chicken at crossroads?",
     ["394"],
     ["I don't know"]),

    # ── CATEGORY 8: Cross-hall queries ──────────────────────────────────────
    ("C8-01 All halls with halal dinner options",
     "which dining halls have halal options for dinner tonight?",
     ["Cafe 3", "Clark Kerr", "Crossroads", "Foothill"],
     []),

    ("C8-02 All halls with halal brunch options",
     "which dining halls have halal options for brunch today?",
     ["Cafe 3", "Clark Kerr", "Crossroads", "Foothill"],
     []),

    ("C8-03 Where can I eat halal tonight",
     "where can i eat halal tonight?",
     ["Cafe 3", "Clark Kerr", "Crossroads", "Foothill"],
     []),

    ("C8-04 All halls any halal today",
     "what halal protein options are available today across all dining halls?",
     ["Halal Chicken", "Halal Ground Beef"],
     []),

    ("C8-05 Highest protein halal option across all halls",
     "what is the highest protein halal option available tonight?",
     ["halal", "protein"],
     []),

    # ── CATEGORY 9: Out of scope ─────────────────────────────────────────────
    ("C9-01 Future menu next week",
     "what will be served next week?",
     ["today", "only"],
     []),

    ("C9-02 Historical menu yesterday",
     "what was served yesterday?",
     ["today", "only"],
     []),

    ("C9-03 Tomorrow's menu",
     "what will crossroads serve tomorrow?",
     ["today", "only"],
     []),

    ("C9-04 Subjective best dining hall",
     "what's the best dining hall?",
     ["only", "nutrition", "dietary"],
     []),

    ("C9-05 Subjective taste question",
     "what tastes the best at crossroads tonight?",
     ["only", "nutrition", "dietary"],
     []),

    ("C9-06 Directions question",
     "how do i get to foothill from the campanile?",
     ["dining"],
     []),

    ("C9-07 Recipe question",
     "give me a recipe for halal chicken",
     ["only", "nutrition", "dietary"],
     []),

    ("C9-08 Weekly meal plan",
     "what are the halal options for this week?",
     ["halal"],
     []),

    # ── CATEGORY 10: Allergen queries ────────────────────────────────────────
    ("C10-01 Gluten free options clark kerr dinner",
     "are there any gluten free options at clark kerr for dinner?",
     ["gluten"],
     []),

    ("C10-02 Allergens in halal chicken breast foothill",
     "does the halal chicken breast at foothill contain any allergens?",
     ["allergen"],
     []),

    ("C10-03 Pork items at foothill",
     "what items at foothill contain pork?",
     ["pork", "Bacon"],
     []),

    ("C10-04 Egg allergen in halal chicken tenders",
     "does the halal chicken tenders at cafe 3 contain any allergens?",
     ["allergen"],
     []),

    ("C10-05 Pork items at crossroads brunch",
     "what items at crossroads contain pork for brunch?",
     ["pork", "Pork Sausage"],
     []),

    # ── CATEGORY 11: Meal period disambiguation ───────────────────────────────
    ("C11-01 Tonight resolves to dinner clark kerr",
     "what halal options are there tonight at clark kerr?",
     ["Halal Honey Mustard"],
     []),

    ("C11-02 Tonight resolves to dinner foothill",
     "what halal food is at foothill tonight?",
     ["Halal Beef Mushroom Burger"],
     []),

    ("C11-03 Brunch at crossroads",
     "whats for brunch at crossroads?",
     ["Brunch", "Crossroads"],
     []),

    ("C11-04 Breakfast maps to brunch cafe 3",
     "what can i eat for breakfast at cafe 3?",
     ["Cafe 3"],
     []),

    ("C11-05 Dinner at foothill explicit",
     "what is available for dinner at foothill?",
     ["Halal Beef Mushroom Burger", "Foothill"],
     []),

    # ── CATEGORY 12: Protein and macro queries ───────────────────────────────
    ("C12-01 Protein in halal beef mushroom burger",
     "how much protein does the halal beef mushroom burger at foothill have?",
     ["36"],
     []),

    ("C12-02 Protein in halal chicken breast",
     "how much protein does the halal chicken breast at cafe 3 have?",
     ["23"],
     []),

    ("C12-03 Highest protein halal clark kerr dinner",
     "what is the highest protein halal item at clark kerr for dinner?",
     ["Halal Honey Mustard", "22"],
     []),

    ("C12-04 Protein in halal north african chicken",
     "how much protein is in the halal north african style roasted chicken at crossroads brunch?",
     ["19"],
     []),

    ("C12-05 Serving size halal beef mushroom burger",
     "what is the serving size of the halal beef mushroom burger at foothill?",
     ["10"],
     []),

    ("C12-06 Protein halal ground beef crossroads",
     "how much protein is in the halal ground beef at crossroads dinner?",
     ["18"],
     []),

    ("C12-07 Fat in halal chicken thigh clark kerr",
     "how much fat is in the halal chicken thigh at clark kerr dinner?",
     ["fat"],
     []),

    ("C12-08 Protein halal rosemary chicken clark kerr",
     "how much protein is in the halal rosemary roasted chicken thigh at clark kerr brunch?",
     ["21"],
     []),

    # ── CATEGORY 13: Edge cases ──────────────────────────────────────────────
    ("C13-01 Item not on menu today",
     "is there a grilled cheese at clark kerr today?",
     ["menu"],
     []),

    ("C13-02 Halal desserts",
     "are there any halal desserts at clark kerr for dinner?",
     ["Assorted", "Fruits"],
     []),

    ("C13-03 Show everything at crossroads dinner",
     "show me everything at crossroads for dinner",
     ["Halal Chicken Thigh", "Crossroads"],
     []),

    ("C13-04 Gluten allergy crossroads",
     "i'm allergic to gluten, what can i eat at crossroads dinner?",
     ["gluten"],
     []),

    ("C13-05 Soyrizo halal clark kerr brunch",
     "is the soyrizo with peppers and onion at clark kerr brunch halal?",
     ["HALAL", "✅"],
     ["NOT HALAL", "❌"]),

    # ── CATEGORY 14: Shellfish flagging ─────────────────────────────────────
    ("C14-01 Peach pie uncertain at crossroads dinner",
     "is the peach pie at crossroads dinner halal?",
     ["UNCERTAIN"],
     ["NOT HALAL"]),

    ("C14-02 Fiery veggie chili halal foothill",
     "is the fiery veggie chili at foothill halal?",
     ["HALAL", "✅"],
     ["NOT HALAL", "❌"]),

    ("C14-03 Garbanzo beans halal clark kerr",
     "are the garbanzo beans at clark kerr halal?",
     ["HALAL", "✅"],
     ["NOT HALAL", "❌"]),

    # ── CATEGORY 15: Meal plan queries ──────────────────────────────────────
    ("C15-01 High protein halal plan clark kerr today",
     "build me a high protein halal meal plan for today at clark kerr",
     ["Halal", "protein", "Brunch", "Dinner"],
     []),

    ("C15-02 Lowest calorie halal clark kerr dinner",
     "what is the lowest calorie halal option at clark kerr for dinner?",
     ["cal"],
     []),

    ("C15-03 Vegan meal plan crossroads today",
     "build me a vegan meal plan for today at crossroads",
     ["vegan"],
     []),

    ("C15-04 150g protein goal clark kerr honest answer",
     "i want to hit 150g of protein today eating only halal at clark kerr, is that possible?",
     ["protein"],
     []),
]

assert len(CASES) == 100, f"Expected 100 cases, got {len(CASES)}"


def setup_db():
    print(f"[SETUP] Scraping menu for {MENU_DATE}...")
    cache = load_cache()
    raw = fetch_all(MENU_DATE)
    print(f"[SETUP] Scraped {len(raw)} items. Classifying...")
    classified = classify_all(raw, cache)
    print(f"[SETUP] Classified {len(classified)} items. Embedding (in-memory)...")
    db = embed_menu(classified, use_chroma=False)
    print("[SETUP] Done.\n")
    return db


def call_gpt(messages):
    import time
    from openai import OpenAI, RateLimitError
    client = OpenAI()
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=False,
            )
            return response.choices[0].message.content
        except RateLimitError:
            wait = 10 * (attempt + 1)
            print(f"         [rate limit — waiting {wait}s]")
            time.sleep(wait)
    raise RuntimeError("Rate limit retries exhausted")


def run_case(db, prompt, must_contain, must_not_contain):
    chunks = retrieve(db, prompt)
    context = "\n\n".join(getattr(c, "page_content", str(c)) for c in chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(date=MENU_DATE)},
        {"role": "system", "content": f"Menu context:\n{context}"},
        {"role": "user", "content": prompt},
    ]
    response = call_gpt(messages)
    r = response.lower()
    misses = [s for s in must_contain if s.lower() not in r]
    bad_hits = [s for s in must_not_contain if s.lower() in r]
    passed = not misses and not bad_hits
    return passed, response, misses, bad_hits


def main():
    db = setup_db()
    results = []

    for i, (label, prompt, must_contain, must_not_contain) in enumerate(CASES, 1):
        import time
        time.sleep(2)
        print(f"[{i:03d}/100] {label}")
        print(f"         Q: {prompt}")
        passed, response, misses, bad_hits = run_case(db, prompt, must_contain, must_not_contain)
        status = "PASS" if passed else "FAIL"
        print(f"         {status}", end="")
        if misses:
            print(f"  | missing: {misses}", end="")
        if bad_hits:
            print(f"  | unexpected: {bad_hits}", end="")
        print()
        preview = textwrap.shorten(response, width=160, placeholder="...")
        print(f"         A: {preview}\n")
        results.append((status, label, misses, bad_hits))

    passed_count = sum(1 for r in results if r[0] == "PASS")
    print("\n" + "=" * 70)
    print(f"FINAL RESULTS: {passed_count}/100 passed")
    print("=" * 70)

    fails = [(label, misses, bad_hits) for status, label, misses, bad_hits in results if status == "FAIL"]
    if fails:
        print(f"\nFAILED ({len(fails)}):")
        for label, misses, bad_hits in fails:
            print(f"  ❌ {label}")
            if misses:
                print(f"       missing: {misses}")
            if bad_hits:
                print(f"       unexpected: {bad_hits}")
    else:
        print("\nAll 100 cases passed ✅")


if __name__ == "__main__":
    main()

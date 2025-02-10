import json
import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import gpt_classifier as classifier  # OpenAI Classifier
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

CACHE_FILE = "meals_cache.json"

dining_halls = ['Cafe_3', 'Crossroads', 'Foothill', 'Clark_Kerr_Campus']

def download_and_parse_xml(dining_hall, date):
    """Fetch XML data from Berkeley dining API and parse it."""
    url = f"https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/{dining_hall}_{date}.xml"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return ET.fromstring(response.content)
        else:
            print(f"Failed to retrieve XML for {dining_hall} (Status {response.status_code})")
            return None
    except requests.RequestException as e:
        print(f"Error fetching XML: {e}")
        return None

def extract_meals(root, meal_type):
    meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}

    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')

        # 🛑 Fix: Normalize unexpected meal period names
        normalized_meal_period = None
        if "Breakfast" in meal_period:
            normalized_meal_period = "Breakfast"
        elif "Brunch" in meal_period:
            normalized_meal_period = "Brunch"
        elif "Lunch" in meal_period:
            normalized_meal_period = "Lunch"
        elif "Dinner" in meal_period:
            normalized_meal_period = "Dinner"

        # 🛑 Fix: Skip meal periods that don’t match expected values
        if normalized_meal_period is None:
            print(f"⚠️ Skipping unexpected meal period: {meal_period}")
            continue

        recipes = meal.find('recipes')
        if recipes is not None:
            for recipe in recipes.findall('recipe'):
                meal_name = recipe.attrib.get('shortName', '')
                ingredients = recipe.find('ingredients').text

                # 🛑 Fix: Check for NoneType in ingredients
                if ingredients is None:
                    ingredients = ""

                # ✅ Filter meals based on meal_type (halal, vegan, etc.)
                if meal_type == "halal" and "halal" in ingredients.lower():
                    meals[normalized_meal_period].append(meal_name)
                elif meal_type == "vegan" and "vegan" in ingredients.lower():
                    meals[normalized_meal_period].append(meal_name)
                elif meal_type == "vegetarian" and "vegetarian" in ingredients.lower():
                    meals[normalized_meal_period].append(meal_name)

    return meals

def precompute_meal_data():
    """Fetches and caches Halal, Vegetarian, and Vegan meal data, intended to be run once daily."""
    today = datetime.now().strftime("%Y%m%d")
    all_meals = {"halal": {}, "vegetarian": {}, "vegan": {}}

    for dining_hall in dining_halls:
        print(f"Processing meals for {dining_hall} on {today}")
        root = download_and_parse_xml(dining_hall, today)
        if root is not None:
            all_meals["halal"][dining_hall] = extract_meals(root, "halal")
            all_meals["vegetarian"][dining_hall] = extract_meals(root, "vegetarian")
            all_meals["vegan"][dining_hall] = extract_meals(root, "vegan")

    with open(CACHE_FILE, "w") as f:
        json.dump(all_meals, f)

    print("✅ Daily meal update complete!")

def load_cached_meal_data():
    """Loads cached meal data if available, else returns an empty structure."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"halal": {}, "vegetarian": {}, "vegan": {}}


def debug_cache():
    """Prints cached meal data for debugging."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cached_data = json.load(f)
        print("🔍 DEBUG: Cached meal data ->", json.dumps(cached_data, indent=4))
    else:
        print("⚠️ No cache file found.")

@app.route('/')
def home():
    """Simple home route to check API status."""
    return jsonify({"message": "BearGrub API is running!"}), 200

@app.route('/api/halal-meals', methods=['GET'])
def get_halal_meals():
    """Returns cached Halal meal data."""
    return jsonify(load_cached_meal_data().get("halal", {}))

@app.route('/api/vegetarian-meals', methods=['GET'])
def get_vegetarian_meals():
    """Returns cached Vegetarian meal data."""
    return jsonify(load_cached_meal_data().get("vegetarian", {}))

@app.route('/api/vegan-meals', methods=['GET'])
def get_vegan_meals():
    """Returns cached Vegan meal data."""
    return jsonify(load_cached_meal_data().get("vegan", {}))

@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Manually refresh the cached meal data."""
    precompute_meal_data()
    return jsonify({"message": "Cache refreshed successfully"}), 200

@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Manually refresh the cached meal data."""
    precompute_meal_data()
    debug_cache()  # Print cached data after refreshing
    return jsonify({"message": "Cache refreshed successfully"}), 200


if __name__ == '__main__':
    # Check if running as a standalone script
    if os.getenv("RUN_CRON_JOB") == "1":
        precompute_meal_data()  # Run only if triggered by a cron job
    else:
        app.run(host="0.0.0.0", port=5000, debug=True)  # Run Flask normally

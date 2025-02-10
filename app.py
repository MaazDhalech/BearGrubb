import json
import os
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
import gpt_classifier as classifier  # OpenAI Classifier
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

CACHE_FILE = "meals_cache.json"

dining_halls = ['Cafe_3', 'Crossroads', 'Foothill', 'Clark_Kerr_Campus']

def download_and_parse_xml(dining_hall, date):
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

def extract_halal_meals(root):
    halal_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    ai_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}

    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if recipes is not None:
            for recipe in recipes.findall('recipe'):
                ingredients = recipe.find('ingredients').text
                meal_name = recipe.attrib.get('shortName', '')
                if 'halal' in ingredients.lower():
                    if 'Breakfast' in meal_period:
                        ai_meals['Breakfast'].append((meal_name, ingredients))
                    elif 'Brunch' in meal_period:
                        ai_meals['Brunch'].append((meal_name, ingredients))
                    elif 'Lunch' in meal_period:
                        ai_meals['Lunch'].append((meal_name, ingredients))
                    elif 'Dinner' in meal_period:
                        ai_meals['Dinner'].append((meal_name, ingredients))
    
    return classifier.meat_classifier(ai_meals)

def precompute_meal_data():
    """Fetches and caches meal data, intended to be run once daily."""
    today = datetime.now().strftime("%Y%m%d")
    all_halal_meals = {}

    for dining_hall in dining_halls:
        print(f"Processing meals for {dining_hall} on {today}")
        root = download_and_parse_xml(dining_hall, today)
        if root is not None:
            halal_meals = extract_halal_meals(root)
            all_halal_meals[dining_hall] = halal_meals

    with open(CACHE_FILE, "w") as f:
        json.dump(all_halal_meals, f)

    print("✅ Daily meal update complete!")

def load_cached_meal_data():
    """Loads cached meal data if available, else returns an empty structure."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

@app.route('/')
def home():
    """Simple home route to check API status."""
    return jsonify({"message": "BearGrub API is running!"}), 200

@app.route('/api/halal-meals', methods=['GET'])
def get_halal_meals():
    """Returns cached meal data."""
    return jsonify(load_cached_meal_data())

@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache():
    """Manually refresh the cached meal data."""
    precompute_meal_data()
    return jsonify({"message": "Cache refreshed successfully"}), 200

if __name__ == '__main__':
    # Check if running as a standalone script
    if os.getenv("RUN_CRON_JOB") == "1":
        precompute_meal_data()  # Run only if triggered by a cron job
    else:
        app.run(host="0.0.0.0", port=5000, debug=True)  # Run Flask normally

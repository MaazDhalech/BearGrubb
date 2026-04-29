from flask import Flask, jsonify
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import gpt_classifier as classifier
from functools import cache

app = Flask(__name__)
CORS(app)

# List of dining halls
dining_halls = [
    'Cafe_3',
    'Crossroads',
    'Foothill',
    'Clark_Kerr_Campus',
]

# Function to download and parse the XML file for a specific dining hall and date
def download_and_parse_xml(dining_hall, date):
    url = f"https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/{dining_hall}_{date}.xml"
    response = requests.get(url)
    if response.status_code == 200:
        xml_content = response.content
        root = ET.fromstring(xml_content)
        return root
    else:
        print(f"Failed to retrieve XML for {dining_hall} on {date}")
        return None

def find_allergen_value(recipe, allergen_id):
    allergens = recipe.find('allergens')
    allergen = allergens.find(f'allergen[@id="{allergen_id}"]')
    return allergen.text if allergen is not None else None

def find_dietary_value(recipe, dietary_id):
    dietaries = recipe.find('dietaryChoices')
    dietary = dietaries.find(f'dietaryChoice[@id="{dietary_id}"]')
    return dietary.text if dietary is not None else None

# Function to extract halal meals

def extract_halal_meals(root):
    halal_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if recipes:
            for recipe in recipes.findall('recipe'):
                ingredients = recipe.find('ingredients').text
                if 'halal' in ingredients.lower():
                    meal_name = recipe.attrib.get('shortName', '')
                    if 'Breakfast' in meal_period:
                        halal_meals['Breakfast'].append(meal_name)
                    elif 'Brunch' in meal_period:
                        halal_meals['Brunch'].append(meal_name)
                    elif 'Lunch' in meal_period:
                        halal_meals['Lunch'].append(meal_name)
                    elif 'Dinner' in meal_period:
                        halal_meals['Dinner'].append(meal_name)
    return halal_meals

# Get halal meals for today
def get_halal_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    all_halal_meals = {}
    for dining_hall in dining_halls:
        root = download_and_parse_xml(dining_hall, date_str)
        if root:  # Check if root is not None
            halal_meals = extract_halal_meals(root)
            all_halal_meals[dining_hall] = halal_meals
    return all_halal_meals

# Vegan meal extraction
def extract_vegan_meals(root):
    vegan_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if recipes:
            for recipe in recipes.findall('recipe'):
                vegan_value = find_dietary_value(recipe, "Vegan Option")
                if vegan_value == 'Yes':
                    meal_name = recipe.attrib.get('shortName', '')
                    if 'Breakfast' in meal_period:
                        vegan_meals['Breakfast'].append(meal_name)
                    elif 'Brunch' in meal_period:
                        vegan_meals['Brunch'].append(meal_name)
                    elif 'Lunch' in meal_period:
                        vegan_meals['Lunch'].append(meal_name)
                    elif 'Dinner' in meal_period:
                        vegan_meals['Dinner'].append(meal_name)
    return vegan_meals


def extract_halal_meals(root):
    halal_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    ai_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    #Find all meal periods
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if len(recipes) > 0:
            for recipe in recipes.findall('recipe'):
                ingredients = recipe.find('ingredients').text
                alcohol_value = find_allergen_value(recipe, "Alcohol")
                pork_value = find_allergen_value(recipe, "Pork")
                if (alcohol_value == "No" and pork_value == "No"):
                    meal_name = recipe.attrib.get('shortName', '')
                    if 'Breakfast' in meal_period:
                        ai_meals['Breakfast'].append((meal_name,ingredients))
                    elif 'Brunch' in meal_period:
                        ai_meals['Brunch'].append((meal_name,ingredients))
                    elif 'Lunch' in meal_period:
                        ai_meals['Lunch'].append((meal_name,ingredients))
                    elif 'Dinner' in meal_period:
                        ai_meals['Dinner'].append((meal_name,ingredients))
    
    return classifier.meat_classifier(ai_meals)

@cache
def get_halal_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")  # Format date as YYYYMMDD
    all_halal_meals = {}

    for dining_hall in dining_halls:
        print(f"Processing halal meals for {dining_hall} on {date_str}")
        
        root = download_and_parse_xml(dining_hall, date_str)
        if len(root) > 0:
            halal_meals = extract_halal_meals(root)
            all_halal_meals[dining_hall] = halal_meals
    
    return all_halal_meals


# Vegetarian meal extraction
def extract_vegetarian_meals(root):
    vegetarian_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if recipes:
            for recipe in recipes.findall('recipe'):
                vegetarian_value = find_dietary_value(recipe, "Vegetarian Option")
                vegan_value = find_dietary_value(recipe, "Vegan Option")
                if vegetarian_value == 'Yes' or vegan_value == 'Yes':
                    meal_name = recipe.attrib.get('shortName', '')
                    if 'Breakfast' in meal_period:
                        vegetarian_meals['Breakfast'].append(meal_name)
                    elif 'Brunch' in meal_period:
                        vegetarian_meals['Brunch'].append(meal_name)
                    elif 'Lunch' in meal_period:
                        vegetarian_meals['Lunch'].append(meal_name)
                    elif 'Dinner' in meal_period:
                        vegetarian_meals['Dinner'].append(meal_name)
    return vegetarian_meals

# Get vegan meals for today
@cache
def get_vegan_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    all_vegan_meals = {}
    for dining_hall in dining_halls:
        root = download_and_parse_xml(dining_hall, date_str)
        if root:
            vegan_meals = extract_vegan_meals(root)
            all_vegan_meals[dining_hall] = vegan_meals
    return all_vegan_meals

# Get vegetarian meals for today
@cache
def get_vegetarian_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    all_vegetarian_meals = {}
    for dining_hall in dining_halls:
        root = download_and_parse_xml(dining_hall, date_str)
        if root:
            vegetarian_meals = extract_vegetarian_meals(root)
            all_vegetarian_meals[dining_hall] = vegetarian_meals
    return all_vegetarian_meals

# Route to get halal meals
@app.route('/api/halal-meals', methods=['GET'])
def get_halal_meals():
    return jsonify(get_halal_meals_for_today())

# Route to get vegan meals
@app.route('/api/vegan-meals', methods=['GET'])
def get_vegan_meals():
    return jsonify(get_vegan_meals_for_today())

# Route to get vegetarian meals
@app.route('/api/vegetarian-meals', methods=['GET'])
def get_vegetarian_meals():
    return jsonify(get_vegetarian_meals_for_today())

# Running the Flask app
if __name__ == '__main__':
    print("server starting...")
    get_halal_meals_for_today()
    get_vegan_meals_for_today()
    get_vegetarian_meals_for_today()
    print("precompute done..")
    app.run(debug=True, port=5000)

from flask import Flask, jsonify
import subprocess
import json
from flask_cors import CORS

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json


app = Flask(__name__)
CORS(app)

# List of dining halls
dining_halls = [
    'Cafe_3',
    'Crossroads',
    'Foothill',
    'Clark_Kerr_Campus',
    # Add other dining hall names as necessary
]

# Function to download and parse the XML file for a specific dining hall and date
def download_and_parse_xml(dining_hall, date):
    # Format the URL with the dining hall and desired date
    url = f"https://dining.berkeley.edu/wp-content/uploads/menus-exportimport/{dining_hall}_{date}.xml"
    
    # Send a GET request to the URL
    response = requests.get(url)
    
    if response.status_code == 200:
        # Parse the XML content
        xml_content = response.content
        root = ET.fromstring(xml_content)
        return root
    else:
        print(f"Failed to retrieve XML for {dining_hall} on {date}")
        return None

# Function to extract halal meals from the XML based on the keyword 'halal' in ingredients
def extract_halal_meals(root):
    halal_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    
    # Find all meal periods
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        
        if recipes:
            for recipe in recipes.findall('recipe'):
                ingredients = recipe.find('ingredients').text
                if 'halal' in ingredients.lower():  # Search for 'halal' in ingredients
                    meal_name = recipe.attrib.get('shortName', '')  # Use the shortName attribute
                    
                    # Categorize meals based on the meal period
                    if 'Breakfast' in meal_period:
                        halal_meals['Breakfast'].append(meal_name)
                    elif 'Brunch' in meal_period:
                        halal_meals['Brunch'].append(meal_name)
                    elif 'Lunch' in meal_period:
                        halal_meals['Lunch'].append(meal_name)
                    elif 'Dinner' in meal_period:
                        halal_meals['Dinner'].append(meal_name)
    
    return halal_meals

# Function to get halal meals for today's date
def get_halal_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")  # Format date as YYYYMMDD
    all_halal_meals = {}

    for dining_hall in dining_halls:
        print(f"Processing halal meals for {dining_hall} on {date_str}")
        
        root = download_and_parse_xml(dining_hall, date_str)
        if root:
            halal_meals = extract_halal_meals(root)
            all_halal_meals[dining_hall] = halal_meals
    
    return all_halal_meals

# Main code
# if __name__ == "__main__":
#     halal_meals_data = get_halal_meals_for_today()

#     # Print or process the halal meals
#     for dining_hall, meals in halal_meals_data.items():
#         print(f"\nHalal meals for {dining_hall}:")
#         for meal_period, meal_list in meals.items():
#             print(f"  {meal_period}:")
#             if meal_list:
#                 for meal in meal_list:
#                     print(f"    - {meal}")
#             else:
#                 print(f"    No halal meals found.")

# print(json.dumps(meals_data))


@app.route('/api/halal-meals', methods=['GET'])
def get_halal_meals():
    return jsonify(get_halal_meals_for_today())
    # Call the HalalMeat.py script and capture the output
    # try:
    #     result = subprocess.run(['python3', 'HalalMeat.py'], capture_output=True, text=True)
    #     meals_data = json.loads(result.stdout)  # Assuming HalalMeat.py outputs a JSON string
    #     return jsonify(meals_data)  # Return as a JSON response to the client
    # except Exception as e:
    #     return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import gpt_classifier as classifier

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
        # If can't retrieve XML for the dining hall on this date, error message is returned
        print(f"Failed to retrieve XML for {dining_hall} on {date}")
        return None
    
# Finds if the recipe item has a specific allergen
def find_allergen_value(recipe, allergen_id):
    allergens = recipe.find('allergens')
    allergen = allergens.find(f'allergen[@id="{allergen_id}"]')
    return allergen.text if allergen is not None else None

# Finds if the recipe item is meant for a specific diet
def find_dietary_value(recipe, dietary_id):
    dietaries = recipe.find('dietaryChoices')
    dietary = dietaries.find(f'dietaryChoice[@id="{dietary_id}"]')
    return dietary.text if dietary is not None else None

# Switches the dictionary layers of our nested dictionary
def swap_dict_layers(input_dict):
    # Initialize an empty dictionary to store the swapped layers
    new_dict = {}
    # Outer loop: Iterate through the first layer of the input dictionary
    for layer1 in input_dict:
        # Get the dictionary associated with the current 'layer1' key
        layer1_data = input_dict[layer1]
        # Inner loop: Iterate through the second layer within 'layer1'
        for layer2 in layer1_data:
            # Get the data (value) associated with the current 'layer2' key
            layer2_data = layer1_data[layer2]
            # If 'layer2' is not already a key in the new dictionary, create an empty dictionary for it
            if not layer2 in new_dict:
                new_dict[layer2] = {}
            # Swap the layers: Set the value of 'layer1' as a key inside the 'layer2' dictionary
            # with its corresponding value being 'layer2_data'
            new_dict[layer2][layer1] = layer2_data
    # Return the new dictionary with swapped layers
    return new_dict

# Finds all the vegan meals in the xml
def extract_vegan_meals(root):
    # Initialize a dictionary to store vegan meals for each meal period
    vegan_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    #Finds all meal periods 
    for meal in root.findall('.//menu'):
        # Get the 'mealperiodname' attribute for the current meal (e.g., Breakfast, Lunch)
        meal_period = meal.attrib.get('mealperiodname', '')
        # Find the 'recipes' element within the current meal
        recipes = meal.find('recipes')
        # If there are recipes for this meal period
        if len(recipes) > 0:
            # Iterate through each recipe within 'recipes'
            for recipe in recipes.findall('recipe'):
                # Check if the recipe has a vegan option by calling the 'find_dietary_value' function
                vegan_value = find_dietary_value(recipe, "Vegan Option")
                # If the vegan option is available (value is 'Yes')
                if vegan_value == 'Yes':
                    # Get the short name of the recipe (i.e., the meal name)
                    meal_name = recipe.attrib.get('shortName', '')
                    # Add the meal to the appropriate list based on the meal period
                    if 'Breakfast' in meal_period:
                        vegan_meals['Breakfast'].append(meal_name)
                    elif 'Brunch' in meal_period:
                        vegan_meals['Brunch'].append(meal_name)
                    elif 'Lunch' in meal_period:
                        vegan_meals['Lunch'].append(meal_name)
                    elif 'Dinner' in meal_period:
                        vegan_meals['Dinner'].append(meal_name)
    # Return the dictionary containing vegan meals categorized by meal periods
    return vegan_meals
# Finds all the vegetarian meals in the xml following a similar method as the function above
def extract_vegetarian_meals(root):
    vegetarian_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    
    #Find all meal periods
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')

        if len(recipes) > 0:
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

# Extracts halal meals from the meals in the xml file
def extract_halal_meals(root):
    ai_meals = {'Breakfast': [], 'Brunch': [], 'Lunch': [], 'Dinner': []}
    #Find all meal periods
    for meal in root.findall('.//menu'):
        meal_period = meal.attrib.get('mealperiodname', '')
        recipes = meal.find('recipes')
        if len(recipes) > 0:
            # 
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
            


def get_vegan_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    all_vegan_meals = {}

    for dining_hall in dining_halls:
        print(f"Processing vegan meals for {dining_hall} on {date_str}")

        root = download_and_parse_xml(dining_hall,date_str)
        if len(root) > 0:
            vegan_meals = extract_vegan_meals(root)
            all_vegan_meals[dining_hall] = vegan_meals

    return all_vegan_meals

def get_vegetarian_meals_for_today():
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    all_vegetarian_meals = {}

    for dining_hall in dining_halls:
        print(f"Processing vegetarian meals for {dining_hall} on {date_str}")

        root = download_and_parse_xml(dining_hall,date_str)
        if len(root) > 0:
            vegetarian_meals = extract_vegetarian_meals(root)
            all_vegetarian_meals[dining_hall] = vegetarian_meals

    return all_vegetarian_meals

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

if __name__ == "__main__":
    vegan_meals_data = get_vegan_meals_for_today()

    vegetarian_meals_data = get_vegetarian_meals_for_today()
    halal_meals_data = get_halal_meals_for_today()
    
    for dining_hall, meals in vegan_meals_data.items():
        print(f"\nVegan meals for {dining_hall}:")
        for meal_period, meal_list in meals.items():
            print(f"  {meal_period}:")
            if meal_list:
                for meal in meal_list:
                    print(f"    - {meal}")
            else:
                print(f"    No vegan meals found.")
    for dining_hall, meals in vegetarian_meals_data.items():
        print(f"\nVegetarian meals for {dining_hall}:")
        for meal_period, meal_list in meals.items():
            print(f"  {meal_period}:")
            if meal_list:
                for meal in meal_list:
                    print(f"    - {meal}")
            else:
                print(f"    No vegetarian meals found.")
    for dining_hall, meals in halal_meals_data.items():
        print(f"\nHalal meals for {dining_hall}:")
        for meal_period, meal_list in meals.items():
            print(f"  {meal_period}:")
            if meal_list:
                for meal in meal_list:
                    print(f"    - {meal}")
            else:
                print(f"    No halal meals found.")
    
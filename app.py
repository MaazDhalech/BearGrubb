from flask import Flask, jsonify
import MealClassification as mealClassifier
app = Flask(__name__)

@app.route('/halal_meals_today', methods=['GET'])
def get_halal_meals():
    halal_meals_data = mealClassifier.swap_dict_layers(mealClassifier.get_halal_meals_for_today())
    return jsonify(halal_meals_data)

@app.route('/vegan_meals_today', methods = ['GET'])
def get_vegan_meals():
    vegan_meals_data = mealClassifier.swap_dict_layers(mealClassifier.get_vegan_meals_for_today())
    return jsonify(vegan_meals_data)

@app.route('/vegetarian_meals_today', methods = ['GET'])
def get_vegetarian_meals():
    vegetarian_meals_data = mealClassifier.swap_dict_layers(mealClassifier.get_vegetarian_meals_for_today())
    return jsonify(vegetarian_meals_data)
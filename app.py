from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/halal_meals_today', methods=['GET'])
def get_halal_meals():
    halal_meals_data = get_halal_meals_for_today()
    return jsonify(halal_meals_data)

from flask import Flask, request, jsonify, session
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'  # Necessary for session management

# GPT-4o Mini API URL (replace with actual URL)
GPT4O_API_URL = 'http://gpt4o-mini-api-url.com/v1/generate'

# Sample Menu Data
menu_data = {
    "pizza": {
        "dining_hall": "Hall A",
        "ingredients": ["flour", "tomato", "cheese"],
        "nutrition": {"calories": 300, "protein": 12},
    },
    "salad": {
        "dining_hall": "Hall B",
        "ingredients": ["lettuce", "tomato", "cucumber"],
        "nutrition": {"calories": 150, "protein": 2},
    },
    "hummus": {
        "dining_hall": "Hall C",
        "ingredients": ["chickpeas", "tahini", "olive oil"],
        "nutrition": {"calories": 200, "protein": 6},
    }
}

# Dietary Preferences
halal_items = ["salad", "hummus"]
vegetarian_items = ["pizza", "salad"]
vegan_items = ["salad"]

# Function to format menu data into a string
def format_menu_data():
    menu_info = "Menu Information:\n"
    for item, details in menu_data.items():
        menu_info += f"{item.title()} is available at {details['dining_hall']}, "
        menu_info += f"ingredients include {', '.join(details['ingredients'])}. "
        menu_info += f"Nutritional info: {details['nutrition']['calories']} calories, {details['nutrition']['protein']}g protein.\n"
    return menu_info

# Function to query GPT-4o API with conversation history and user input
def query_gpt4o(user_message):
    # Retrieve previous conversation history from session
    conversation_history = session.get('conversation_history', '')

    # Initial prompt explaining the chatbot's job
    initial_prompt = (
        "You are a chatbot that helps users with questions about dining hall menus, halal, vegetarian, and vegan options, "
        "and provides advice on what meals to eat based on their nutritional needs or dietary restrictions. "
        "You should use the menu data provided, give nutritional advice if asked, and suggest meals based on dietary restrictions like vegan or halal. "
        "You may also help users reach specific nutrition goals, such as maintaining a certain calorie intake or consuming above a certain amount of protein."
    )

    # Construct the full prompt with menu data, dietary info, and the current conversation
    menu_info = format_menu_data()
    dietary_info = f"Halal items: {', '.join(halal_items)}. Vegetarian items: {', '.join(vegetarian_items)}. Vegan items: {', '.join(vegan_items)}."
    prompt = f"{initial_prompt}\n\n{menu_info}\n\n{dietary_info}\n\n{conversation_history}User's query: {user_message}"

    # API Payload
    payload = {
        "prompt": prompt,
        "max_tokens": 150,
        "temperature": 0.5
    }
    headers = {
        "Authorization": "Bearer your-api-key-here",
        "Content-Type": "application/json"
    }

    # Call GPT-4o API
    response = requests.post(GPT4O_API_URL, json=payload, headers=headers)
    return response.json()

# Chat route to handle user input
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    # Query GPT-4o API with user message
    try:
        gpt4o_response = query_gpt4o(user_message)
        bot_response = gpt4o_response.get('text', 'Sorry, I am unable to process this request.')
    except Exception as e:
        bot_response = f"Error: {str(e)}"

    # Update conversation history in session
    conversation_history = session.get('conversation_history', '')
    conversation_history += f"User: {user_message}\nBot: {bot_response}\n"
    session['conversation_history'] = conversation_history

    # Return chatbot response
    return jsonify({"response": bot_response})

# Reset the conversation (optional route to clear session)
@app.route('/reset', methods=['POST'])
def reset():
    session.pop('conversation_history', None)
    return jsonify({"message": "Conversation history cleared."})

if __name__ == '__main__':
    app.run(debug=True)

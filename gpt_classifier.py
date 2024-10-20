from openai import OpenAI
client = OpenAI(api_key="(insert API key here)")

def check_meal(meal):
    response = client.chat.completions.with_raw_response.create(
    messages=[
        {
        "role": "system",
        "content": "You are a classifier that looks at different ingredients and assesses which are meat based. You always follow all instructions exactly and only return exactly what is asked of you without additional words."
        },
        {
        "role": "user",
        "content": "I will give you a list of ingredients for a food item. Write a list of all meat-based ingredients from the list which are NOT seafood, writing the whole ingredient including descriptors such as (HALAL). Separate ingredients by line breaks. Ignore whitespace characters at the beginning of the ingredient list. List each sub-item of another item inside parentheses separately. ONLY respond with this list with no preamble or filler words. There should be no other words in your response besides these ingredients. This is the ingredient list for the food item " + meal[0] + ": " + meal[1]
    }],
    model="gpt-4o-mini",
    )

    completion = response.parse()
    return completion.choices[0].message.content

def meat_classifier(unknown_meals):
    meat_ingredients = {}
    for meal_time in unknown_meals:
        meat_ingredients[meal_time] = {}
        for meal in unknown_meals[meal_time]:
            meat_item_str = check_meal(meal)
            meat_items_i = meat_item_str.split("\n")
            
            halal_list = []
            for item in meat_items_i:
                if "HALAL" in item.upper() or "KOSHER" in item.upper():
                    halal_list.append(item)
            for item in halal_list:
                i = meat_items_i.index(item)
                meat_items_i.pop(i)

            meat_ingredients[meal_time][meal[0]] = meat_items_i

    result = {}
    for meal_time in unknown_meals:
        result[meal_time] = []
        for meal in unknown_meals[meal_time]:
            if len(meat_ingredients[meal_time][meal[0]]) == 0 or len(meat_ingredients[meal_time][meal[0]][0]) == 0:
                result[meal_time].append(meal[0])
    
    return result
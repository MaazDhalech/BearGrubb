from openai import OpenAI
client = OpenAI()

response = client.chat.completions.with_raw_response.create(
    messages=[{
        "role": "user",
        "content": "Say this is a test",
    }],
    model="gpt-4o-mini",
)
#print(response.headers.get('x-ratelimit-limit-tokens'))

# get the object that `chat.completions.create()` would have returned
completion = response.parse()
print(completion.choices[0].message.content)
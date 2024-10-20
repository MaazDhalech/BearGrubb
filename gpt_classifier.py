from openai import OpenAI
client = OpenAI(api_key="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")

response = client.chat.completions.with_raw_response.create(
    messages=[{
        "role": "user",
        "content": "Say this is a test",
    }],
    model="gpt-4o-mini",
)

completion = response.parse()
print(completion.choices[0].message.content)
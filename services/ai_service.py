import os
import json
import openai


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    openai.api_key = api_key
    return openai


def clean_ai_text(text):
    if not text:
        return "Sorry, I could not generate a response."

    cleaned = str(text)
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = cleaned.replace("\\t", "\t")
    cleaned = cleaned.replace("\\r", "")
    return cleaned.strip()


def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful productivity assistant."},
            {"role": "user", "content": user_message}
        ]
    )

    text = response["choices"][0]["message"]["content"]
    return clean_ai_text(text)


def extract_task_from_message(user_message):
    client = get_openai_client()

    prompt = f"""
Extract one task from this message and return JSON:

User: {user_message}
"""

    response = client.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    text = response["choices"][0]["message"]["content"]
    cleaned = clean_ai_text(text)

    try:
        parsed = json.loads(cleaned)
    except:
        raise ValueError("Invalid JSON from AI")

    return parsed


def decide_smart_action(user_message):
    reply = generate_ai_reply(user_message)

    return {
        "action": "reply",
        "title": "",
        "description": "",
        "priority": "medium",
        "status": "pending",
        "reply": reply
    }
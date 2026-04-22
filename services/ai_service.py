import os
import json
from openai import OpenAI


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def clean_ai_text(text):
    if not text:
        return "Sorry, I could not generate a response."

    cleaned = str(text)
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = cleaned.replace("\\t", "\t")
    cleaned = cleaned.replace("\\r", "")
    cleaned = cleaned.replace("\\u2014", "—")
    cleaned = cleaned.replace("\\u2013", "–")
    cleaned = cleaned.replace("\\u2018", "‘")
    cleaned = cleaned.replace("\\u2019", "’")
    cleaned = cleaned.replace("\\u201c", "“")
    cleaned = cleaned.replace("\\u201d", "”")

    return cleaned.strip()


def get_response_text(response):
    try:
        return response.choices[0].message.content
    except Exception:
        return None


def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful productivity assistant."
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    return clean_ai_text(get_response_text(response))


def extract_task_from_message(user_message):
    client = get_openai_client()

    prompt = f"""
You are a task extraction assistant.

Read the user's message and extract one actionable task.

Return ONLY valid JSON in this exact format:
{{
  "title": "task title",
  "description": "short optional description or empty string",
  "priority": "low or medium or high",
  "status": "pending",
  "due_date": "ISO datetime string or null"
}}

Rules:
- Return only JSON.
- Keep the title short and clear.
- status must always be "pending".
- priority must be one of: low, medium, high.
- If description is not needed, return an empty string.
- If the message contains time/date (e.g. tomorrow, next week, 6pm), convert it to ISO format (YYYY-MM-DDTHH:MM:SS).
- If no date is found, return null.
- Do not add markdown.
- Do not add explanation.

User message:
{user_message}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_text = get_response_text(response)
    cleaned = clean_ai_text(raw_text)

    try:
        parsed = json.loads(cleaned)
    except Exception:
        raise ValueError("AI did not return valid JSON")

    title = str(parsed.get("title", "")).strip()
    description = str(parsed.get("description", "")).strip()
    priority = str(parsed.get("priority", "medium")).strip().lower()
    status = str(parsed.get("status", "pending")).strip().lower()
    due_date = parsed.get("due_date", None)

    if not title:
        raise ValueError("AI did not return a task title")

    if priority not in ["low", "medium", "high"]:
        priority = "medium"

    if status not in ["pending", "done"]:
        status = "pending"

    return {
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
        "due_date": due_date
    }


def decide_smart_action(user_message):
    client = get_openai_client()

    prompt = f"""
You are a smart personal productivity assistant.

Your job is to decide whether the user's message should:
1. create a task
2. or receive a normal assistant reply

Return ONLY valid JSON in this exact format:
{{
  "action": "task" or "reply",
  "title": "",
  "description": "",
  "priority": "low or medium or high",
  "status": "pending",
  "due_date": "ISO datetime string or null",
  "reply": ""
}}

Rules:
- Return only JSON.
- If the user is asking to remember, do, add, remind, schedule, track, or note an actionable item, choose "task".
- If the user is asking for advice, planning, explanation, or conversation, choose "reply".
- If action is "task":
  - fill title
  - description can be empty
  - priority must be low, medium, or high
  - status must be pending
  - due_date should be ISO datetime string if a date/time exists, otherwise null
  - reply should be empty
- If action is "reply":
  - fill reply
  - title and description should be empty
  - priority should be medium
  - status should be pending
  - due_date should be null
- Do not add markdown.
- Do not add explanation outside JSON.

User message:
{user_message}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_text = get_response_text(response)
    cleaned = clean_ai_text(raw_text)

    try:
        parsed = json.loads(cleaned)
    except Exception:
        raise ValueError("AI did not return valid JSON")

    action = str(parsed.get("action", "reply")).strip().lower()
    title = str(parsed.get("title", "")).strip()
    description = str(parsed.get("description", "")).strip()
    priority = str(parsed.get("priority", "medium")).strip().lower()
    status = str(parsed.get("status", "pending")).strip().lower()
    due_date = parsed.get("due_date", None)
    reply = str(parsed.get("reply", "")).strip()

    if action not in ["task", "reply"]:
        action = "reply"

    if priority not in ["low", "medium", "high"]:
        priority = "medium"

    if status not in ["pending", "done"]:
        status = "pending"

    if action == "task" and not title:
        raise ValueError("AI decided task but did not return a title")

    if action == "reply":
        due_date = None
        if not reply:
            reply = generate_ai_reply(user_message)

    return {
        "action": action,
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
        "due_date": due_date,
        "reply": reply
    }
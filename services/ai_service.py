import os
import json
from datetime import datetime
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
    current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    prompt = f"""
You are a task extraction assistant.

Current datetime (UTC):
{current_datetime}

Read the user's message and extract one actionable task.

Return ONLY valid JSON in this exact format:
{{
  "title": "task title",
  "description": "full user intent as natural sentence",
  "priority": "low or medium or high",
  "status": "pending",
  "due_date": "ISO datetime string or null"
}}

Rules:
- Return only JSON.
- Title must be short (2-4 words).
- Description MUST contain the full original intent of the user.
- Description MUST NOT be empty.
- If user says time/date → include it in description AND convert to due_date.
- priority must be one of: low, medium, high.
- status must always be "pending".
- If the message contains time/date (e.g. tomorrow, next week, 6pm), convert it to ISO format relative to current datetime.
- If no date is found, return null.
- Do not add markdown.
- Do not add explanation.

User message:
{user_message}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
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

    if not description:
        description = user_message.strip()

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
    current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    prompt = f"""
You are a smart productivity assistant.

Current datetime (UTC):
{current_datetime}

Return ONLY JSON:
{{
  "action": "task" or "reply",
  "title": "",
  "description": "",
  "priority": "low|medium|high",
  "status": "pending",
  "due_date": "ISO datetime string or null",
  "reply": ""
}}

Rules:
- If task → description MUST contain full user message
- If reply → due_date must be null
- No markdown

User message:
{user_message}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
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

    if action == "task" and not description:
        description = user_message.strip()

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
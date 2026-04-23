import os
import json
from datetime import datetime
from openai import OpenAI


VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"pending", "done"}


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


def normalize_priority(priority):
    normalized = str(priority or "medium").strip().lower()
    if normalized not in VALID_PRIORITIES:
        return "medium"
    return normalized


def normalize_status(status):
    normalized = str(status or "pending").strip().lower()
    if normalized not in VALID_STATUSES:
        return "pending"
    return normalized


def normalize_due_date(due_date):
    if due_date in [None, "", "null"]:
        return None

    if isinstance(due_date, str):
        cleaned_due_date = due_date.strip()
        if not cleaned_due_date:
            return None
        return cleaned_due_date

    return None


def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a smart, warm, professional productivity assistant. "
                    "You help with planning, focus, tasks, daily organization, motivation, and practical advice. "
                    "You can understand and reply naturally in the same language as the user, including Persian and English. "
                    "Keep answers useful, clear, and natural. "
                    "If the user asks in Persian, reply in Persian. "
                    "If the user asks in English, reply in English."
                )
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

Read the user's message and extract exactly one actionable task.

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
- Title must be short, clear, and useful.
- Description must contain the full original user intent in natural language.
- Description must not be empty.
- status must always be "pending".
- priority must be exactly one of: low, medium, high.
- If the user includes a date or time, convert it to an ISO datetime string relative to current datetime.
- If there is no date/time, return null for due_date.
- Understand Persian and English.
- Do not add markdown.
- Do not add explanation.
- Do not return anything except JSON.

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
    priority = normalize_priority(parsed.get("priority", "medium"))
    status = normalize_status(parsed.get("status", "pending"))
    due_date = normalize_due_date(parsed.get("due_date"))

    if not title:
        raise ValueError("AI did not return a task title")

    if not description:
        description = user_message.strip()

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
- Understand Persian and English.
- If the user is asking to remember, remind, add, do, schedule, track, plan for later, or note an actionable item, choose "task".
- If the user is asking for explanation, advice, ideas, planning help, writing help, productivity help, or conversation, choose "reply".
- If action is "task":
  - title must be short and clear
  - description must contain the full user intent in natural language
  - priority must be low, medium, or high
  - status must be pending
  - due_date should be ISO datetime string if a date/time exists, otherwise null
  - reply must be empty
- If action is "reply":
  - title must be empty
  - description must be empty
  - priority must be medium
  - status must be pending
  - due_date must be null
  - reply must contain a natural helpful response in the same language as the user
- Do not add markdown.
- Do not add explanation outside JSON.
- Do not return anything except JSON.

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
    priority = normalize_priority(parsed.get("priority", "medium"))
    status = normalize_status(parsed.get("status", "pending"))
    due_date = normalize_due_date(parsed.get("due_date"))
    reply = str(parsed.get("reply", "")).strip()

    if action not in ["task", "reply"]:
        action = "reply"

    if action == "task":
        if not title:
            raise ValueError("AI decided task but did not return a title")

        if not description:
            description = user_message.strip()

        return {
            "action": "task",
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "due_date": due_date,
            "reply": ""
        }

    if not reply:
        reply = generate_ai_reply(user_message)

    return {
        "action": "reply",
        "title": "",
        "description": "",
        "priority": "medium",
        "status": "pending",
        "due_date": None,
        "reply": reply
    }
import os
import json
import re
from datetime import datetime
from openai import OpenAI


VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"pending", "done"}


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def get_chat_model():
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


def clean_ai_text(text):
    if not text:
        return "Sorry, I could not generate a response."

    cleaned = str(text)
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = cleaned.replace("\\t", "\t")
    cleaned = cleaned.replace("\\r", "")
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


# 🔥 NEW — REAL MULTILINGUAL INSTRUCTION
def get_language_instruction():
    return (
        "You must ALWAYS detect the user's language from their message and reply in the SAME language. "
        "Support ALL languages (Persian, English, Arabic, Spanish, French, German, etc). "
        "Do not translate unless the user asks. "
        "Match tone, style, and formality naturally."
    )


def extract_first_json_object(text):
    if not text:
        return None

    text = str(text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                candidate = text[start:index + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None

    return None


# 🔥 IMPROVED CHATGPT-STYLE RESPONSE
def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a highly intelligent, friendly, and professional AI assistant. "
                    "You help with thinking, planning, problem-solving, productivity, learning, and real-life decisions. "
                    "Your answers must be clear, helpful, structured when needed, and natural like ChatGPT. "
                    "Avoid robotic answers. Be human-like and practical. "
                    f"{get_language_instruction()}"
                )
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.7
    )

    return clean_ai_text(get_response_text(response))


# 🔥 IMPROVED TASK EXTRACTION
def extract_task_from_message(user_message):
    client = get_openai_client()
    current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    prompt = f"""
You are a task extraction AI.

Current datetime (UTC):
{current_datetime}

{get_language_instruction()}

Extract ONE actionable task from the user's message.

Return ONLY valid JSON:
{{
  "title": "",
  "description": "",
  "priority": "low or medium or high",
  "status": "pending",
  "due_date": "ISO datetime or null"
}}

Rules:
- Only JSON
- Title short
- Description complete
- Detect language automatically
- Convert dates to ISO
- If no date → null

User:
{user_message}
"""

    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    raw_text = get_response_text(response)
    parsed = extract_first_json_object(clean_ai_text(raw_text))

    if not parsed:
        return {
            "title": user_message[:80] or "New task",
            "description": user_message,
            "priority": "medium",
            "status": "pending",
            "due_date": None
        }

    return {
        "title": parsed.get("title") or user_message[:80],
        "description": parsed.get("description") or user_message,
        "priority": normalize_priority(parsed.get("priority")),
        "status": "pending",
        "due_date": normalize_due_date(parsed.get("due_date"))
    }


# 🔥 MAIN DECISION ENGINE (SMART LIKE CHATGPT)
def decide_smart_action(user_message):
    client = get_openai_client()
    current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    prompt = f"""
You are an intelligent assistant.

Current datetime:
{current_datetime}

{get_language_instruction()}

Decide:
- "task" → if user wants to remember something
- "reply" → normal conversation

Return ONLY JSON:
{{
  "action": "task" or "reply",
  "title": "",
  "description": "",
  "priority": "low or medium or high",
  "status": "pending",
  "due_date": "ISO datetime or null",
  "reply": ""
}}

Rules:
- Only JSON
- Be accurate
- Do NOT over-create tasks
- If unsure → reply
- Reply must be natural and helpful

User:
{user_message}
"""

    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    parsed = extract_first_json_object(
        clean_ai_text(get_response_text(response))
    )

    if not parsed:
        return {
            "action": "reply",
            "title": "",
            "description": "",
            "priority": "medium",
            "status": "pending",
            "due_date": None,
            "reply": generate_ai_reply(user_message)
        }

    if parsed.get("action") == "task":
        task = extract_task_from_message(user_message)
        return {
            "action": "task",
            **task,
            "reply": ""
        }

    return {
        "action": "reply",
        "title": "",
        "description": "",
        "priority": "medium",
        "status": "pending",
        "due_date": None,
        "reply": parsed.get("reply") or generate_ai_reply(user_message)
    }
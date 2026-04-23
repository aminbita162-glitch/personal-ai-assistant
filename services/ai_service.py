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
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1")


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


def detect_user_language(user_message):
    text = str(user_message or "").strip()

    if not text:
        return "english"

    persian_chars = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))

    if persian_chars > latin_chars:
        return "persian"

    return "english"


def get_language_instruction(language):
    if language == "persian":
        return (
            "The user's message is in Persian. "
            "You must reply only in Persian. "
            "Do not use English unless the user explicitly asks for English words."
        )

    return (
        "The user's message is in English. "
        "You must reply only in English. "
        "Do not use Persian unless the user explicitly asks for Persian words."
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


def generate_ai_reply(user_message, force_language=None):
    client = get_openai_client()
    language = force_language or detect_user_language(user_message)

    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a smart, warm, highly capable productivity assistant. "
                    "You help with planning, focus, tasks, scheduling, studying, organization, writing, and practical advice. "
                    "Your answers should be natural, useful, concise, and professional. "
                    f"{get_language_instruction(language)}"
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


def extract_task_from_message(user_message):
    client = get_openai_client()
    current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    language = detect_user_language(user_message)

    prompt = f"""
You are a task extraction assistant.

Current datetime (UTC):
{current_datetime}

{get_language_instruction(language)}

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
        model=get_chat_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    raw_text = get_response_text(response)
    cleaned = clean_ai_text(raw_text)
    parsed = extract_first_json_object(cleaned)

    if not parsed:
        return {
            "title": user_message.strip()[:80] or "New task",
            "description": user_message.strip() or "Task created from user message",
            "priority": "medium",
            "status": "pending",
            "due_date": None
        }

    title = str(parsed.get("title", "")).strip()
    description = str(parsed.get("description", "")).strip()
    priority = normalize_priority(parsed.get("priority", "medium"))
    status = normalize_status(parsed.get("status", "pending"))
    due_date = normalize_due_date(parsed.get("due_date"))

    if not title:
        title = user_message.strip()[:80] or "New task"

    if not description:
        description = user_message.strip() or "Task created from user message"

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
    language = detect_user_language(user_message)

    prompt = f"""
You are a smart productivity assistant.

Current datetime (UTC):
{current_datetime}

{get_language_instruction(language)}

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
- Detect the language from the CURRENT user message only.
- If the user is asking to remember, remind, add, do, schedule, track, plan for later, note something for later, or describes a future actionable item, choose "task".
- If the user is asking for explanation, advice, ideas, planning help, writing help, productivity help, conversation, brainstorming, or general assistance, choose "reply".
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
        model=get_chat_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    raw_text = get_response_text(response)
    cleaned = clean_ai_text(raw_text)
    parsed = extract_first_json_object(cleaned)

    if not parsed:
        return {
            "action": "reply",
            "title": "",
            "description": "",
            "priority": "medium",
            "status": "pending",
            "due_date": None,
            "reply": generate_ai_reply(user_message, force_language=language)
        }

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
            title = user_message.strip()[:80] or "New task"

        if not description:
            description = user_message.strip() or "Task created from user message"

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
        reply = generate_ai_reply(user_message, force_language=language)

    return {
        "action": "reply",
        "title": "",
        "description": "",
        "priority": "medium",
        "status": "pending",
        "due_date": None,
        "reply": reply
    }
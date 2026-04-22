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
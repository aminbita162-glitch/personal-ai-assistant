import os
import json
from datetime import datetime
from flask import Flask, jsonify, request, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/tasks", methods=["OPTIONS"])
@app.route("/tasks/<int:task_id>", methods=["OPTIONS"])
@app.route("/init-db", methods=["OPTIONS"])
@app.route("/ai", methods=["OPTIONS"])
@app.route("/ai-browser", methods=["OPTIONS"])
@app.route("/quick-add", methods=["OPTIONS"])
@app.route("/ai-to-task", methods=["OPTIONS"])
@app.route("/ai-to-task-browser", methods=["OPTIONS"])
@app.route("/smart-ai", methods=["OPTIONS"])
@app.route("/smart-ai-browser", methods=["OPTIONS"])
def options_handler(task_id=None):
    return ("", 204)


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def serialize_task(task):
    if not task:
        return task

    if isinstance(task.get("created_at"), datetime):
        task["created_at"] = task["created_at"].isoformat()

    if isinstance(task.get("due_date"), datetime):
        task["due_date"] = task["due_date"].isoformat()

    return task


def parse_due_date(value):
    if value in [None, ""]:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        cleaned = cleaned.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)

    raise ValueError("due_date must be a valid ISO datetime string")


def ensure_tasks_schema():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'medium',
            due_date TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium';
        """
    )

    cur.execute(
        """
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS due_date TIMESTAMP NULL;
        """
    )

    conn.commit()
    cur.close()
    conn.close()


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
    text = None

    try:
        text = response.output_text
    except Exception:
        text = None

    if not text:
        try:
            output_items = getattr(response, "output", [])
            collected = []

            for item in output_items:
                contents = getattr(item, "content", [])
                for content in contents:
                    if getattr(content, "type", "") == "output_text":
                        collected.append(getattr(content, "text", ""))

            if collected:
                text = "\n".join(part for part in collected if part)
        except Exception:
            text = None

    return text


def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"You are a helpful productivity assistant.\nUser: {user_message}"
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
  "status": "pending"
}}

Rules:
- Return only JSON.
- Keep the title short and clear.
- status must always be "pending".
- priority must be one of: low, medium, high.
- If description is not needed, return an empty string.
- Do not add markdown.
- Do not add explanation.

User message:
{user_message}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
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
        "status": status
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
  - reply should be empty
- If action is "reply":
  - fill reply
  - title and description should be empty
  - priority should be medium
  - status should be pending
- Do not add markdown.
- Do not add explanation outside JSON.

User message:
{user_message}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
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
    reply = str(parsed.get("reply", "")).strip()

    if action not in ["task", "reply"]:
        action = "reply"

    if priority not in ["low", "medium", "high"]:
        priority = "medium"

    if status not in ["pending", "done"]:
        status = "pending"

    if action == "task" and not title:
        raise ValueError("AI decided task but did not return a title")

    if action == "reply" and not reply:
        reply = generate_ai_reply(user_message)

    return {
        "action": action,
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
        "reply": reply
    }


def insert_task(title, description="", status="pending", priority="medium", due_date=None):
    ensure_tasks_schema()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        INSERT INTO tasks (title, description, status, priority, due_date)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, title, description, status, priority, due_date, created_at;
        """,
        (title, description, status, priority, due_date)
    )

    task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return serialize_task(dict(task))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/db-check")
def db_check():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "database": "connected",
            "result": result[0]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/init-db", methods=["POST"])
def initialize_database():
    try:
        ensure_tasks_schema()
        return jsonify({
            "status": "success",
            "message": "Database initialized successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/tasks", methods=["GET"])
def get_tasks():
    try:
        ensure_tasks_schema()

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, title, description, status, priority, due_date, created_at
            FROM tasks
            ORDER BY id DESC;
            """
        )
        tasks = cur.fetchall()
        cur.close()
        conn.close()

        serialized_tasks = [serialize_task(dict(task)) for task in tasks]

        return jsonify({
            "status": "success",
            "tasks": serialized_tasks
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/tasks", methods=["POST"])
def create_task():
    try:
        ensure_tasks_schema()

        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        title = data.get("title")
        description = data.get("description", "")
        status = data.get("status", "pending")
        priority = data.get("priority", "medium")
        due_date = parse_due_date(data.get("due_date"))

        if not title or not str(title).strip():
            return jsonify({
                "status": "error",
                "message": "Title is required"
            }), 400

        task = insert_task(
            title=title.strip(),
            description=description,
            status=status,
            priority=priority,
            due_date=due_date
        )

        return jsonify({
            "status": "success",
            "task": task
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/quick-add")
def quick_add():
    try:
        title = request.args.get("title", "Quick Task").strip()

        task = insert_task(title=title)

        return jsonify({
            "status": "success",
            "task": task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/ai", methods=["POST"])
def ai_chat():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        message = data.get("message")

        if not message or not str(message).strip():
            return jsonify({
                "status": "error",
                "message": "Message is required"
            }), 400

        reply = generate_ai_reply(message)

        return jsonify({
            "status": "success",
            "reply": reply
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/ai-browser")
def ai_browser():
    try:
        message = request.args.get("message", "").strip()

        if not message:
            return jsonify({
                "status": "error",
                "message": "message query parameter is required"
            }), 400

        reply = generate_ai_reply(message)

        return jsonify({
            "status": "success",
            "reply": reply
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/ai-to-task", methods=["POST"])
def ai_to_task():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        message = data.get("message")

        if not message or not str(message).strip():
            return jsonify({
                "status": "error",
                "message": "Message is required"
            }), 400

        extracted_task = extract_task_from_message(message.strip())

        task = insert_task(
            title=extracted_task["title"],
            description=extracted_task["description"],
            status=extracted_task["status"],
            priority=extracted_task["priority"],
            due_date=None
        )

        return jsonify({
            "status": "success",
            "message": "Task created from AI",
            "task": task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/ai-to-task-browser")
def ai_to_task_browser():
    try:
        message = request.args.get("message", "").strip()

        if not message:
            return jsonify({
                "status": "error",
                "message": "message query parameter is required"
            }), 400

        extracted_task = extract_task_from_message(message)

        task = insert_task(
            title=extracted_task["title"],
            description=extracted_task["description"],
            status=extracted_task["status"],
            priority=extracted_task["priority"],
            due_date=None
        )

        return jsonify({
            "status": "success",
            "message": "Task created from AI",
            "task": task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/smart-ai", methods=["POST"])
def smart_ai():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        message = data.get("message")

        if not message or not str(message).strip():
            return jsonify({
                "status": "error",
                "message": "Message is required"
            }), 400

        decision = decide_smart_action(message.strip())

        if decision["action"] == "task":
            task = insert_task(
                title=decision["title"],
                description=decision["description"],
                status=decision["status"],
                priority=decision["priority"],
                due_date=None
            )

            return jsonify({
                "status": "success",
                "action": "task",
                "message": "Task created from Smart AI",
                "task": task
            })

        return jsonify({
            "status": "success",
            "action": "reply",
            "reply": decision["reply"]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/smart-ai-browser")
def smart_ai_browser():
    try:
        message = request.args.get("message", "").strip()

        if not message:
            return jsonify({
                "status": "error",
                "message": "message query parameter is required"
            }), 400

        decision = decide_smart_action(message)

        if decision["action"] == "task":
            task = insert_task(
                title=decision["title"],
                description=decision["description"],
                status=decision["status"],
                priority=decision["priority"],
                due_date=None
            )

            return jsonify({
                "status": "success",
                "action": "task",
                "message": "Task created from Smart AI",
                "task": task
            })

        return jsonify({
            "status": "success",
            "action": "reply",
            "reply": decision["reply"]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
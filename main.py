import os
from datetime import datetime
from flask import Flask, jsonify, request
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


# ✅ FIXED AI FUNCTION
def generate_ai_reply(user_message):
    client = get_openai_client()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"You are a helpful productivity assistant.\nUser: {user_message}"
    )

    # safer extraction
    try:
        return response.output_text.strip()
    except Exception:
        try:
            return response.output[0].content[0].text.strip()
        except Exception:
            return "Sorry, I could not generate a response."


@app.route("/")
def home():
    return jsonify({
        "message": "Personal AI Assistant backend is live"
    })


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

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO tasks (title, description, status, priority, due_date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, description, status, priority, due_date, created_at;
            """,
            (title.strip(), description, status, priority, due_date)
        )
        task = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "task": serialize_task(dict(task))
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/quick-add")
def quick_add():
    try:
        ensure_tasks_schema()

        title = request.args.get("title", "Quick Task")

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            INSERT INTO tasks (title)
            VALUES (%s)
            RETURNING id, title, description, status, priority, due_date, created_at;
            """,
            (title,)
        )

        task = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "task": serialize_task(dict(task))
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

        message = data.get("message")

        reply = generate_ai_reply(message.strip())

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
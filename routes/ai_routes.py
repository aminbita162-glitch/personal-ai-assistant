from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.ai_service import (
    decide_smart_action,
    extract_task_from_message,
    generate_ai_reply
)
from services.task_service import build_task_payload, serialize_task


ai_routes = Blueprint("ai_routes", __name__)


def ensure_tasks_schema(get_connection):
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER
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

    cur.execute(
        """
        ALTER TABLE tasks
        ADD COLUMN IF NOT EXISTS user_id INTEGER;
        """
    )

    conn.commit()
    cur.close()
    conn.close()


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "").strip()

    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "", 1).strip()
    return token or None


def get_authenticated_user(get_connection):
    token = get_bearer_token()

    if not token:
        return None

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT id, email, auth_token, created_at
        FROM users
        WHERE auth_token = %s;
        """,
        (token,)
    )

    user = cur.fetchone()
    cur.close()
    conn.close()

    return dict(user) if user else None


def insert_task(
    get_connection,
    title,
    description="",
    status="pending",
    priority="medium",
    due_date=None,
    user_id=None
):
    ensure_tasks_schema(get_connection)

    payload = build_task_payload(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        user_id=user_id
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO tasks (title, description, status, priority, due_date, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, title, description, status, priority, due_date, created_at, user_id;
        """,
        (
            payload["title"],
            payload["description"],
            payload["status"],
            payload["priority"],
            payload["due_date"],
            payload["user_id"]
        )
    )

    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    task = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "status": row[3],
        "priority": row[4],
        "due_date": row[5],
        "created_at": row[6],
        "user_id": row[7]
    }

    return serialize_task(task)


def init_ai_routes(app, get_connection):
    @ai_routes.route("/ai", methods=["POST"])
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

    @ai_routes.route("/ai-browser")
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

    @ai_routes.route("/ai-to-task", methods=["POST"])
    def ai_to_task():
        try:
            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

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
                get_connection=get_connection,
                title=extracted_task["title"],
                description=extracted_task["description"],
                status=extracted_task["status"],
                priority=extracted_task["priority"],
                due_date=None,
                user_id=authenticated_user["id"]
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

    @ai_routes.route("/ai-to-task-browser")
    def ai_to_task_browser():
        try:
            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            message = request.args.get("message", "").strip()

            if not message:
                return jsonify({
                    "status": "error",
                    "message": "message query parameter is required"
                }), 400

            extracted_task = extract_task_from_message(message)

            task = insert_task(
                get_connection=get_connection,
                title=extracted_task["title"],
                description=extracted_task["description"],
                status=extracted_task["status"],
                priority=extracted_task["priority"],
                due_date=None,
                user_id=authenticated_user["id"]
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

    @ai_routes.route("/smart-ai", methods=["POST"])
    def smart_ai():
        try:
            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

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
                    get_connection=get_connection,
                    title=decision["title"],
                    description=decision["description"],
                    status=decision["status"],
                    priority=decision["priority"],
                    due_date=None,
                    user_id=authenticated_user["id"]
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

    @ai_routes.route("/smart-ai-browser")
    def smart_ai_browser():
        try:
            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            message = request.args.get("message", "").strip()

            if not message:
                return jsonify({
                    "status": "error",
                    "message": "message query parameter is required"
                }), 400

            decision = decide_smart_action(message)

            if decision["action"] == "task":
                task = insert_task(
                    get_connection=get_connection,
                    title=decision["title"],
                    description=decision["description"],
                    status=decision["status"],
                    priority=decision["priority"],
                    due_date=None,
                    user_id=authenticated_user["id"]
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

    app.register_blueprint(ai_routes)
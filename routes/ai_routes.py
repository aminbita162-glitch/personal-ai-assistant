from flask import Blueprint, jsonify, request

from services.auth_service import get_current_user
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
            from services.ai_service import generate_ai_reply

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
            from services.ai_service import generate_ai_reply

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
            from services.ai_service import extract_task_from_message

            current_user, error_response, status_code = get_current_user(get_connection)
            if error_response:
                return jsonify(error_response), status_code

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
                due_date=extracted_task.get("due_date"),
                user_id=current_user["id"]
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
            from services.ai_service import extract_task_from_message

            current_user, error_response, status_code = get_current_user(get_connection)
            if error_response:
                return jsonify(error_response), status_code

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
                due_date=extracted_task.get("due_date"),
                user_id=current_user["id"]
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
            from services.ai_service import decide_smart_action

            current_user, error_response, status_code = get_current_user(get_connection)
            if error_response:
                return jsonify(error_response), status_code

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
                    due_date=decision.get("due_date"),
                    user_id=current_user["id"]
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
            from services.ai_service import decide_smart_action

            current_user, error_response, status_code = get_current_user(get_connection)
            if error_response:
                return jsonify(error_response), status_code

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
                    due_date=decision.get("due_date"),
                    user_id=current_user["id"]
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
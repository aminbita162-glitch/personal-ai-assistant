from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.task_service import (
    build_task_payload,
    parse_due_date,
    serialize_task
)


task_routes = Blueprint("task_routes", __name__)


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


def insert_task(get_connection, title, description="", status="pending", priority="medium", due_date=None, user_id=None):
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
    cur = conn.cursor(cursor_factory=RealDictCursor)

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

    task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return serialize_task(dict(task))


def update_task_in_db(
    get_connection,
    task_id,
    user_id,
    title=None,
    description=None,
    status=None,
    priority=None,
    due_date=None,
    due_date_provided=False
):
    ensure_tasks_schema(get_connection)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT id, title, description, status, priority, due_date, created_at, user_id
        FROM tasks
        WHERE id = %s AND user_id = %s;
        """,
        (task_id, user_id)
    )
    existing_task = cur.fetchone()

    if not existing_task:
        cur.close()
        conn.close()
        return None

    new_title = existing_task["title"] if title is None else title
    new_description = existing_task["description"] if description is None else description
    new_status = existing_task["status"] if status is None else status
    new_priority = existing_task["priority"] if priority is None else priority
    new_due_date = existing_task["due_date"]

    if due_date_provided:
        new_due_date = due_date

    payload = build_task_payload(
        title=new_title,
        description=new_description,
        status=new_status,
        priority=new_priority,
        due_date=new_due_date,
        user_id=existing_task["user_id"]
    )

    cur.execute(
        """
        UPDATE tasks
        SET title = %s,
            description = %s,
            status = %s,
            priority = %s,
            due_date = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, title, description, status, priority, due_date, created_at, user_id;
        """,
        (
            payload["title"],
            payload["description"],
            payload["status"],
            payload["priority"],
            payload["due_date"],
            task_id,
            user_id
        )
    )
    updated_task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return serialize_task(dict(updated_task))


def init_task_routes(app, get_connection):
    @task_routes.route("/tasks", methods=["GET"])
    def get_tasks():
        try:
            ensure_tasks_schema(get_connection)

            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                SELECT id, title, description, status, priority, due_date, created_at, user_id
                FROM tasks
                WHERE user_id = %s
                ORDER BY id DESC;
                """,
                (authenticated_user["id"],)
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

    @task_routes.route("/tasks", methods=["POST"])
    def create_task():
        try:
            ensure_tasks_schema(get_connection)

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

            due_date = parse_due_date(data.get("due_date"))

            task = insert_task(
                get_connection=get_connection,
                title=data.get("title"),
                description=data.get("description", ""),
                status=data.get("status", "pending"),
                priority=data.get("priority", "medium"),
                due_date=due_date,
                user_id=authenticated_user["id"]
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

    @task_routes.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
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

            due_date_provided = "due_date" in data
            due_date = None

            if due_date_provided:
                due_date = parse_due_date(data.get("due_date"))

            updated_task = update_task_in_db(
                get_connection=get_connection,
                task_id=task_id,
                user_id=authenticated_user["id"],
                title=data.get("title"),
                description=data.get("description"),
                status=data.get("status"),
                priority=data.get("priority"),
                due_date=due_date,
                due_date_provided=due_date_provided
            )

            if not updated_task:
                return jsonify({
                    "status": "error",
                    "message": "Task not found"
                }), 404

            return jsonify({
                "status": "success",
                "task": updated_task
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @task_routes.route("/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id):
        try:
            ensure_tasks_schema(get_connection)

            authenticated_user = get_authenticated_user(get_connection)

            if not authenticated_user:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                DELETE FROM tasks
                WHERE id = %s AND user_id = %s
                RETURNING id, title, description, status, priority, due_date, created_at, user_id;
                """,
                (task_id, authenticated_user["id"])
            )
            deleted_task = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            if not deleted_task:
                return jsonify({
                    "status": "error",
                    "message": "Task not found"
                }), 404

            return jsonify({
                "status": "success",
                "message": "Task deleted",
                "task": serialize_task(dict(deleted_task))
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(task_routes)
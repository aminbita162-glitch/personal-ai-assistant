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


def insert_task(get_connection, title, description="", status="pending", priority="medium", due_date=None):
    ensure_tasks_schema(get_connection)

    payload = build_task_payload(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date
    )

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        INSERT INTO tasks (title, description, status, priority, due_date)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, title, description, status, priority, due_date, created_at;
        """,
        (
            payload["title"],
            payload["description"],
            payload["status"],
            payload["priority"],
            payload["due_date"]
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
        SELECT id, title, description, status, priority, due_date, created_at
        FROM tasks
        WHERE id = %s;
        """,
        (task_id,)
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
        due_date=new_due_date
    )

    cur.execute(
        """
        UPDATE tasks
        SET title = %s,
            description = %s,
            status = %s,
            priority = %s,
            due_date = %s
        WHERE id = %s
        RETURNING id, title, description, status, priority, due_date, created_at;
        """,
        (
            payload["title"],
            payload["description"],
            payload["status"],
            payload["priority"],
            payload["due_date"],
            task_id
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

    @task_routes.route("/tasks", methods=["POST"])
    def create_task():
        try:
            ensure_tasks_schema(get_connection)

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

    @task_routes.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        try:
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

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                DELETE FROM tasks
                WHERE id = %s
                RETURNING id, title, description, status, priority, due_date, created_at;
                """,
                (task_id,)
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
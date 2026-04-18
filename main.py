import os
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


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
        init_db()
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
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, title, description, status, created_at
            FROM tasks
            ORDER BY id DESC;
            """
        )
        tasks = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "tasks": tasks
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/tasks", methods=["POST"])
def create_task():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        title = data.get("title")
        description = data.get("description", "")
        status = data.get("status", "pending")

        if not title or not str(title).strip():
            return jsonify({
                "status": "error",
                "message": "Title is required"
            }), 400

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO tasks (title, description, status)
            VALUES (%s, %s, %s)
            RETURNING id, title, description, status, created_at;
            """,
            (title.strip(), description, status)
        )
        task = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "task": task
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body must be JSON"
            }), 400

        title = data.get("title")
        description = data.get("description")
        status = data.get("status")

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM tasks WHERE id = %s;", (task_id,))
        existing_task = cur.fetchone()

        if not existing_task:
            cur.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Task not found"
            }), 404

        new_title = title.strip() if title is not None and str(title).strip() else existing_task["title"]
        new_description = description if description is not None else existing_task["description"]
        new_status = status if status is not None else existing_task["status"]

        cur.execute(
            """
            UPDATE tasks
            SET title = %s, description = %s, status = %s
            WHERE id = %s
            RETURNING id, title, description, status, created_at;
            """,
            (new_title, new_description, new_status, task_id)
        )
        updated_task = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "task": updated_task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            DELETE FROM tasks
            WHERE id = %s
            RETURNING id, title, description, status, created_at;
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
            "task": deleted_task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
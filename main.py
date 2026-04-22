import os
from flask import Flask, jsonify, render_template
import psycopg2

from routes.task_routes import init_task_routes, ensure_tasks_schema
from routes.calendar_routes import init_calendar_routes, ensure_appointments_schema
from routes.reminder_routes import init_reminder_routes
from routes.ai_routes import init_ai_routes
from routes.user_routes import init_user_routes
from services.user_service import create_user_table

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/tasks", methods=["OPTIONS"])
@app.route("/tasks/<int:task_id>", methods=["OPTIONS"])
@app.route("/appointments", methods=["OPTIONS"])
@app.route("/appointments/<int:appointment_id>", methods=["OPTIONS"])
@app.route("/reminders", methods=["OPTIONS"])
@app.route("/init-db", methods=["OPTIONS"])
@app.route("/ai", methods=["OPTIONS"])
@app.route("/ai-browser", methods=["OPTIONS"])
@app.route("/quick-add", methods=["OPTIONS"])
@app.route("/ai-to-task", methods=["OPTIONS"])
@app.route("/ai-to-task-browser", methods=["OPTIONS"])
@app.route("/smart-ai", methods=["OPTIONS"])
@app.route("/smart-ai-browser", methods=["OPTIONS"])
@app.route("/signup", methods=["OPTIONS"])
@app.route("/login", methods=["OPTIONS"])
@app.route("/app-info", methods=["OPTIONS"])
def options_handler(task_id=None, appointment_id=None):
    return ("", 204)


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/app-info")
def app_info():
    return jsonify({
        "name": "Personal AI Assistant",
        "version": "1.0.0",
        "author": "Amin Azimi",
        "description": "A smart productivity assistant for tasks, reminders, appointments, and AI-powered help."
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
        ensure_tasks_schema(get_connection)
        ensure_appointments_schema(get_connection)
        create_user_table(get_connection)

        return jsonify({
            "status": "success",
            "message": "Database initialized successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


init_task_routes(app, get_connection)
init_calendar_routes(app, get_connection)
init_reminder_routes(app, get_connection)
init_ai_routes(app, get_connection)
init_user_routes(app, get_connection)
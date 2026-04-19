from flask import Blueprint, jsonify

from services.reminder_service import (
    build_reminder_window,
    build_reminders_payload
)


reminder_routes = Blueprint("reminder_routes", __name__)


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


def ensure_appointments_schema(get_connection):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            appointment_time TIMESTAMP NOT NULL,
            location TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS description TEXT;
        """
    )

    cur.execute(
        """
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS location TEXT;
        """
    )

    cur.execute(
        """
        ALTER TABLE appointments
        ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'scheduled';
        """
    )

    conn.commit()
    cur.close()
    conn.close()


def init_reminder_routes(app, get_connection):
    @reminder_routes.route("/reminders", methods=["GET"])
    def get_reminders():
        try:
            ensure_tasks_schema(get_connection)
            ensure_appointments_schema(get_connection)

            reminder_window = build_reminder_window(hours=1)
            current_time = reminder_window["current_time"]
            end_time = reminder_window["end_time"]

            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT id, title, due_date, status
                FROM tasks
                WHERE due_date IS NOT NULL
                  AND due_date >= %s
                  AND due_date <= %s
                  AND status = 'pending'
                ORDER BY due_date ASC;
                """,
                (current_time, end_time)
            )
            task_rows = cur.fetchall()

            cur.execute(
                """
                SELECT id, title, appointment_time, status
                FROM appointments
                WHERE appointment_time >= %s
                  AND appointment_time <= %s
                  AND status = 'scheduled'
                ORDER BY appointment_time ASC;
                """,
                (current_time, end_time)
            )
            appointment_rows = cur.fetchall()

            cur.close()
            conn.close()

            tasks = [
                {
                    "id": row[0],
                    "title": row[1],
                    "due_date": row[2],
                    "status": row[3]
                }
                for row in task_rows
            ]

            appointments = [
                {
                    "id": row[0],
                    "title": row[1],
                    "appointment_time": row[2],
                    "status": row[3]
                }
                for row in appointment_rows
            ]

            return jsonify(build_reminders_payload(tasks, appointments))
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(reminder_routes)
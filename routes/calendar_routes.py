from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor

from services.calendar_service import (
    build_appointment_payload,
    parse_appointment_time,
    serialize_appointment
)


calendar_routes = Blueprint("calendar_routes", __name__)


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


def insert_appointment(
    get_connection,
    title,
    appointment_time,
    description="",
    location="",
    status="scheduled"
):
    ensure_appointments_schema(get_connection)

    payload = build_appointment_payload(
        title=title,
        appointment_time=appointment_time,
        description=description,
        location=location,
        status=status
    )

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        INSERT INTO appointments (title, description, appointment_time, location, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, title, description, appointment_time, location, status, created_at;
        """,
        (
            payload["title"],
            payload["description"],
            payload["appointment_time"],
            payload["location"],
            payload["status"]
        )
    )

    appointment = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return serialize_appointment(dict(appointment))


def update_appointment_in_db(
    get_connection,
    appointment_id,
    title=None,
    description=None,
    appointment_time=None,
    location=None,
    status=None,
    appointment_time_provided=False
):
    ensure_appointments_schema(get_connection)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT id, title, description, appointment_time, location, status, created_at
        FROM appointments
        WHERE id = %s;
        """,
        (appointment_id,)
    )
    existing_appointment = cur.fetchone()

    if not existing_appointment:
        cur.close()
        conn.close()
        return None

    new_title = existing_appointment["title"] if title is None else title
    new_description = existing_appointment["description"] if description is None else description
    new_location = existing_appointment["location"] if location is None else location
    new_status = existing_appointment["status"] if status is None else status
    new_appointment_time = existing_appointment["appointment_time"]

    if appointment_time_provided:
        new_appointment_time = appointment_time

    payload = build_appointment_payload(
        title=new_title,
        appointment_time=new_appointment_time,
        description=new_description,
        location=new_location,
        status=new_status
    )

    cur.execute(
        """
        UPDATE appointments
        SET title = %s,
            description = %s,
            appointment_time = %s,
            location = %s,
            status = %s
        WHERE id = %s
        RETURNING id, title, description, appointment_time, location, status, created_at;
        """,
        (
            payload["title"],
            payload["description"],
            payload["appointment_time"],
            payload["location"],
            payload["status"],
            appointment_id
        )
    )
    updated_appointment = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return serialize_appointment(dict(updated_appointment))


def init_calendar_routes(app, get_connection):
    @calendar_routes.route("/appointments", methods=["GET"])
    def get_appointments():
        try:
            ensure_appointments_schema(get_connection)

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, title, description, appointment_time, location, status, created_at
                FROM appointments
                ORDER BY appointment_time ASC, id DESC;
                """
            )
            appointments = cur.fetchall()
            cur.close()
            conn.close()

            serialized_appointments = [
                serialize_appointment(dict(appointment))
                for appointment in appointments
            ]

            return jsonify({
                "status": "success",
                "appointments": serialized_appointments
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @calendar_routes.route("/appointments", methods=["POST"])
    def create_appointment():
        try:
            ensure_appointments_schema(get_connection)

            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            appointment_time = parse_appointment_time(data.get("appointment_time"))

            appointment = insert_appointment(
                get_connection=get_connection,
                title=data.get("title"),
                description=data.get("description", ""),
                appointment_time=appointment_time,
                location=data.get("location", ""),
                status=data.get("status", "scheduled")
            )

            return jsonify({
                "status": "success",
                "appointment": appointment
            }), 201
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @calendar_routes.route("/appointments/create")
    def create_appointment_browser():
        try:
            ensure_appointments_schema(get_connection)

            title = request.args.get("title", "").strip()
            description = request.args.get("description", "").strip()
            location = request.args.get("location", "").strip()
            status = request.args.get("status", "scheduled").strip().lower()
            appointment_time_raw = request.args.get("appointment_time", "").strip()
            scheduled_at_raw = request.args.get("scheduled_at", "").strip()

            raw_time_value = appointment_time_raw or scheduled_at_raw
            appointment_time = parse_appointment_time(raw_time_value)

            appointment = insert_appointment(
                get_connection=get_connection,
                title=title,
                description=description,
                appointment_time=appointment_time,
                location=location,
                status=status
            )

            return jsonify({
                "status": "success",
                "appointment": appointment
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @calendar_routes.route("/appointments/<int:appointment_id>", methods=["PUT"])
    def update_appointment(appointment_id):
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            appointment_time_provided = "appointment_time" in data
            appointment_time = None

            if appointment_time_provided:
                appointment_time = parse_appointment_time(data.get("appointment_time"))

            updated_appointment = update_appointment_in_db(
                get_connection=get_connection,
                appointment_id=appointment_id,
                title=data.get("title"),
                description=data.get("description"),
                appointment_time=appointment_time,
                location=data.get("location"),
                status=data.get("status"),
                appointment_time_provided=appointment_time_provided
            )

            if not updated_appointment:
                return jsonify({
                    "status": "error",
                    "message": "Appointment not found"
                }), 404

            return jsonify({
                "status": "success",
                "appointment": updated_appointment
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @calendar_routes.route("/appointments/<int:appointment_id>", methods=["DELETE"])
    def delete_appointment(appointment_id):
        try:
            ensure_appointments_schema(get_connection)

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                DELETE FROM appointments
                WHERE id = %s
                RETURNING id, title, description, appointment_time, location, status, created_at;
                """,
                (appointment_id,)
            )
            deleted_appointment = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            if not deleted_appointment:
                return jsonify({
                    "status": "error",
                    "message": "Appointment not found"
                }), 404

            return jsonify({
                "status": "success",
                "message": "Appointment deleted",
                "appointment": serialize_appointment(dict(deleted_appointment))
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(calendar_routes)
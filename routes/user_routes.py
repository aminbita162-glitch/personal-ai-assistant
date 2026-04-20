from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor
import bcrypt

user_routes = Blueprint("user_routes", __name__)


def ensure_users_schema(get_connection):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def init_user_routes(app, get_connection):

    @user_routes.route("/signup", methods=["POST"])
    def signup():
        try:
            ensure_users_schema(get_connection)

            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return jsonify({
                    "status": "error",
                    "message": "Email and password required"
                }), 400

            hashed_password = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                INSERT INTO users (email, password)
                VALUES (%s, %s)
                RETURNING id, email, created_at;
            """, (email, hashed_password))

            user = cur.fetchone()

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "status": "success",
                "user": user
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500


    @user_routes.route("/login", methods=["POST"])
    def login():
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            email = data.get("email")
            password = data.get("password")

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT * FROM users WHERE email = %s;
            """, (email,))

            user = cur.fetchone()

            cur.close()
            conn.close()

            if not user:
                return jsonify({
                    "status": "error",
                    "message": "User not found"
                }), 404

            if not bcrypt.checkpw(
                password.encode("utf-8"),
                user["password"].encode("utf-8")
            ):
                return jsonify({
                    "status": "error",
                    "message": "Invalid password"
                }), 401

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "email": user["email"]
                }
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(user_routes)
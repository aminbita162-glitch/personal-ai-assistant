from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor
import bcrypt
import secrets

user_routes = Blueprint("user_routes", __name__)


def ensure_users_schema(get_connection):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            auth_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS name TEXT;
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS auth_token TEXT;
    """)

    conn.commit()
    cur.close()
    conn.close()


def generate_auth_token():
    return secrets.token_hex(32)


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "").strip()

    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "", 1).strip()
    return token or None


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

            name = str(data.get("name", "")).strip()
            email = str(data.get("email", "")).strip().lower()
            password = str(data.get("password", "")).strip()

            if not email or not password:
                return jsonify({
                    "status": "error",
                    "message": "Email and password required"
                }), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id
                FROM users
                WHERE email = %s;
            """, (email,))
            existing_user = cur.fetchone()

            if existing_user:
                cur.close()
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": "User already exists"
                }), 409

            hashed_password = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            auth_token = generate_auth_token()

            cur.execute("""
                INSERT INTO users (name, email, password, auth_token)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, email, auth_token, created_at;
            """, (name, email, hashed_password, auth_token))

            user = cur.fetchone()

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "status": "success",
                "message": "Signup successful",
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "auth_token": user["auth_token"],
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None
                }
            }), 201

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @user_routes.route("/login", methods=["POST"])
    def login():
        try:
            ensure_users_schema(get_connection)

            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            email = str(data.get("email", "")).strip().lower()
            password = str(data.get("password", "")).strip()

            if not email or not password:
                return jsonify({
                    "status": "error",
                    "message": "Email and password required"
                }), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, name, email, password, auth_token, created_at
                FROM users
                WHERE email = %s;
            """, (email,))

            user = cur.fetchone()

            if not user:
                cur.close()
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": "User not found"
                }), 404

            if not bcrypt.checkpw(
                password.encode("utf-8"),
                user["password"].encode("utf-8")
            ):
                cur.close()
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": "Invalid password"
                }), 401

            auth_token = generate_auth_token()

            cur.execute("""
                UPDATE users
                SET auth_token = %s
                WHERE id = %s
                RETURNING id, name, email, auth_token, created_at;
            """, (auth_token, user["id"]))

            updated_user = cur.fetchone()

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": updated_user["id"],
                    "name": updated_user["name"],
                    "email": updated_user["email"],
                    "auth_token": updated_user["auth_token"],
                    "created_at": updated_user["created_at"].isoformat() if updated_user["created_at"] else None
                }
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @user_routes.route("/me", methods=["GET"])
    def me():
        try:
            ensure_users_schema(get_connection)

            token = get_bearer_token()

            if not token:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, name, email, auth_token, created_at
                FROM users
                WHERE auth_token = %s;
            """, (token,))

            user = cur.fetchone()
            cur.close()
            conn.close()

            if not user:
                return jsonify({
                    "status": "error",
                    "message": "Invalid token"
                }), 401

            return jsonify({
                "status": "success",
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "auth_token": user["auth_token"],
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None
                }
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @user_routes.route("/logout", methods=["POST"])
    def logout():
        try:
            ensure_users_schema(get_connection)

            token = get_bearer_token()

            if not token:
                return jsonify({
                    "status": "error",
                    "message": "Authorization token is required"
                }), 401

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                UPDATE users
                SET auth_token = NULL
                WHERE auth_token = %s
                RETURNING id, name, email, created_at;
            """, (token,))

            user = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            if not user:
                return jsonify({
                    "status": "error",
                    "message": "Invalid token"
                }), 401

            return jsonify({
                "status": "success",
                "message": "Logout successful"
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(user_routes)
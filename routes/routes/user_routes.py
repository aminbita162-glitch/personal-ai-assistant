from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor


user_routes = Blueprint("user_routes", __name__)


def init_user_routes(app, get_connection):
    @user_routes.route("/signup", methods=["POST"])
    def signup():
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            username = str(data.get("username", "")).strip()
            password = str(data.get("password", "")).strip()

            if not username:
                return jsonify({
                    "status": "error",
                    "message": "Username is required"
                }), 400

            if not password:
                return jsonify({
                    "status": "error",
                    "message": "Password is required"
                }), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                SELECT id
                FROM users
                WHERE username = %s;
                """,
                (username,)
            )
            existing_user = cur.fetchone()

            if existing_user:
                cur.close()
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": "Username already exists"
                }), 400

            cur.execute(
                """
                INSERT INTO users (username, password)
                VALUES (%s, %s)
                RETURNING id, username, created_at;
                """,
                (username, password)
            )
            user = cur.fetchone()

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "status": "success",
                "message": "User created successfully",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
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
            data = request.get_json()

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body must be JSON"
                }), 400

            username = str(data.get("username", "")).strip()
            password = str(data.get("password", "")).strip()

            if not username:
                return jsonify({
                    "status": "error",
                    "message": "Username is required"
                }), 400

            if not password:
                return jsonify({
                    "status": "error",
                    "message": "Password is required"
                }), 400

            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                SELECT id, username, password, created_at
                FROM users
                WHERE username = %s;
                """,
                (username,)
            )
            user = cur.fetchone()

            cur.close()
            conn.close()

            if not user:
                return jsonify({
                    "status": "error",
                    "message": "User not found"
                }), 404

            if user["password"] != password:
                return jsonify({
                    "status": "error",
                    "message": "Invalid password"
                }), 401

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None
                }
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    app.register_blueprint(user_routes)
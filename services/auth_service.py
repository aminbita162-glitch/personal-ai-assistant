from flask import request
from psycopg2.extras import RealDictCursor


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "").strip()

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    return auth_header.replace("Bearer ", "", 1).strip()


def get_current_user(get_connection):
    token = get_bearer_token()

    if not token:
        return None, {
            "status": "error",
            "message": "Authentication required"
        }, 401

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, email, auth_token, created_at
        FROM users
        WHERE auth_token = %s;
    """, (token,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return None, {
            "status": "error",
            "message": "Invalid token"
        }, 401

    return user, None, None
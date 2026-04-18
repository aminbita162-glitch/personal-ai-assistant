import os
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)


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
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        return jsonify({
            "status": "error",
            "message": "DATABASE_URL is not set"
        }), 500

    try:
        conn = psycopg2.connect(database_url)
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
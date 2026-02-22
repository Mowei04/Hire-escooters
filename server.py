from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scooter_mvp.db"

app = Flask(__name__)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
        """
    )
    conn.commit()
    conn.close()


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health_check():
    return jsonify({"status": "ok", "framework": "flask"})


@app.post("/api/auth/register")
def register_user():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"message": "email and password are required"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (email, f"plain::{password}", "customer"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"message": "Email already exists"}), 409
    finally:
        conn.close()

    return jsonify({"message": "User registered"}), 201


@app.post("/api/auth/login")
def login_user():
    return jsonify({"message": "Login endpoint placeholder"})


@app.get("/api/customer/pricing")
def get_pricing():
    return jsonify({"message": "Pricing endpoint placeholder"})


@app.post("/api/customer/bookings")
def create_booking():
    return jsonify({"message": "Create booking placeholder"})


@app.get("/api/admin/scooters")
def list_scooters_admin():
    return jsonify({"message": "Admin scooters endpoint placeholder"})


@app.get("/api/admin/revenue/weekly")
def weekly_revenue():
    return jsonify({"message": "Weekly revenue endpoint placeholder"})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=True)

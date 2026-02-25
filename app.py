from __future__ import annotations

import sqlite3
from pathlib import Path
from flask import Flask, jsonify, render_template, request

# Project structure setup
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scooter_mvp.db"

app = Flask(__name__)

# Member B: Pricing Plans Definition (as per api.md contract)
PLANS = {
    "1h": {"duration_minutes": 60, "price": "2.99"},
    "4h": {"duration_minutes": 240, "price": "8.99"},
    "1d": {"duration_minutes": 1440, "price": "19.99"},
    "1w": {"duration_minutes": 10080, "price": "79.99"}
}

def init_db() -> None:
    """Initialize database tables for all team members."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Member A: User accounts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
    """)
    
    # Member B/C: Scooter inventory table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scooters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'available' -- available, in_use, maintenance
        )
    """)
    
    # Member B: Bookings table (matching API contract fields)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scooter_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL,
            total_cost TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING_PAYMENT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (scooter_id) REFERENCES scooters (id)
        )
    """)
    
    # Seed data: Insert default scooters if table is empty
    cur.execute("SELECT COUNT(*) FROM scooters")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO scooters (code, status) VALUES (?, ?)", 
                       [("SC-001", "available"), ("SC-002", "available")])
        
    conn.commit()
    conn.close()

# --- ROUTES ---

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/health")
def health_check():
    """Service health check (Member D / General)."""
    return jsonify({"status": "ok", "framework": "flask"})

# --- AUTH ENDPOINTS (Member A) ---

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
    # Placeholder for Member A
    return jsonify({"message": "Login endpoint placeholder"})

# --- CUSTOMER ENDPOINTS (Member B - YOUR TASK) ---

@app.get("/api/customer/pricing")
def get_pricing():
    """Return available hire plans defined in the API contract."""
    plans_list = [{"plan_type": k, **v} for k, v in PLANS.items()]
    return jsonify({"plans": plans_list})

@app.post("/api/customer/bookings")
def create_booking():
    """Create a new booking for a scooter based on a selected plan."""
    payload = request.get_json(silent=True) or {}
    scooter_id = payload.get("scooter_id")
    plan_type = payload.get("plan_type")

    # Validation
    if not scooter_id or plan_type not in PLANS:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "Invalid scooter_id or plan_type"}
        }), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # Check if scooter exists and is available
        cur.execute("SELECT status FROM scooters WHERE id = ?", (scooter_id,))
        row = cur.fetchone()
        
        if not row:
            return jsonify({
                "error": {"code": "SCOOTER_NOT_FOUND", "message": "Scooter does not exist"}
            }), 404
        
        if row[0] != 'available':
            return jsonify({
                "error": {"code": "SCOOTER_UNAVAILABLE", "message": "Scooter is not available"}
            }), 409

        # Dummy user_id (to be updated once Member A completes Auth integration)
        user_id = 1 
        cost = PLANS[plan_type]["price"]

        # Transaction: Create booking and update scooter status
        cur.execute(
            "INSERT INTO bookings (user_id, scooter_id, plan_type, total_cost, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, scooter_id, plan_type, cost, 'PENDING_PAYMENT')
        )
        booking_id = cur.lastrowid
        
        cur.execute("UPDATE scooters SET status = 'in_use' WHERE id = ?", (scooter_id,))
        
        conn.commit()
        
        return jsonify({
            "booking": {
                "id": booking_id,
                "user_id": user_id,
                "scooter_id": scooter_id,
                "plan_type": plan_type,
                "status": "PENDING_PAYMENT",
                "total_cost": cost
            }
        }), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": {"code": "SERVER_ERROR", "message": str(e)}}), 500
    finally:
        conn.close()

# --- ADMIN ENDPOINTS (Member C) ---

@app.get("/api/admin/scooters")
def list_scooters_admin():
    return jsonify({"message": "Admin scooters endpoint placeholder"})

@app.get("/api/admin/revenue/weekly")
def weekly_revenue():
    return jsonify({"message": "Weekly revenue endpoint placeholder"})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=True)
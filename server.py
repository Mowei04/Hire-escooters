from __future__ import annotations

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/customer")
def customer_home():
    return render_template("customer_login.html")


@app.get("/customer/register")
def customer_register_page():
    return render_template("customer_register.html")


@app.get("/customer/login")
def customer_login_page():
    return render_template("customer_login.html")


@app.get("/customer/dashboard")
def customer_dashboard_page():
    return render_template("customer_dashboard.html")


@app.get("/admin")
def admin_page():
    return render_template("admin.html")


@app.get("/api/health")
def health_check():
    return jsonify({"status": "ok", "framework": "flask", "mode": "frontend-scaffold"})


@app.post("/api/auth/register")
def register_user():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"message": "email is required", "mock": True}), 400
    return jsonify({"message": "Register endpoint is in mock mode", "email": email, "mock": True}), 200


@app.post("/api/auth/login")
def login_user():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    role = "manager" if "manager" in email else "customer"
    return jsonify(
        {
            "token": "mock-token",
            "user": {"id": 1, "email": email or "demo@example.com", "role": role},
            "mock": True,
        }
    )


@app.get("/api/customer/pricing")
def get_pricing():
    return jsonify(
        {
            "plans": [
                {"plan_type": "1h", "duration_minutes": 60, "price": "2.99"},
                {"plan_type": "4h", "duration_minutes": 240, "price": "8.99"},
                {"plan_type": "1d", "duration_minutes": 1440, "price": "19.99"},
                {"plan_type": "1w", "duration_minutes": 10080, "price": "79.99"},
            ],
            "mock": True,
        }
    )


@app.post("/api/customer/bookings")
def create_booking():
    payload = request.get_json(silent=True) or {}
    return jsonify(
        {
            "booking": {
                "id": 1001,
                "scooter_id": payload.get("scooter_id"),
                "plan_type": payload.get("plan_type"),
                "status": "PENDING_PAYMENT",
                "total_cost": "2.99",
            },
            "mock": True,
        }
    )


@app.get("/api/admin/scooters")
def list_scooters_admin():
    return jsonify(
        {
            "items": [
                {"id": 1, "code": "SC-001", "status": "available", "location_text": "City Centre A"},
                {"id": 2, "code": "SC-002", "status": "unavailable", "location_text": "City Centre B"},
                {"id": 3, "code": "SC-003", "status": "available", "location_text": "Station"},
            ],
            "mock": True,
        }
    )


@app.get("/api/admin/revenue/weekly")
def weekly_revenue():
    return jsonify(
        {
            "week_start": "2026-02-23",
            "week_end": "2026-03-01",
            "total_revenue": "66.88",
            "by_plan": [
                {"plan_type": "1h", "revenue": "20.00"},
                {"plan_type": "4h", "revenue": "18.00"},
                {"plan_type": "1d", "revenue": "28.88"},
            ],
            "mock": True,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)

from app import app, init_db


def test_smoke_full_flow() -> None:
    app.config["TESTING"] = True
    init_db()
    client = app.test_client()

    health = client.get("/api/health")
    assert health.status_code == 200

    unauthorized = client.get("/api/customer/pricing")
    assert unauthorized.status_code == 401

    customer_login = client.post(
        "/api/auth/login",
        json={"email": "demo_user@example.com", "password": "123456"},
    )
    assert customer_login.status_code == 200

    pricing = client.get("/api/customer/pricing")
    assert pricing.status_code == 200

    admin_forbidden = client.get("/api/admin/scooters")
    assert admin_forbidden.status_code == 403

    from app import DB_PATH
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id FROM scooters WHERE status = 'available' ORDER BY id LIMIT 1").fetchone()
    conn.close()
    assert row is not None

    booking_create = client.post(
        "/api/customer/bookings",
        json={"scooter_id": row[0], "plan_type": "1h"},
    )
    assert booking_create.status_code == 201
    booking_id = booking_create.get_json()["booking"]["id"]

    booking_list = client.get("/api/customer/bookings")
    assert booking_list.status_code == 200
    assert any(item["id"] == booking_id for item in booking_list.get_json()["items"])

    booking_cancel = client.delete(f"/api/customer/bookings/{booking_id}")
    assert booking_cancel.status_code == 200

    client.post("/api/auth/logout")

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "manager@example.com", "password": "admin123"},
    )
    assert admin_login.status_code == 200

    scooters = client.get("/api/admin/scooters")
    assert scooters.status_code == 200
    scooter_id = scooters.get_json()["items"][0]["id"]

    update = client.patch(
        f"/api/admin/scooters/{scooter_id}",
        json={"status": "maintenance"},
    )
    assert update.status_code == 200
    assert update.get_json()["item"]["status"] == "maintenance"

    revenue = client.get("/api/admin/revenue/weekly")
    assert revenue.status_code == 200
    body = revenue.get_json()
    assert "total_revenue" in body
    assert "by_plan" in body

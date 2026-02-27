"""Customer flow integration tests."""

import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path

# Allow direct imports from project root when running tests standalone.
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app import DB_PATH, app, init_db


class TestMemberBCustomerFlow(unittest.TestCase):
    def setUp(self):
        """Prepare app client and initialize DB for each test."""
        app.config["TESTING"] = True
        self.client = app.test_client()
        init_db()

    def _login_customer(self):
        """Authenticate default customer test user."""
        response = self.client.post(
            "/api/auth/login",
            json={"email": "demo_user@example.com", "password": "123456"},
        )
        self.assertEqual(response.status_code, 200)

    def _login_admin(self):
        """Authenticate default admin test user."""
        response = self.client.post(
            "/api/auth/login",
            json={"email": "manager@example.com", "password": "admin123"},
        )
        self.assertEqual(response.status_code, 200)

    def _force_available_scooter(self):
        """Return an available scooter with no active bookings for deterministic tests."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id
            FROM scooters s
            LEFT JOIN bookings b
              ON b.scooter_id = s.id
             AND b.status = 'PENDING_PAYMENT'
            GROUP BY s.id
            HAVING COUNT(b.id) = 0
            ORDER BY s.id
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            code = f"TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            cur.execute(
                "INSERT INTO scooters (code, status, location_text) VALUES (?, ?, ?)",
                (code, "available", "Test Zone"),
            )
            scooter_id = cur.lastrowid
        else:
            scooter_id = row[0]
        cur.execute("UPDATE scooters SET status = 'available' WHERE id = ?", (scooter_id,))
        conn.commit()
        conn.close()
        return scooter_id

    def _set_booking_created_at_hours_ago(self, booking_id: int, hours: int):
        """Backdate booking start time to simulate expiration in tests."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE bookings SET created_at = datetime('now', ?) WHERE id = ?",
            (f"-{hours} hours", booking_id),
        )
        conn.commit()
        conn.close()

    def test_get_pricing_contract(self):
        """Pricing endpoint returns expected basic contract shape."""
        self._login_customer()
        response = self.client.get("/api/customer/pricing")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("plans", data)
        plan_types = [p["plan_type"] for p in data["plans"]]
        self.assertIn("1h", plan_types)

    def test_list_scooters_for_customer(self):
        """Customer can view scooter inventory and status for booking decisions."""
        self._login_customer()
        response = self.client.get("/api/customer/scooters")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", data)
        self.assertTrue(len(data["items"]) > 0)
        self.assertIn("status", data["items"][0])
        self.assertIn("is_available", data["items"][0])

    def test_create_booking_flow(self):
        """Customer can create a booking for an available scooter."""
        self._login_customer()

        # Find any scooter currently available for booking.
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM scooters WHERE status = 'available' LIMIT 1")
        scooter = cur.fetchone()
        conn.close()

        if not scooter:
            self.skipTest("No available scooters in DB to perform booking test")

        scooter_id = scooter[0]

        response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": scooter_id, "plan_type": "1h"},
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertIn("booking", data)
        self.assertEqual(data["booking"]["status"], "PENDING_PAYMENT")
        self.assertEqual(data["booking"]["scooter_id"], scooter_id)

    def test_booking_unavailable_scooter(self):
        """Booking must fail with 409 when scooter is not available."""
        self._login_customer()

        # Force known scooter into in_use state to simulate conflict.
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE scooters SET status = 'in_use' WHERE id = 1")
        conn.commit()
        conn.close()

        response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": 1, "plan_type": "1h"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "SCOOTER_UNAVAILABLE")

    def test_old_cancelled_bookings_hidden_by_default(self):
        """Default booking list hides old cancelled records but all-history mode can include them."""
        self._login_customer()
        scooter_id = self._force_available_scooter()

        create_response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": scooter_id, "plan_type": "1h"},
        )
        self.assertEqual(create_response.status_code, 201)
        booking_id = create_response.get_json()["booking"]["id"]

        cancel_response = self.client.delete(f"/api/customer/bookings/{booking_id}")
        self.assertEqual(cancel_response.status_code, 200)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE bookings SET created_at = datetime('now', '-120 days') WHERE id = ?", (booking_id,))
        conn.commit()
        conn.close()

        default_list = self.client.get("/api/customer/bookings")
        self.assertEqual(default_list.status_code, 200)
        default_items = default_list.get_json()["items"]
        self.assertFalse(any(item["id"] == booking_id for item in default_items))

        all_list = self.client.get("/api/customer/bookings?include_cancelled=all")
        self.assertEqual(all_list.status_code, 200)
        all_items = all_list.get_json()["items"]
        self.assertTrue(any(item["id"] == booking_id for item in all_items))

    def test_admin_cannot_set_available_with_active_booking(self):
        """Admin status update rejects forcing available while unresolved booking exists."""
        self._login_customer()
        scooter_id = self._force_available_scooter()

        create_response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": scooter_id, "plan_type": "1h"},
        )
        self.assertEqual(create_response.status_code, 201)

        self.client.post("/api/auth/logout")
        self._login_admin()

        response = self.client.patch(
            f"/api/admin/scooters/{scooter_id}",
            json={"status": "available"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "ACTIVE_BOOKING_EXISTS")

    def test_expired_booking_auto_completes_and_releases_scooter(self):
        """Expired booking is auto-completed and scooter returns to available."""
        self._login_customer()
        scooter_id = self._force_available_scooter()

        create_response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": scooter_id, "plan_type": "1h"},
        )
        self.assertEqual(create_response.status_code, 201)
        booking_id = create_response.get_json()["booking"]["id"]

        self._set_booking_created_at_hours_ago(booking_id, 3)

        # Trigger synchronization through list endpoint.
        list_response = self.client.get("/api/customer/bookings")
        self.assertEqual(list_response.status_code, 200)
        rows = list_response.get_json()["items"]
        row = next(item for item in rows if item["id"] == booking_id)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["remaining_seconds"], 0)

        scooters_response = self.client.get("/api/customer/scooters")
        self.assertEqual(scooters_response.status_code, 200)
        scooters = scooters_response.get_json()["items"]
        scooter = next(item for item in scooters if item["id"] == scooter_id)
        self.assertEqual(scooter["status"], "available")

    def test_cancel_completed_booking_is_rejected(self):
        """Completed booking cannot be cancelled again."""
        self._login_customer()
        scooter_id = self._force_available_scooter()

        create_response = self.client.post(
            "/api/customer/bookings",
            json={"scooter_id": scooter_id, "plan_type": "1h"},
        )
        booking_id = create_response.get_json()["booking"]["id"]
        self._set_booking_created_at_hours_ago(booking_id, 3)

        # Force sync first so booking becomes COMPLETED.
        self.client.get("/api/customer/bookings")

        cancel_response = self.client.delete(f"/api/customer/bookings/{booking_id}")
        self.assertEqual(cancel_response.status_code, 409)
        self.assertEqual(cancel_response.get_json()["error"]["code"], "BOOKING_ALREADY_ENDED")


if __name__ == "__main__":
    unittest.main()

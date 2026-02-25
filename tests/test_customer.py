import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from app import DB_PATH, app, init_db


class TestMemberBCustomerFlow(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        init_db()

    def _login_customer(self):
        response = self.client.post(
            "/api/auth/login",
            json={"email": "demo_user@example.com", "password": "123456"},
        )
        self.assertEqual(response.status_code, 200)

    def test_get_pricing_contract(self):
        self._login_customer()
        response = self.client.get("/api/customer/pricing")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("plans", data)
        plan_types = [p["plan_type"] for p in data["plans"]]
        self.assertIn("1h", plan_types)

    def test_create_booking_flow(self):
        self._login_customer()

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
        self._login_customer()

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


if __name__ == "__main__":
    unittest.main()

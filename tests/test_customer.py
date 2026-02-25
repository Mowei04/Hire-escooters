import unittest
import sqlite3
import os
import sys
from pathlib import Path

# Ensure the parent directory is in the path so we can import app.py
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app import app, DB_PATH

class TestMemberBCustomerFlow(unittest.TestCase):
    def setUp(self):
        """Executed before each test: Set up a clean testing environment."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Ensure the database exists and has fresh data for testing
        # In a real CI environment, you might use an in-memory database
        from app import init_db
        init_db()

    def test_get_pricing_contract(self):
        """Test if the pricing endpoint matches the API contract (api.md)."""
        response = self.client.get('/api/customer/pricing')
        data = response.get_json()
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('plans', data)
        # Check if the mandatory plan '1h' exists in the response
        plan_types = [p['plan_type'] for p in data['plans']]
        self.assertIn('1h', plan_types)

    def test_create_booking_flow(self):
        """Test the full cycle: pricing -> availability check -> booking."""
        # 1. First, check if there is an available scooter
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM scooters WHERE status = 'available' LIMIT 1")
        scooter = cur.fetchone()
        conn.close()

        if not scooter:
            self.skipTest("No available scooters in DB to perform booking test")

        scooter_id = scooter[0]

        # 2. Attempt to create a booking
        payload = {
            "scooter_id": scooter_id,
            "plan_type": "1h"
        }
        response = self.client.post('/api/customer/bookings', json=payload)
        data = response.get_json()

        # 3. Assertions based on the API Contract
        self.assertEqual(response.status_code, 201)
        self.assertIn('booking', data)
        self.assertEqual(data['booking']['status'], 'PENDING_PAYMENT')
        self.assertEqual(data['booking']['scooter_id'], scooter_id)

    def test_booking_unavailable_scooter(self):
        """Test that booking an unavailable scooter returns an error (409)."""
        # Manually set a scooter to 'in_use'
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE scooters SET status = 'in_use' WHERE id = 1")
        conn.commit()
        conn.close()

        payload = {
            "scooter_id": 1,
            "plan_type": "1h"
        }
        response = self.client.post('/api/customer/bookings', json=payload)
        
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['error']['code'], 'SCOOTER_UNAVAILABLE')

if __name__ == '__main__':
    unittest.main()
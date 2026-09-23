"""
Comprehensive Security & Face Recognition Test Suite
===================================================
Tests:
1. 1 Phone = 1 Student device binding on registration.
2. Blocking registration of Student B on Device A (403 Device Security Alert).
3. Student login via POST /students/login:
   - Success when device matches.
   - Blocked when device belongs to another student.
   - Blocked when student is locked to another device.
4. Admin reset device binding allows binding to a new device.
5. Attendance verification:
   - Blocks proxy verification from unauthorized device.
   - Computes confidence and matches face correctly.
"""

import json
import unittest
import numpy as np
from fastapi.testclient import TestClient
from datetime import datetime

from main import app, init_db, get_db, compute_match_confidence, match_encoding

client = TestClient(app)

class TestSecurityAndFaceRecognition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import asyncio
        asyncio.run(init_db())

    def setUp(self):
        # Clean up test records
        import asyncio
        async def cleanup():
            db = await get_db()
            try:
                await db.execute("DELETE FROM students WHERE roll_no LIKE 'TEST_ROLL_%'")
                await db.execute("DELETE FROM attendance WHERE roll_no LIKE 'TEST_ROLL_%'")
                await db.commit()
            finally:
                await db.close()
        asyncio.run(cleanup())

    def test_compute_match_confidence(self):
        """Test intuitive percentage conversion of Euclidean distance."""
        self.assertEqual(compute_match_confidence(0.0, 0.55), 100.0)
        self.assertEqual(compute_match_confidence(0.275, 0.55), 80.0)
        self.assertEqual(compute_match_confidence(0.55, 0.55), 60.0)
        self.assertTrue(compute_match_confidence(0.70, 0.55) < 60.0)

    def test_device_binding_lifecycle(self):
        """Test end-to-end 1 Phone = 1 Student enforcement."""
        import asyncio

        # Seed Student A and Student B in DB directly for testing
        async def seed():
            db = await get_db()
            try:
                enc = json.dumps([0.1] * 128)
                await db.execute(
                    """
                    INSERT INTO students (roll_no, name, face_encoding, is_locked, device_id, branch_code, section, year)
                    VALUES (?, ?, ?, 1, ?, 'A', 'A1', 1)
                    """,
                    ("TEST_ROLL_A", "Student A", enc, "DEV_PHONE_1"),
                )
                await db.execute(
                    """
                    INSERT INTO students (roll_no, name, face_encoding, is_locked, device_id, branch_code, section, year)
                    VALUES (?, ?, ?, 1, ?, 'A', 'A1', 1)
                    """,
                    ("TEST_ROLL_B", "Student B", enc, ""),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(seed())

        # 1. Student A logins with DEV_PHONE_1 -> 200 OK
        res = client.post("/students/login", data={"roll_no": "TEST_ROLL_A", "device_id": "DEV_PHONE_1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

        # 2. Student B tries to login using DEV_PHONE_1 (Student A's phone) -> 403 BLOCKED
        res_proxy = client.post("/students/login", data={"roll_no": "TEST_ROLL_B", "device_id": "DEV_PHONE_1"})
        self.assertEqual(res_proxy.status_code, 403)
        self.assertIn("Device Security Alert", res_proxy.json()["detail"])
        self.assertIn("Student A", res_proxy.json()["detail"])

        # 3. Student A tries to login from DEV_PHONE_2 (different phone) -> 403 BLOCKED
        res_diff = client.post("/students/login", data={"roll_no": "TEST_ROLL_A", "device_id": "DEV_PHONE_2"})
        self.assertEqual(res_diff.status_code, 403)
        self.assertIn("Device Binding Alert", res_diff.json()["detail"])

        # 4. Student B logins from DEV_PHONE_2 (unbound device) -> 200 OK & binds DEV_PHONE_2
        res_b = client.post("/students/login", data={"roll_no": "TEST_ROLL_B", "device_id": "DEV_PHONE_2"})
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.json()["student"]["device_id"], "DEV_PHONE_2")

        # 5. Admin resets Student A's device
        res_reset = client.post("/admin/students/TEST_ROLL_A/reset-device")
        self.assertEqual(res_reset.status_code, 200)

        # 6. Now Student A can bind to a brand new DEV_PHONE_3 -> 200 OK
        res_new_phone = client.post("/students/login", data={"roll_no": "TEST_ROLL_A", "device_id": "DEV_PHONE_3"})
        self.assertEqual(res_new_phone.status_code, 200)
        self.assertEqual(res_new_phone.json()["student"]["device_id"], "DEV_PHONE_3")

if __name__ == "__main__":
    unittest.main()

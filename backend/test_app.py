import unittest
from unittest.mock import MagicMock, patch

from app import create_app


class VlabApiTestCase(unittest.TestCase):
    def setUp(self):
        self.connect_patcher = patch("app.psycopg.connect")
        self.connect = self.connect_patcher.start()
        self.database = self.connect.return_value.__enter__.return_value
        self.client = create_app({"TESTING": True}).test_client()

    def tearDown(self):
        self.connect_patcher.stop()

    @staticmethod
    def cursor(row=None, rows=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        cursor.fetchall.return_value = rows
        return cursor

    def test_list_vlabs(self):
        self.database.execute.return_value = self.cursor(
            rows=[
                {"id": 1, "name": "Flight controls validation", "type": "Airbus A320", "status": "running"},
                {"id": 2, "name": "Cabin systems training", "type": "Boing 737", "status": "stopped"},
                {"id": 3, "name": "Navigation sandbox", "type": "Embraer ERJ", "status": "running"},
                {"id": 4, "name": "Legacy test environment", "type": "Airbus A320", "status": "terminated"},
            ]
        )

        response = self.client.get("/api/vlabs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 4)

    def test_list_vlab_types(self):
        self.database.execute.return_value = self.cursor(
            rows=[
                {"name": "Airbus A320"},
                {"name": "Boing 737"},
                {"name": "Embraer ERJ"},
            ]
        )

        response = self.client.get("/api/vlabtype")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), ["Airbus A320", "Boing 737", "Embraer ERJ"])

    def test_create_vlab_defaults_to_stopped(self):
        self.database.execute.side_effect = [
            self.cursor(row={"id": 1}),
            self.cursor(
                row={"id": 5, "name": "New training lab", "type": "Airbus A320", "status": "stopped"}
            ),
        ]

        response = self.client.post(
            "/api/vlabs",
            json={"name": "New training lab", "type": "Airbus A320"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["status"], "stopped")

    def test_update_vlab_status(self):
        self.database.execute.return_value = self.cursor(
            row={"id": 2, "name": "Cabin systems training", "type": "Boing 737", "status": "running"}
        )

        response = self.client.put("/api/vlabs/2", json={"status": "running"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "running")

    def test_delete_vlab(self):
        self.database.execute.return_value = self.cursor(
            row={"id": 2, "name": "Cabin systems training", "type": "Boing 737", "status": "stopped"}
        )

        response = self.client.delete("/api/vlabs/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], 2)

    def test_delete_unknown_vlab_returns_not_found(self):
        self.database.execute.return_value = self.cursor(row=None)

        response = self.client.delete("/api/vlabs/999")

        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_type_and_status(self):
        self.database.execute.return_value = self.cursor(row=None)

        create_response = self.client.post(
            "/api/vlabs",
            json={"name": "Invalid lab", "type": "Unknown"},
        )
        update_response = self.client.put("/api/vlabs/1", json={"status": "unknown"})

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(update_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

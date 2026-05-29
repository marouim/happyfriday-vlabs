import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app import create_app


class VlabApiTestCase(unittest.TestCase):
    def setUp(self):
        self.connect_patcher = patch("app.psycopg.connect")
        self.connect = self.connect_patcher.start()
        self.database = self.connect.return_value.__enter__.return_value
        self.client = create_app(
            {
                "TESTING": True,
                "AAP_BASE_URL": "https://example-aap.apps.example.com",
                "AAP_TOKEN": "test-token",
            }
        ).test_client()

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

    @patch("app.requests.post")
    def test_start_vlab_launches_start_aap_job_template(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {"job": 42}
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "aap_start_job_template_id": 10,
                    "aap_stop_job_template_id": 11,
                    "status": "stopped",
                }
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "starting",
                }
            ),
        ]

        response = self.client.put("/api/vlabs/2", json={"status": "running"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "starting")
        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://example-aap.apps.example.com/api/controller/v2/job_templates/10/launch/",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["extra_vars"],
            {
                "vlab_id": 2,
                "vlab_name": "Cabin systems training",
                "vlab_type": "Boing 737",
                "vlab_action": "start",
            },
        )

    @patch("app.requests.post")
    def test_stop_vlab_launches_stop_aap_job_template(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {"job": 43}
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "aap_start_job_template_id": 10,
                    "aap_stop_job_template_id": 11,
                    "status": "running",
                }
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "stopping",
                }
            ),
        ]

        response = self.client.put("/api/vlabs/2", json={"status": "stopped"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "stopping")
        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://example-aap.apps.example.com/api/controller/v2/job_templates/11/launch/",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["extra_vars"],
            {
                "vlab_id": 2,
                "vlab_name": "Cabin systems training",
                "vlab_type": "Boing 737",
                "vlab_action": "stop",
            },
        )

    @patch("app.requests.post")
    def test_terminate_vlab_does_not_launch_aap_job_template(self, post):
        self.database.execute.return_value = self.cursor(
            row={"id": 2, "name": "Cabin systems training", "type": "Boing 737", "status": "terminated"}
        )

        response = self.client.put("/api/vlabs/2", json={"status": "terminated"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "terminated")
        post.assert_not_called()

    @patch("app.requests.post")
    def test_start_returns_error_when_aap_launch_fails(self, post):
        post.return_value.ok = False
        post.return_value.status_code = 401
        post.return_value.text = "unauthorized"
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "aap_start_job_template_id": 8,
                    "aap_stop_job_template_id": 9,
                    "status": "stopped",
                }
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "failed",
                }
            ),
        ]

        response = self.client.put("/api/vlabs/2", json={"status": "running"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("AAP job template launch failed", response.get_json()["error"])
        self.assertEqual(response.get_json()["vlab"]["status"], "failed")

    def test_start_rejects_type_without_aap_job_template(self):
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 3,
                    "name": "Navigation sandbox",
                    "type": "Embraer ERJ",
                    "aap_start_job_template_id": None,
                    "aap_stop_job_template_id": None,
                    "status": "running",
                }
            ),
            self.cursor(
                row={
                    "id": 3,
                    "name": "Navigation sandbox",
                    "type": "Embraer ERJ",
                    "status": "failed",
                }
            ),
        ]

        response = self.client.put("/api/vlabs/3", json={"status": "running"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("No AAP start job template", response.get_json()["error"])
        self.assertEqual(response.get_json()["vlab"]["status"], "failed")

    @patch("app.requests.get")
    def test_list_vlabs_updates_successful_starting_job_to_target_status(self, get):
        get.return_value.ok = True
        get.return_value.json.return_value = {"status": "successful"}
        self.database.execute.side_effect = [
            self.cursor(
                rows=[
                    {
                        "id": 2,
                        "name": "Cabin systems training",
                        "type": "Boing 737",
                        "status": "starting",
                        "aap_job_id": 42,
                        "aap_target_status": "running",
                        "aap_last_job_status": "launched",
                    }
                ]
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "running",
                    "aap_job_id": 42,
                    "aap_target_status": None,
                    "aap_last_job_status": "successful",
                }
            ),
        ]

        response = self.client.get("/api/vlabs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["status"], "running")
        get.assert_called_once()

    @patch("app.requests.get")
    def test_list_vlabs_updates_failed_starting_job_to_failed_status(self, get):
        get.return_value.ok = True
        get.return_value.json.return_value = {"status": "failed"}
        self.database.execute.side_effect = [
            self.cursor(
                rows=[
                    {
                        "id": 2,
                        "name": "Cabin systems training",
                        "type": "Boing 737",
                        "status": "starting",
                        "aap_job_id": 42,
                        "aap_target_status": "running",
                        "aap_last_job_status": "launched",
                    }
                ]
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "failed",
                    "aap_job_id": 42,
                    "aap_target_status": None,
                    "aap_last_job_status": "failed",
                }
            ),
        ]

        response = self.client.get("/api/vlabs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["status"], "failed")
        get.assert_called_once()

    @patch("app.requests.post")
    def test_delete_vlab_launches_delete_aap_job_template(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {"job": 44}
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "aap_delete_job_template_id": 12,
                    "status": "stopped",
                }
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "deleting",
                }
            ),
        ]

        response = self.client.delete("/api/vlabs/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "deleting")
        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://example-aap.apps.example.com/api/controller/v2/job_templates/12/launch/",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["extra_vars"],
            {
                "vlab_id": 2,
                "vlab_name": "Cabin systems training",
                "vlab_type": "Boing 737",
                "vlab_action": "delete",
            },
        )

    @patch("app.requests.get")
    def test_list_vlabs_removes_successful_deleting_job(self, get):
        get.return_value.ok = True
        get.return_value.json.return_value = {"status": "successful"}
        self.database.execute.side_effect = [
            self.cursor(
                rows=[
                    {
                        "id": 2,
                        "name": "Cabin systems training",
                        "type": "Boing 737",
                        "status": "deleting",
                        "aap_job_id": 44,
                        "aap_target_status": "deleted",
                        "aap_last_job_status": "launched",
                    }
                ]
            ),
            self.cursor(),
        ]

        response = self.client.get("/api/vlabs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        get.assert_called_once()

    @patch("app.requests.post")
    def test_delete_returns_error_when_aap_launch_fails(self, post):
        post.return_value.ok = False
        post.return_value.status_code = 401
        post.return_value.text = "unauthorized"
        self.database.execute.side_effect = [
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "aap_delete_job_template_id": 12,
                    "status": "stopped",
                }
            ),
            self.cursor(
                row={
                    "id": 2,
                    "name": "Cabin systems training",
                    "type": "Boing 737",
                    "status": "failed",
                }
            ),
        ]

        response = self.client.delete("/api/vlabs/2")

        self.assertEqual(response.status_code, 502)
        self.assertIn("AAP job template launch failed", response.get_json()["error"])
        self.assertEqual(response.get_json()["vlab"]["status"], "failed")

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

    def test_list_physical_lab_locations(self):
        self.database.execute.return_value = self.cursor(
            rows=[
                {
                    "id": 1,
                    "name": "Montreal",
                    "server_capacity": 12,
                    "available_servers": 8,
                    "description": "Primary lab floor.",
                },
                {
                    "id": 2,
                    "name": "Ottawa",
                    "server_capacity": 8,
                    "available_servers": 5,
                    "description": "Secure lab space.",
                },
            ]
        )

        response = self.client.get("/api/physical-lab-locations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["name"], "Montreal")
        self.assertEqual(response.get_json()[0]["availableServers"], 8)

    def test_list_physical_lab_requests(self):
        created_at = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
        self.database.execute.return_value = self.cursor(
            rows=[
                {
                    "id": 7,
                    "requester_name": "Martin",
                    "location_id": 1,
                    "location": "Montreal",
                    "server_count": 3,
                    "purpose": "Firmware validation",
                    "status": "requested",
                    "created_at": created_at,
                }
            ]
        )

        response = self.client.get("/api/physical-lab-requests")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["requesterName"], "Martin")
        self.assertEqual(response.get_json()[0]["serverCount"], 3)
        self.assertEqual(response.get_json()[0]["createdAt"], created_at.isoformat())

    def test_create_physical_lab_request_reserves_servers(self):
        created_at = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
        self.database.execute.side_effect = [
            self.cursor(row={"id": 1, "available_servers": 8}),
            self.cursor(),
            self.cursor(
                row={
                    "id": 9,
                    "requester_name": "Martin",
                    "location_id": 1,
                    "location": "Montreal",
                    "server_count": 2,
                    "purpose": "Hardware test",
                    "status": "requested",
                    "created_at": created_at,
                }
            ),
        ]

        response = self.client.post(
            "/api/physical-lab-requests",
            json={
                "requesterName": "Martin",
                "locationId": 1,
                "serverCount": 2,
                "purpose": "Hardware test",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["status"], "requested")
        self.database.execute.assert_any_call(
            """
                UPDATE physical_lab_locations
                SET available_servers = available_servers - %s
                WHERE id = %s
                """,
            (2, 1),
        )

    def test_create_physical_lab_request_rejects_unavailable_servers(self):
        self.database.execute.return_value = self.cursor(row={"id": 1, "available_servers": 1})

        response = self.client.post(
            "/api/physical-lab-requests",
            json={
                "requesterName": "Martin",
                "locationId": 1,
                "serverCount": 2,
                "purpose": "Hardware test",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Not enough servers", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

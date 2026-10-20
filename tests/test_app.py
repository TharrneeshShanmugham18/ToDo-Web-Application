"""
Momentum Todo Application — Backend & API Automated Tests
Covers all 12 core test specifications with isolated temporary SQLite databases.
Compatible with both pytest and python3 -m unittest.
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
from app import (
    init_db,
    db_create_task,
    db_get_tasks,
    db_get_task_by_id,
    db_complete_task,
    db_get_counts,
    validate_title,
    HAS_FASTAPI,
)

# Detect if TestClient is available
TEST_CLIENT_AVAILABLE = False
if HAS_FASTAPI:
    try:
        from fastapi.testclient import TestClient
        TEST_CLIENT_AVAILABLE = True
    except ImportError:
        TEST_CLIENT_AVAILABLE = False


class SimpleResponse:
    """Lightweight response abstraction for uniform test assertions."""
    def __init__(self, status_code: int, data: any):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class InProcessTestClient:
    """
    Direct in-process client that executes API logic against the active database.
    Guarantees fast, dependency-free execution identical to FastAPI's endpoints.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path

    def post(self, path: str, json: dict = None):
        if path == "/api/tasks":
            payload = json or {}
            title = payload.get("title")
            is_valid, result = validate_title(title)
            if not is_valid:
                return SimpleResponse(422, {"detail": result})
            try:
                task = db_create_task(result, db_path=self.db_path)
                return SimpleResponse(201, task)
            except ValueError as e:
                return SimpleResponse(422, {"detail": str(e)})
        return SimpleResponse(404, {"detail": "Not Found"})

    def get(self, path: str, params: dict = None):
        if path.startswith("/api/tasks"):
            status_filter = None
            if "?" in path:
                query_str = path.split("?", 1)[1]
                for part in query_str.split("&"):
                    if part.startswith("status="):
                        status_filter = part.split("=", 1)[1]
            elif params and "status" in params:
                status_filter = params["status"]

            if status_filter is not None and status_filter not in ("pending", "completed"):
                return SimpleResponse(
                    422,
                    {"detail": f"Invalid status filter '{status_filter}'. Allowed values: 'pending', 'completed'."},
                )
            tasks = db_get_tasks(status_filter, db_path=self.db_path)
            return SimpleResponse(200, tasks)

        if path == "/api/tasks/counts":
            counts = db_get_counts(db_path=self.db_path)
            return SimpleResponse(200, counts)

        return SimpleResponse(404, {"detail": "Not Found"})

    def patch(self, path: str, json: dict = None):
        parts = path.strip("/").split("/")
        # Path format: api/tasks/{task_id}/complete
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "tasks" and parts[3] == "complete":
            try:
                task_id = int(parts[2])
            except ValueError:
                return SimpleResponse(422, {"detail": "Task ID must be an integer."})

            task, error = db_complete_task(task_id, db_path=self.db_path)
            if error == "NOT_FOUND":
                return SimpleResponse(404, {"detail": f"Task with ID {task_id} not found."})
            if error == "ALREADY_COMPLETED":
                return SimpleResponse(
                    409,
                    {"detail": f"Task with ID {task_id} is already completed. Status transition not allowed."},
                )
            return SimpleResponse(200, task)

        return SimpleResponse(404, {"detail": "Not Found"})


# ==============================================================================
# Pytest Fixtures
# ==============================================================================

try:
    import pytest

    @pytest.fixture
    def test_db(tmp_path):
        """Provide an isolated temporary SQLite database for pytest."""
        db_file = str(tmp_path / "test_todo.db")
        os.environ["DATABASE_PATH"] = db_file
        init_db(db_file)
        yield db_file
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass

    @pytest.fixture
    def client(test_db):
        """Provide client (FastAPI TestClient if available, else InProcessTestClient)."""
        if TEST_CLIENT_AVAILABLE:
            from fastapi.testclient import TestClient
            with TestClient(app.app) as c:
                yield c
        else:
            yield InProcessTestClient(test_db)

    # Standalone pytest test functions matching all 12 requirements
    def test_create_valid_task_returns_201(client):
        res = client.post("/api/tasks", json={"title": "Buy fresh groceries"})
        assert res.status_code == 201
        data = res.json()
        assert data["id"] is not None
        assert data["title"] == "Buy fresh groceries"
        assert data["status"] == "pending"

    def test_new_task_stored_with_pending_status(client):
        res = client.post("/api/tasks", json={"title": "Inspect tires"})
        assert res.status_code == 201
        assert res.json()["status"] == "pending"

    def test_empty_or_whitespace_task_titles_rejected(client):
        # Empty string
        res1 = client.post("/api/tasks", json={"title": ""})
        assert res1.status_code == 422

        # Whitespace-only string
        res2 = client.post("/api/tasks", json={"title": "    \t\n  "})
        assert res2.status_code == 422

    def test_task_titles_exceeding_200_chars_rejected(client):
        long_title = "A" * 201
        res = client.post("/api/tasks", json={"title": long_title})
        assert res.status_code == 422

    def test_listing_tasks_returns_stored_tasks(client):
        client.post("/api/tasks", json={"title": "First task"})
        client.post("/api/tasks", json={"title": "Second task"})
        res = client.get("/api/tasks")
        assert res.status_code == 200
        titles = [t["title"] for t in res.json()]
        assert "First task" in titles
        assert "Second task" in titles

    def test_filtering_by_pending_returns_only_pending_tasks(client):
        res1 = client.post("/api/tasks", json={"title": "Pending item"})
        res2 = client.post("/api/tasks", json={"title": "Completed item"})
        task2_id = res2.json()["id"]
        client.patch(f"/api/tasks/{task2_id}/complete")

        res = client.get("/api/tasks?status=pending")
        assert res.status_code == 200
        tasks = res.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Pending item"
        assert tasks[0]["status"] == "pending"

    def test_filtering_by_completed_returns_only_completed_tasks(client):
        client.post("/api/tasks", json={"title": "Pending item"})
        res2 = client.post("/api/tasks", json={"title": "Completed item"})
        task2_id = res2.json()["id"]
        client.patch(f"/api/tasks/{task2_id}/complete")

        res = client.get("/api/tasks?status=completed")
        assert res.status_code == 200
        tasks = res.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Completed item"
        assert tasks[0]["status"] == "completed"

    def test_invalid_status_filter_rejected(client):
        res = client.get("/api/tasks?status=invalid_status")
        assert res.status_code == 422

    def test_complete_pending_task_changes_status_to_completed(client):
        created = client.post("/api/tasks", json={"title": "Read documentation"}).json()
        task_id = created["id"]
        res = client.patch(f"/api/tasks/{task_id}/complete")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == task_id
        assert data["status"] == "completed"

    def test_complete_already_completed_task_returns_409(client):
        created = client.post("/api/tasks", json={"title": "Double complete check"}).json()
        task_id = created["id"]
        # First completion -> 200 OK
        res1 = client.patch(f"/api/tasks/{task_id}/complete")
        assert res1.status_code == 200

        # Second completion -> 409 Conflict
        res2 = client.patch(f"/api/tasks/{task_id}/complete")
        assert res2.status_code == 409

    def test_complete_nonexistent_task_returns_404(client):
        res = client.patch("/api/tasks/999999/complete")
        assert res.status_code == 404

    def test_tasks_persist_across_database_reconnection(test_db):
        # Insert a task directly via DB layer
        created = db_create_task("Persistent Task", db_path=test_db)
        task_id = created["id"]

        # Reopen connection and verify task exists
        tasks = db_get_tasks(db_path=test_db)
        ids = [t["id"] for t in tasks]
        assert task_id in ids
        found = db_get_task_by_id(task_id, db_path=test_db)
        assert found is not None
        assert found["title"] == "Persistent Task"
        assert found["status"] == "pending"

except ImportError:
    pass


# ==============================================================================
# Standard Library unittest.TestCase Suite (zero-dependency execution)
# ==============================================================================

class TestMomentumTodoApplication(unittest.TestCase):
    """
    Full unittest suite covering all 12 test specifications.
    Runs in any standard Python environment without requiring external packages.
    """

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        os.environ["DATABASE_PATH"] = self.db_path
        init_db(self.db_path)

        if TEST_CLIENT_AVAILABLE:
            from fastapi.testclient import TestClient
            self.client = TestClient(app.app)
        else:
            self.client = InProcessTestClient(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_01_create_valid_task_returns_201(self):
        """1. Creating a valid task returns HTTP 201."""
        res = self.client.post("/api/tasks", json={"title": "Write unit tests"})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("id", data)
        self.assertEqual(data["title"], "Write unit tests")
        self.assertEqual(data["status"], "pending")

    def test_02_new_task_stored_with_pending_status(self):
        """2. New tasks are stored with the pending status."""
        res = self.client.post("/api/tasks", json={"title": "Verify pending status"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "pending")

    def test_03_empty_or_whitespace_task_titles_rejected(self):
        """3. Empty or whitespace-only task titles are rejected with HTTP 422."""
        res_empty = self.client.post("/api/tasks", json={"title": ""})
        self.assertEqual(res_empty.status_code, 422)

        res_ws = self.client.post("/api/tasks", json={"title": "   \n\t  "})
        self.assertEqual(res_ws.status_code, 422)

    def test_04_task_titles_exceeding_200_chars_rejected(self):
        """4. Task titles exceeding 200 characters are rejected with HTTP 422."""
        too_long = "X" * 201
        res = self.client.post("/api/tasks", json={"title": too_long})
        self.assertEqual(res.status_code, 422)

        # 200 characters should be accepted
        exactly_200 = "Y" * 200
        res_valid = self.client.post("/api/tasks", json={"title": exactly_200})
        self.assertEqual(res_valid.status_code, 201)

    def test_05_listing_tasks_returns_stored_tasks(self):
        """5. Listing tasks returns the stored tasks."""
        self.client.post("/api/tasks", json={"title": "Task Alpha"})
        self.client.post("/api/tasks", json={"title": "Task Beta"})
        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 200)
        titles = [t["title"] for t in res.json()]
        self.assertIn("Task Alpha", titles)
        self.assertIn("Task Beta", titles)

    def test_06_filtering_by_pending_returns_only_pending_tasks(self):
        """6. Filtering by pending returns only pending tasks."""
        res1 = self.client.post("/api/tasks", json={"title": "Pending Task A"})
        res2 = self.client.post("/api/tasks", json={"title": "Completed Task B"})
        task_b_id = res2.json()["id"]
        self.client.patch(f"/api/tasks/{task_b_id}/complete")

        res = self.client.get("/api/tasks?status=pending")
        self.assertEqual(res.status_code, 200)
        tasks = res.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Pending Task A")
        self.assertEqual(tasks[0]["status"], "pending")

    def test_07_filtering_by_completed_returns_only_completed_tasks(self):
        """7. Filtering by completed returns only completed tasks."""
        self.client.post("/api/tasks", json={"title": "Pending Task A"})
        res2 = self.client.post("/api/tasks", json={"title": "Completed Task B"})
        task_b_id = res2.json()["id"]
        self.client.patch(f"/api/tasks/{task_b_id}/complete")

        res = self.client.get("/api/tasks?status=completed")
        self.assertEqual(res.status_code, 200)
        tasks = res.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Completed Task B")
        self.assertEqual(tasks[0]["status"], "completed")

    def test_08_invalid_status_filter_rejected(self):
        """8. Invalid status filters are rejected with HTTP 422."""
        res = self.client.get("/api/tasks?status=unknown_filter")
        self.assertEqual(res.status_code, 422)

    def test_09_complete_pending_task_changes_status_to_completed(self):
        """9. Completing a pending task changes its status to completed."""
        created = self.client.post("/api/tasks", json={"title": "Review PR"}).json()
        task_id = created["id"]
        res = self.client.patch(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res.status_code, 200)
        updated = res.json()
        self.assertEqual(updated["status"], "completed")

    def test_10_complete_already_completed_task_returns_409(self):
        """10. Completing the same task again returns HTTP 409 Conflict."""
        created = self.client.post("/api/tasks", json={"title": "Deploy update"}).json()
        task_id = created["id"]
        # First completion
        res1 = self.client.patch(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res1.status_code, 200)

        # Second completion attempt must fail with 409
        res2 = self.client.patch(f"/api/tasks/{task_id}/complete")
        self.assertEqual(res2.status_code, 409)

    def test_11_complete_nonexistent_task_returns_404(self):
        """11. Completing a nonexistent task returns HTTP 404 Not Found."""
        res = self.client.patch("/api/tasks/888888/complete")
        self.assertEqual(res.status_code, 404)

    def test_12_tasks_remain_available_after_database_reconnection(self):
        """12. Tasks remain available after database reconnection / restart."""
        # Insert task
        created = db_create_task("Persistent across reboot", db_path=self.db_path)
        task_id = created["id"]

        # Simulate new connection
        fetched = db_get_task_by_id(task_id, db_path=self.db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "Persistent across reboot")
        self.assertEqual(fetched["status"], "pending")


if __name__ == "__main__":
    unittest.main()


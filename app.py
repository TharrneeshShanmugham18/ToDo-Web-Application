"""
Momentum Todo Application — Modular Monolith Backend
FastAPI + SQLite + Static Frontend Server
"""

import os
import sys
import json
import sqlite3
import mimetypes
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "todo.db")
DATABASE_PATH = os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
STATIC_DIR = os.path.join(BASE_DIR, "static")

# ==============================================================================
# Database Layer
# ==============================================================================

def get_db_path() -> str:
    """Return the active database path from environment or default."""
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establish a connection to the SQLite database with row factory."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Create tasks table and required indexes if they do not exist."""
    path = db_path or get_db_path()
    with get_db_connection(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'completed')) DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """)
        conn.commit()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an SQLite Row to a standard Python dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def validate_title(title: Any) -> Tuple[bool, str]:
    """Validate task title: must be a non-empty string <= 200 characters."""
    if title is None or not isinstance(title, str):
        return False, "Task title is mandatory and must be a string."
    cleaned = title.strip()
    if not cleaned:
        return False, "Task title cannot be empty or whitespace only."
    if len(cleaned) > 200:
        return False, "Task title must not exceed 200 characters."
    return True, cleaned


def db_create_task(title: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a new task with status 'pending' and current timestamp."""
    is_valid, cleaned_title = validate_title(title)
    if not is_valid:
        raise ValueError(cleaned_title)

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
            (cleaned_title, now_iso),
        )
        task_id = cursor.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_dict(row)


def db_get_tasks(status: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve tasks optionally filtered by status, newest first."""
    if status is not None and status not in ("pending", "completed"):
        raise ValueError(f"Invalid status filter '{status}'. Allowed values: 'pending', 'completed'.")

    with get_db_connection(db_path) as conn:
        if status:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC",
                (status,),
            )
        else:
            cursor = conn.execute("SELECT * FROM tasks ORDER BY id DESC")
        return [row_to_dict(r) for r in cursor.fetchall()]


def db_get_task_by_id(task_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single task by its primary key ID."""
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_dict(row) if row else None


def db_complete_task(task_id: int, db_path: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Complete a pending task.
    Returns (task_dict, None) on success.
    Returns (None, "NOT_FOUND") if task does not exist.
    Returns (None, "ALREADY_COMPLETED") if task status is already 'completed'.
    """
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None, "NOT_FOUND"

        if row["status"] == "completed":
            return None, "ALREADY_COMPLETED"

        conn.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
        conn.commit()

        updated_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_dict(updated_row), None


def db_get_counts(db_path: Optional[str] = None) -> Dict[str, int]:
    """Retrieve counts for all, pending, and completed tasks."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
        counts = {"total": 0, "pending": 0, "completed": 0}
        for row in cursor.fetchall():
            s = row["status"]
            c = row["count"]
            if s in counts:
                counts[s] = c
            counts["total"] += c
        return counts


# ==============================================================================
# FastAPI Application
# ==============================================================================

try:
    from fastapi import FastAPI, HTTPException, Query, status as http_status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field, field_validator
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


if HAS_FASTAPI:
    app = FastAPI(
        title="Momentum Todo API",
        description=(
            "A fast, modern Todo Task Manager REST API with enforced "
            "status-transition rules (pending -> completed)."
        ),
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class TaskCreateRequest(BaseModel):
        title: str = Field(..., description="Task title (1-200 characters)")

        @field_validator("title")
        @classmethod
        def validate_title_content(cls, v: str) -> str:
            if not isinstance(v, str):
                raise ValueError("Task title must be a string")
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Task title cannot be empty or whitespace only")
            if len(cleaned) > 200:
                raise ValueError("Task title must not exceed 200 characters")
            return cleaned

    @app.on_event("startup")
    def on_startup():
        init_db()

    @app.post("/api/tasks", status_code=http_status.HTTP_201_CREATED)
    def api_create_task(payload: TaskCreateRequest):
        """Create a new pending task."""
        try:
            task = db_create_task(payload.title)
            return task
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    @app.get("/api/tasks")
    def api_get_tasks(status: Optional[str] = Query(None, description="Filter by status: pending or completed")):
        """List tasks, optionally filtered by status."""
        if status is not None and status not in ("pending", "completed"):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status filter '{status}'. Allowed values are 'pending' or 'completed'.",
            )
        return db_get_tasks(status)

    @app.get("/api/tasks/counts")
    def api_get_task_counts():
        """Get summary statistics for tasks."""
        return db_get_counts()

    @app.patch("/api/tasks/{task_id}/complete")
    def api_complete_task(task_id: int):
        """Complete a pending task. Enforces status transition rule."""
        task, error = db_complete_task(task_id)
        if error == "NOT_FOUND":
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )
        if error == "ALREADY_COMPLETED":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Task with ID {task_id} is already completed. Status transition not allowed.",
            )
        return task

    # Serve static assets and index.html
    if os.path.exists(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse({"message": "Momentum Todo API is active. Static files not yet deployed."})

    @app.get("/style.css", include_in_schema=False)
    def serve_direct_style():
        return FileResponse(os.path.join(STATIC_DIR, "style.css"), media_type="text/css")

    @app.get("/script.js", include_in_schema=False)
    def serve_direct_script():
        return FileResponse(os.path.join(STATIC_DIR, "script.js"), media_type="application/javascript")

else:
    app = None


# ==============================================================================
# Standard Library HTTP Server Fallback (Runs without dependencies)
# ==============================================================================

import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler


class StandardLibraryTodoHandler(BaseHTTPRequestHandler):
    """Reliable fallback HTTP request handler implementing the REST API & static file serving."""

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, file_path: str, default_content_type: Optional[str] = None):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return self._send_json(404, {"detail": f"File not found: {os.path.basename(file_path)}"})

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            content_type = default_content_type
            if not content_type:
                guessed, _ = mimetypes.guess_type(file_path)
                content_type = guessed or "application/octet-stream"
                if "css" in content_type:
                    content_type = "text/css; charset=utf-8"
                elif "javascript" in content_type:
                    content_type = "application/javascript; charset=utf-8"
                elif "html" in content_type:
                    content_type = "text/html; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_json(500, {"detail": f"Error serving file: {str(e)}"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Ignore favicon noise
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # Dashboard HTML
        if path in ("/", "/index.html"):
            index_path = os.path.join(STATIC_DIR, "index.html")
            return self._serve_file(index_path, "text/html; charset=utf-8")

        # API Endpoints
        if path == "/api/tasks/counts":
            return self._send_json(200, db_get_counts())

        if path == "/api/tasks":
            status_param = query.get("status", [None])[0]
            if status_param is not None and status_param not in ("pending", "completed"):
                return self._send_json(
                    422,
                    {"detail": f"Invalid status filter '{status_param}'. Allowed values: 'pending', 'completed'."},
                )
            tasks = db_get_tasks(status_param)
            return self._send_json(200, tasks)

        if path == "/docs":
            docs_html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Momentum Todo API Documentation</title>
<style>
body { font-family: system-ui, -apple-system, sans-serif; padding: 2rem; line-height: 1.6; background: #f8fafc; color: #1e293b; max-width: 800px; margin: 0 auto; }
code { background: #ede9fe; color: #5b21b6; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 0.9em; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
.badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; margin-right: 8px; }
.get { background: #0284c7; color: #fff; } .post { background: #16a34a; color: #fff; } .patch { background: #d97706; color: #fff; }
h1 { color: #4338ca; font-size: 1.8rem; margin-bottom: 0.5rem; }
.btn { display: inline-block; background: #4f46e5; color: #fff; text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; margin-top: 1rem; }
</style></head><body>
<h1>Momentum Todo API Documentation</h1>
<p>Standalone API Server active. (FastAPI Swagger UI available when running under Uvicorn).</p>
<div class="card"><h3><span class="badge get">GET</span>/api/tasks</h3><p>List tasks. Optional query param: <code>?status=pending</code> or <code>?status=completed</code>.</p></div>
<div class="card"><h3><span class="badge post">POST</span>/api/tasks</h3><p>Create a pending task. Request body: <code>{"title": "Task description"}</code>. Enforces 1-200 non-empty characters.</p></div>
<div class="card"><h3><span class="badge patch">PATCH</span>/api/tasks/{task_id}/complete</h3><p>Transitions status from <code>pending</code> to <code>completed</code>. Returns <code>409 Conflict</code> if already completed, <code>404 Not Found</code> if task does not exist.</p></div>
<div class="card"><h3><span class="badge get">GET</span>/api/tasks/counts</h3><p>Returns statistics: <code>{"total": N, "pending": N, "completed": N}</code>.</p></div>
<a href="/" class="btn">&larr; Return to Dashboard</a>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(docs_html.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(docs_html.encode("utf-8"))
            return

        # Static Assets (/static/style.css, /static/script.js, etc.)
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):].lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)
            return self._serve_file(file_path)

        # Direct asset fallback (/style.css, /script.js)
        direct_file = os.path.join(STATIC_DIR, path.lstrip("/"))
        if os.path.exists(direct_file) and os.path.isfile(direct_file):
            return self._serve_file(direct_file)

        self._send_json(404, {"detail": f"Path not found: {path}"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/tasks":
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                return self._send_json(422, {"detail": "Invalid JSON payload."})

            if not isinstance(payload, dict) or "title" not in payload:
                return self._send_json(422, {"detail": "Task title is mandatory and must be a string."})

            is_valid, result = validate_title(payload.get("title"))
            if not is_valid:
                return self._send_json(422, {"detail": result})

            try:
                task = db_create_task(result)
                return self._send_json(201, task)
            except ValueError as e:
                return self._send_json(422, {"detail": str(e)})

        self._send_json(404, {"detail": "Not Found"})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        # Expected: api/tasks/{id}/complete
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "tasks" and parts[3] == "complete":
            try:
                task_id = int(parts[2])
            except ValueError:
                return self._send_json(422, {"detail": "Task ID must be an integer."})

            task, error = db_complete_task(task_id)
            if error == "NOT_FOUND":
                return self._send_json(404, {"detail": f"Task with ID {task_id} not found."})
            if error == "ALREADY_COMPLETED":
                return self._send_json(
                    409,
                    {"detail": f"Task with ID {task_id} is already completed. Status transition not allowed."},
                )
            return self._send_json(200, task)

        self._send_json(404, {"detail": "Not Found"})


def run_standalone_server(port: int = 8000, host: str = "127.0.0.1"):
    """Run server using Python's built-in HTTP server."""
    init_db()
    server_address = (host, port)
    httpd = HTTPServer(server_address, StandardLibraryTodoHandler)
    print(f"\n=======================================================")
    print(f" Momentum Todo Application is running!")
    print(f" URL: http://{host}:{port}")
    print(f" API Docs: http://{host}:{port}/docs")
    print(f" Mode: Built-in standard library server")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")

    if HAS_FASTAPI:
        try:
            import uvicorn
            print(f"Starting Uvicorn server with FastAPI on http://{host}:{port}...")
            uvicorn.run("app:app", host=host, port=port, reload=True)
        except ImportError:
            run_standalone_server(port=port, host=host)
    else:
        run_standalone_server(port=port, host=host)

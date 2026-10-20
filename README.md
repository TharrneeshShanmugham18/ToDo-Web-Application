# Momentum — Todo Task Manager

A fast, lightweight, and modern full-stack Todo application built with **FastAPI**, **SQLite**, and **vanilla HTML5/CSS3/JavaScript**.

Momentum is designed around a strict status-transition rule (`pending → completed`), real-time statistics counters, client-side input validation, dynamic status filtering, and an energetic, responsive UI.

---

## 🚀 Key Features

1. **Add Tasks**:
   - Mandatory title between 1 and 200 characters.
   - Automatic trimming of whitespace; rejects empty or whitespace-only titles.
   - Initial status set to `pending`.
   - Creation timestamp recorded and stored in SQLite.
   - Client-side character counter (`0/200`) with real-time feedback.
2. **List Tasks**:
   - Clean, modern card layout displaying task title, status badge, creation date/time, and task ID.
   - Complete button displayed only for pending tasks.
   - Friendly empty states for both new databases and empty filter results.
3. **Complete Tasks**:
   - One-click completion marking a task as `completed`.
   - Immediate visual feedback and celebratory toast notification.
   - Visually distinct completed state (subtle strikethrough and emerald badge).
4. **Filter Tasks**:
   - Segmented filter controls: **All Tasks**, **Pending**, and **Completed**.
   - Filters communicate with the backend (`GET /api/tasks?status=...`).
   - Task counts for Total, Pending, and Completed stay in sync.
5. **Strict Status-Transition Rule**:
   - Only `pending → completed` is allowed.
   - Terminal state: completed tasks cannot be reopened or edited.
   - Completing an already completed task returns `HTTP 409 Conflict`.
   - Completing a nonexistent task returns `HTTP 404 Not Found`.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+ with **FastAPI**
- **Server**: **Uvicorn** (ASGI server) with automatic reload
- **Database**: **SQLite** (local file `todo.db`, automatically created on startup)
- **Frontend**: Vanilla **HTML5**, **CSS3**, and **JavaScript** (ES6+ Fetch API)
- **Testing**: **pytest** and Python's built-in **unittest**

> **Zero Extra Dependencies Required to Run**: The application includes a self-contained fallback server using Python's standard library. You can run it immediately with Python 3, or install the packages in `requirements.txt` for full FastAPI + Uvicorn + Pytest execution.

---

## 📁 Project Structure

```
.
├── app.py              # FastAPI routes, task validation, business logic, and SQLite operations
├── static/
│   ├── index.html      # Semantic HTML5 layout and page structure
│   ├── style.css       # Modern dark/vibrant styling, animations, and responsive media queries
│   └── script.js       # Asynchronous Fetch API client, state management, and DOM updates
├── tests/
│   └── test_app.py     # 12 automated test cases with isolated temporary SQLite databases
├── requirements.txt    # Python dependencies
├── README.md           # Setup, documentation, and architecture
└── .gitignore          # Version control ignore rules
```

---

## 💻 Installation & Quickstart

### Prerequisites
- Python 3.8 or higher installed on your system (`python3 --version` or `python --version`).

### 1. Create and Activate a Virtual Environment

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Application

**Option A (FastAPI via Uvicorn):**
```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

**Option B (Direct execution):**
```bash
python3 app.py
```
*(On Windows: `python app.py`)*

### 4. Open in Your Browser

- **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 Running Automated Tests

The test suite covers all 12 core requirements:
1. Creating a valid task returns HTTP 201.
2. New tasks are stored with the `pending` status.
3. Empty or whitespace-only task titles are rejected with HTTP 422.
4. Task titles exceeding 200 characters are rejected with HTTP 422.
5. Listing tasks returns all stored tasks.
6. Filtering by `pending` returns only pending tasks.
7. Filtering by `completed` returns only completed tasks.
8. Invalid status filters are rejected with HTTP 422.
9. Completing a pending task changes status to `completed`.
10. Completing an already completed task returns HTTP 409 Conflict.
11. Completing a nonexistent task returns HTTP 404 Not Found.
12. Tasks persist across database reconnections and server restarts.

### Run with pytest:
```bash
pytest tests/test_app.py -v
```

### Run with Python's built-in test runner (no dependencies needed):
```bash
python3 tests/test_app.py -v
```
*(On Windows: `python tests/test_app.py -v`)*

---

## 🔒 The Status-Transition Rule

The business rules strictly enforce the state machine:

$$\text{pending} \xrightarrow{\text{PATCH /complete}} \text{completed}$$

- **Creation**: Every task is created with the `pending` status.
- **Completion**: Only a task currently in `pending` can transition to `completed`.
- **Terminal State**: `completed` is a final, terminal state. Completed tasks cannot be modified back to `pending`.
- **Conflict Handling**: Any attempt to complete a task that is already completed triggers an immediate `409 Conflict` response with an explanatory message.
- **Safety**: There is no unrestricted status-update route (e.g. `PUT /tasks/{id}` allowing arbitrary status payload), preventing clients from bypassing the transition invariant.

---

## 🔌 API Endpoints Reference

### 1. Create a Task
- **Endpoint**: `POST /api/tasks`
- **Request Body**:
  ```json
  {
    "title": "Finish presentation slides"
  }
  ```
- **Response (`201 Created`)**:
  ```json
  {
    "id": 1,
    "title": "Finish presentation slides",
    "status": "pending",
    "created_at": "2026-10-20T10:00:00.000000+00:00"
  }
  ```

### 2. List Tasks / Filter by Status
- **Endpoint**: `GET /api/tasks`
- **Query Parameters**:
  - `status` (optional): `pending` or `completed`
- **Examples**:
  - `GET /api/tasks`
  - `GET /api/tasks?status=pending`
  - `GET /api/tasks?status=completed`
- **Response (`200 OK`)**:
  ```json
  [
    {
      "id": 1,
      "title": "Finish presentation slides",
      "status": "pending",
      "created_at": "2026-10-20T10:00:00.000000+00:00"
    }
  ]
  ```

### 3. Complete a Task
- **Endpoint**: `PATCH /api/tasks/{task_id}/complete`
- **Response (`200 OK`)**:
  ```json
  {
    "id": 1,
    "title": "Finish presentation slides",
    "status": "completed",
    "created_at": "2026-10-20T10:00:00.000000+00:00"
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Task does not exist.
  - `409 Conflict`: Task is already completed.

### 4. Get Task Statistics
- **Endpoint**: `GET /api/tasks/counts`
- **Response (`200 OK`)**:
  ```json
  {
    "total": 3,
    "pending": 2,
    "completed": 1
  }
  ```

---

## 🏛️ Application Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│                   Web Browser (Client)                 │
│   • Semantic HTML5 & Modern CSS3 Dashboard             │
│   • Asynchronous Fetch API (JSON requests/responses)   │
│   • Real-time counters & toast notifications           │
└───────────────────────────▲────────────────────────────┘
                            │ HTTP GET / POST / PATCH
                            ▼
┌────────────────────────────────────────────────────────┐
│                  FastAPI / Uvicorn                     │
│   • Serves static assets at root (/) and /static       │
│   • REST API routing (/api/tasks)                      │
│   • Input validation (Pydantic models, title lengths)  │
│   • Status transition enforcement (pending -> complete)│
└───────────────────────────▲────────────────────────────┘
                            │ Parameterized SQL queries
                            ▼
┌────────────────────────────────────────────────────────┐
│                   SQLite Database                      │
│   • Table: tasks (id, title, status, created_at)       │
│   • CHECK constraint: status IN ('pending','completed')│
│   • Persistent local storage (todo.db)                 │
└────────────────────────────────────────────────────────┘
```

1. **Browser Layer**: When the user opens `http://127.0.0.1:8000`, the server delivers `index.html`, `style.css`, and `script.js`. The UI immediately requests `/api/tasks` and `/api/tasks/counts` asynchronously to populate the dashboard.
2. **Interaction Layer**:
   - Submitting a title invokes `handleAddTask()` which disables the submit button to prevent double-submits, performs client-side length checks, and sends a `POST /api/tasks` request.
   - Clicking "Complete" sends a `PATCH /api/tasks/{id}/complete` request.
   - Clicking a filter pill updates the active state and requests `/api/tasks?status=...`.
3. **Backend & Validation Layer**:
   - FastAPI (and the Pydantic validator) strips whitespace and asserts `1 <= len(title) <= 200`.
   - Status filters are checked against `("pending", "completed")`.
   - In `PATCH /api/tasks/{task_id}/complete`, the task is inspected. If missing, a `404` is returned; if already `completed`, a `409 Conflict` is returned; otherwise, an SQL update updates the status to `completed`.
4. **Persistence Layer**: All operations use parameterized SQLite queries (`?` place-holders) preventing SQL injection. Table creation and indexes are executed automatically during startup.


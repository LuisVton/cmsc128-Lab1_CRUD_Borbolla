# CMSC 128 Lab 1 — TaskFlow

A Basic CRUD To-Do List built with **HTML + CSS + JavaScript + Flask (Python) + SQLite**.

The implementation follows the laboratory guide: tasks have a title, due date/time, priority, and tag; tasks can be edited, deleted with confirmation, and marked done. Data is stored in SQLite so it survives browser refreshes and application restarts.

## Features

### Minimum requirements
- View all tasks
- Create task
- Edit task
- Delete task with confirmation
- Mark task as done
- SQLite persistence

### Expanded requirements implemented
1. **Filter and Sort**
   - Filter by Tag
   - Filter by Priority
   - Search by title
   - Sort by Date Added
   - Sort by Due Date
   - Sort by Priority
   - Sort by Tag
2. **Calendar View**
   - Monthly calendar
   - Dates with tasks are marked
   - Clicking a date shows its tasks

## Project structure

```text
cmsc128_todo_flask/
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
├── todo.db                 # generated automatically; do not commit
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js
```

## Setup

1. Install Python 3.
2. Open a terminal in this project folder.
3. Create a virtual environment:

```bash
python -m venv .venv
```

4. Activate it.

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

Windows CMD:
```cmd
.venv\Scripts\activate
```

5. Install Flask:

```bash
pip install -r requirements.txt
```

6. Start the application:

```bash
python app.py
```

7. Open the local address shown by Flask, normally:

```text
http://127.0.0.1:5000
```

The `todo.db` SQLite database is created automatically the first time the application starts.

## API operations

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/tasks` | Read all tasks |
| POST | `/api/tasks` | Create a task |
| PUT | `/api/tasks/<id>` | Update a task |
| PATCH | `/api/tasks/<id>/complete` | Toggle completed status |
| DELETE | `/api/tasks/<id>` | Delete a task |

Example task JSON:

```json
{
  "title": "Finish database report",
  "due_date": "2026-09-10T18:00",
  "priority": "High",
  "tag": "School"
}
```

## Database design

The `tasks` table contains:

- `id` — unique identifier
- `title` — task name
- `due_date` — due date and time
- `priority` — Low, Med, or High
- `tag` — School, Personal, or Others
- `completed` — 0 for active, 1 for completed
- `created_at` — timestamp used for Date Added sorting

## CRUD flow

**Create:** HTML form → JavaScript `fetch()` POST → Flask route → SQLite INSERT → JSON response → UI refresh.

**Read:** Page loads → JavaScript `fetch()` GET → Flask SELECT query → JSON → tasks rendered in the browser.

**Update:** Edit button → form is filled → JavaScript PUT → Flask UPDATE → SQLite → UI refresh.

**Delete:** Delete button → JavaScript confirmation dialog → DELETE request → Flask DELETE → SQLite → UI refresh.

**Done:** Checkbox → PATCH request → Flask toggles `completed` → SQLite UPDATE → UI refresh.

## Why this stack?

HTML/CSS/JavaScript provide a straightforward web interface, Flask provides a lightweight Python backend and REST-style routes, and SQLite provides a simple persistent database appropriate for a small CRUD application. This stack is also easy to extend later with login and per-user task ownership.

## GitHub

The laboratory guide asks for a public repository named:

`cmsc128-Lab1_CRUD_<Lastname>`

Before submission, add screenshots of the working application to this README and commit the final version using the required commit message:

`cmsc128-Indiv-Act1-finalX`

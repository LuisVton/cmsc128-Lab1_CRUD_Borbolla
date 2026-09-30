from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = "todo.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL CHECK(priority IN ('Low','Med','High')),
            tag TEXT NOT NULL CHECK(tag IN ('School','Personal','Others')),
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL
        )
    """)

    # Add deleted_at to an existing database if the column
    # does not already exist.
    try:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN deleted_at TEXT DEFAULT NULL"
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    conn.commit()
    conn.close()


# ============================================================
# DELETE CLEANUP
# ============================================================

def cleanup_deleted_tasks():
    """
    Permanently delete tasks whose 5-second Undo period
    has already expired.
    """
    conn = get_db()

    conn.execute("""
        DELETE FROM tasks
        WHERE deleted_at IS NOT NULL
        AND datetime(deleted_at, '+5 seconds') <= datetime('now')
    """)

    conn.commit()
    conn.close()


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# GET ALL TASKS
# ============================================================

@app.get("/api/tasks")
def get_tasks():
    # Permanently remove expired deleted tasks first.
    cleanup_deleted_tasks()

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM tasks
        WHERE deleted_at IS NULL
        ORDER BY due_date ASC
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


# ============================================================
# CREATE TASK
# ============================================================

@app.post("/api/tasks")
def create_task():
    data = request.get_json()

    title = data.get("title", "").strip()
    due_date = data.get("due_date", "").strip()
    priority = data.get("priority", "")
    tag = data.get("tag", "")

    if (
        not title
        or not due_date
        or priority not in ("Low", "Med", "High")
        or tag not in ("School", "Personal", "Others")
    ):
        return jsonify({
            "error": "Please provide valid task details."
        }), 400

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO tasks
        (title, due_date, priority, tag, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            title,
            due_date,
            priority,
            tag,
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()

    task_id = cursor.lastrowid

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(row)), 201


# ============================================================
# UPDATE TASK
# ============================================================

@app.put("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json()

    title = data.get("title", "").strip()
    due_date = data.get("due_date", "").strip()
    priority = data.get("priority", "")
    tag = data.get("tag", "")

    if (
        not title
        or not due_date
        or priority not in ("Low", "Med", "High")
        or tag not in ("School", "Personal", "Others")
    ):
        return jsonify({
            "error": "Please provide valid task details."
        }), 400

    conn = get_db()

    cursor = conn.execute(
        """
        UPDATE tasks
        SET title = ?,
            due_date = ?,
            priority = ?,
            tag = ?
        WHERE id = ?
        AND deleted_at IS NULL
        """,
        (
            title,
            due_date,
            priority,
            tag,
            task_id
        )
    )

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({
            "error": "Task not found."
        }), 404

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(row))


# ============================================================
# MARK DONE / UNDONE
# ============================================================

@app.patch("/api/tasks/<int:task_id>/complete")
def toggle_complete(task_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT completed
        FROM tasks
        WHERE id = ?
        AND deleted_at IS NULL
        """,
        (task_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({
            "error": "Task not found."
        }), 404

    new_value = 0 if row["completed"] else 1

    conn.execute(
        """
        UPDATE tasks
        SET completed = ?
        WHERE id = ?
        """,
        (new_value, task_id)
    )

    conn.commit()

    updated = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(updated))


# ============================================================
# DELETE TASK — TEMPORARY
# ============================================================

@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    """
    Does NOT permanently delete the task.

    Instead, deleted_at is set to the current time.
    This gives the user 5 seconds to click Undo.
    """

    conn = get_db()

    cursor = conn.execute(
        """
        UPDATE tasks
        SET deleted_at = datetime('now')
        WHERE id = ?
        AND deleted_at IS NULL
        """,
        (task_id,)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({
            "error": "Task not found."
        }), 404

    return jsonify({
        "message": "Task deleted. You have 5 seconds to undo."
    })


# ============================================================
# UNDO DELETE
# ============================================================

@app.post("/api/tasks/<int:task_id>/undo")
def undo_delete(task_id):
    """
    Restores a recently deleted task.
    """

    conn = get_db()

    cursor = conn.execute(
        """
        UPDATE tasks
        SET deleted_at = NULL
        WHERE id = ?
        AND deleted_at IS NOT NULL
        AND datetime(deleted_at, '+5 seconds') > datetime('now')
        """,
        (task_id,)
    )

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()

        return jsonify({
            "error": "Undo period has expired or task was not found."
        }), 404

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(row))


# ============================================================
# FINALIZE DELETE
# ============================================================

@app.delete("/api/tasks/<int:task_id>/finalize")
def finalize_delete(task_id):
    """
    Permanently deletes a task after the Undo period.
    """

    conn = get_db()

    cursor = conn.execute(
        """
        DELETE FROM tasks
        WHERE id = ?
        AND deleted_at IS NOT NULL
        """,
        (task_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Task permanently deleted."
    })


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
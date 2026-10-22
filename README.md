# CMSC 128 — Activity 3: Multi-Account CRUD (UBAC)

An integration of the **Activity 1 TaskFlow CRUD** app (main) and **Activity 2 Accounts** app (act2-accounts). Stack: HTML/CSS/vanilla JavaScript, Flask, SQLite.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Windows: copy .env.example .env
python app.py
```

Open http://127.0.0.1:5000, register two users **using `/register`**, then log in and create 3–5 tasks for each user. Do not prepopulate account passwords or commit `instance/app.db`. For production, set a long random `SECRET_KEY` in `.env`, configure HTTPS and `SESSION_COOKIE_SECURE=1`, and disable debug mode. The app generates and persists a secret key in `instance/secret_key` if none is configured.

SQLite database: `instance/app.db`. Use **VS Code SQLite Viewer** or **DB Browser for SQLite** to inspect `users`, `lists`, `list_members`, and `tasks`. `users.password_hash` contains salted hashes, not plaintext passwords. Never share the database or `.env` publicly.

## Integration and merge approach

The integrated files were built from the provided `main` and `act2-accounts` ZIP snapshots. Activity 2's `app.py`, `auth.py`, `db.py`, `mailer.py`, and account templates are retained. Activity 1's task page, styling, and JavaScript were copied to `templates/tasks.html`, `static/tasks.css`, and `static/tasks.js`, adapted to support selected lists, CSRF headers, and user sessions. `tasks.py` contains the integrated CRUD and access checks. Conflicting app entry points and `/` routes were resolved by keeping Activity 2's app factory and auth blueprint, registering a new tasks blueprint, and redirecting authenticated users to `/dashboard`. Activity 1's globally accessible `tasks` table was replaced by user-linked tasks.



## Schema

- `users(id, username, email, display_name, password_hash, session_version, created_at)`: Activity 2 accounts.
- `password_resets`: Activity 2 password recovery tokens.
- `lists(id, owner_id → users.id, name, kind)`: one personal list per user (partial unique index), any number of collaborative lists.
- `list_members(list_id → lists.id, user_id → users.id)`: composite primary key, collaborative membership only.
- `tasks(id, list_id → lists.id, user_id → users.id, title, due_date, priority, tag, completed, created_at, deleted_at)`: `user_id` is the task creator; `list_id` identifies the access-controlled container. All foreign keys use SQLite `PRAGMA foreign_keys=ON`.

Personal list access is restricted to its owner. Collaborative list access is granted to the owner or an explicitly invited member. Members may create/edit/complete/delete tasks within the shared list; only the list owner can invite/remove other members or delete the list. Tasks do not duplicate usernames, emails, or password hashes.

## Endpoints and authorization

| Method | Endpoint | Authorization |
|---|---|---|
| GET | `/dashboard` | Signed-in user |
| GET | `/api/lists` | Only owned/member lists |
| POST | `/api/lists` | Create collaborative list as owner |
| GET, DELETE | `/api/lists/<id>` | GET owner/member; DELETE owner only, collaborative only |
| GET, POST | `/api/lists/<id>/members` | GET owner/member; POST owner only |
| DELETE | `/api/lists/<id>/members/<user_id>` | Owner can remove members; member can leave |
| GET, POST | `/api/tasks?list_id=<id>`, `/api/tasks` | Filter by authorized list; POST body includes `list_id` |
| GET, PUT, DELETE | `/api/tasks/<id>` | `task_access()` checks list owner or membership |
| PATCH | `/api/tasks/<id>/complete` | Same membership check |
| POST | `/api/tasks/<id>/undo` | Same membership check; 5-second window |
| DELETE | `/api/tasks/<id>/finalize` | Same membership check |

All API mutations require `X-CSRF-Token` matching the session token (included in the dashboard meta tag); account form POSTs use hidden `_csrf` inputs. Requests for inaccessible task/list IDs return **404**. Parameterized SQL protects against injection. Login reuses Activity 2 password hashing, cookie session, session-version invalidation, and login session rotation. Flask session cookies persist for seven days; the signing secret is persistent across restarts. `Cache-Control: no-store` reduces browser-back leakage after logout.

SQLite has no native PostgreSQL-style row-level security; the equivalent here is **server-side ownership/membership filtering** on every data operation.

## Tests and defense

```bash
python -m unittest discover -s tests -v
```


**Trace an IDOR:** `GET /api/tasks/42` → `task_access(42)` → SQL joins `tasks` to `lists` and requires `lists.owner_id = session user ID` **or** membership in `list_members` → if no row matches, 404 without exposing task data. The same function protects update, complete, delete, undo, and finalize. An authenticated user's ID comes from Activity 2's verified session, never from the browser's JSON body.

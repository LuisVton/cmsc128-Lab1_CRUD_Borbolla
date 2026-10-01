# To-Do App: Authentication & User Accounts (CMSC 128 Lab 2)

Account system for the Lab 1 To-Do List: registration, login/logout, persistent sessions, profile editing, and password recovery by email.

## Stack and approach
- **Frontend:** server-rendered HTML (Jinja2), CSS, a little vanilla JS (loading state, show-password, unsaved-changes warning)
- **Backend:** Flask (Python). **Database:** SQLite (`instance/app.db`)
- **Passwords:** Werkzeug `generate_password_hash` (salted scrypt/PBKDF2), verified with `check_password_hash`
- **Sessions:** Flask signed cookie session (HttpOnly, SameSite=Lax, 7-day lifetime). The secret key is read from `SECRET_KEY` or generated once into `instance/secret_key`, so backend restarts keep users logged in.

## Structure
```
app.py        app factory, session/CSRF/current-user loading
auth.py       routes: register, login, logout, profile, forgot/reset
db.py         SQLite connection and schema
mailer.py     reset email (SMTP or demo mode)
templates/    Jinja pages      static/  CSS
.env.example  variable names only
```

## Install and run
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional; fill in SMTP to send real email
python app.py               # http://127.0.0.1:5000
```
The database and tables are created automatically on first start (`instance/app.db`). Inspect it with *SQLite Viewer* / *SQLite* VS Code extensions or DB Browser for SQLite; `password_hash` shows a hash, never the password.

## Features
Sign up (display name, username, email, password) · login by username or email · protected profile page (`Hello, <name>` + Log Out) · logout (session cleared, pages sent `no-store`) · edit display name/username/email/password with uniqueness validation · forgot/reset password · CSRF tokens on all POSTs.

## Endpoints
| Method | Route | Purpose |
|---|---|---|
| GET/POST | `/register` | Create account |
| GET/POST | `/login` | Log in, start session |
| POST | `/logout` | End session |
| GET/POST | `/profile` | Update profile (`action=profile`) or password (`action=password`); login required |
| GET/POST | `/forgot-password` | Request reset link |
| GET/POST | `/reset-password/<token>` | Set new password |

## Session mechanism
On login, `session.clear()` then `uid` and `session_version` are stored in the signed cookie. Each request loads the user from the DB; if the user is gone or `session_version` changed, the session is dropped. Changing or resetting a password increments `session_version`, signing out other devices. Refresh, back/forward and restarts keep you logged in because state lives in the cookie, validated against the DB.

## Password recovery mechanism
1. User submits username/email; the response is identical whether or not the account exists (no account enumeration).
2. A random token (`secrets.token_urlsafe(32)`) is generated; only its **SHA-256 hash** is stored with a 30-minute expiry (`RESET_TOKEN_MINUTES`).
3. The link `/reset-password/<token>` is emailed via SMTP.
4. Submitting a valid new password updates the hash, marks all the user's tokens used (single use), and invalidates existing sessions. The old password stops working.

**Demo mode (no SMTP configured):** the link is printed to the server console and appended to `instance/outbox.log`. *Limitations:* anyone with server access can read links; nothing is actually emailed. Real deployments need SMTP/HTTPS and `SESSION_COOKIE_SECURE=1`. Set `BASE_URL` so links don't depend on the request's Host header.

## Secrets
`.env`, `instance/` (DB, secret key, outbox) are in `.gitignore`. Only `.env.example` is committed.

## Git workflow
```bash
git checkout -b act2-accounts
git add . && git commit -m "cmsc128-Indiv-Act2"
git push -u origin act2-accounts
```

## Next activity
`users.id` is the owner key: add `todos.user_id REFERENCES users(id)`, filter queries by `g.user["id"]`, and use `@login_required` on todo routes.

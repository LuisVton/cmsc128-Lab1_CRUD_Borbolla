"""App factory: config, sessions, CSRF, current-user loading."""
import os, secrets
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, abort, g, request, session
from db import get_db, init_db

load_dotenv()

def load_secret_key(instance_path):
    """Env var wins; otherwise a generated key persists in instance/ so restarts keep sessions valid."""
    if os.getenv("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    p = Path(instance_path) / "secret_key"
    if not p.exists():
        p.write_text(secrets.token_hex(32))
    return p.read_text().strip()

def create_app():
    app = Flask(__name__)
    Path(app.instance_path).mkdir(exist_ok=True)
    app.config.update(
        SECRET_KEY=load_secret_key(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "app.db"),
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE") == "1",
    )
    init_db(app)

    @app.before_request
    def protect_and_load_user():
        session.setdefault("_csrf", secrets.token_hex(16))
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", "") if request.path.startswith("/api/") else request.form.get("_csrf", ""), session["_csrf"]):
            abort(400, "Invalid or missing form token. Reload the page and try again.")
        g.user = None
        uid = session.get("uid")
        if uid:
            u = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if u and u["session_version"] == session.get("sv"):
                g.user = u
            else:
                session.pop("uid", None); session.pop("sv", None)

    @app.after_request
    def no_cache(resp):  # back button after logout must not reveal protected pages
        if request.endpoint != "static":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.context_processor
    def inject():
        return {"csrf_token": session.get("_csrf", "")}

    from auth import bp
    app.register_blueprint(bp)
    from tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

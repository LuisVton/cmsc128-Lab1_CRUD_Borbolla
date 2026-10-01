"""Authentication routes: register, login, logout, profile, password recovery."""
import hashlib, os, re, secrets, sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db
from mailer import send_reset_email

bp = Blueprint("auth", __name__)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUMMY_HASH = generate_password_hash("timing-equalizer")

# ---------- helpers ----------
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*a, **kw)
    return wrapped

def start_session(user):
    session.clear()  # prevents session fixation
    session.permanent = True
    session["uid"], session["sv"] = user["id"], user["session_version"]

def identity_errors(f, exclude_id=0):
    e = {}
    if not USERNAME_RE.match(f["username"]):
        e["username"] = "Use 3–30 characters: letters, numbers, underscore."
    if not EMAIL_RE.match(f["email"]) or len(f["email"]) > 254:
        e["email"] = "Enter a valid email address."
    if not 1 <= len(f["display_name"]) <= 50:
        e["display_name"] = "Display name is required (max 50 characters)."
    db = get_db()
    for col in ("username", "email"):
        if col not in e and db.execute(
                f"SELECT 1 FROM users WHERE {col}=? AND id!=?", (f[col], exclude_id)).fetchone():
            e[col] = f"That {col} is already in use."
    return e

def password_errors(pw, confirm):
    e = {}
    if not (8 <= len(pw) <= 128 and re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        e["password"] = "Use 8–128 characters with at least one letter and one number."
    elif pw != confirm:
        e["confirm"] = "Passwords do not match."
    return e

def identity_form():
    f = {k: request.form.get(k, "").strip() for k in ("username", "email", "display_name")}
    f["email"] = f["email"].lower()
    return f

def token_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()

def now():
    return datetime.now(timezone.utc)

# ---------- routes ----------
@bp.route("/")
def index():
    return redirect(url_for("auth.profile" if g.user else "auth.login"))

@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("auth.profile"))
    form, errors = {}, {}
    if request.method == "POST":
        form = identity_form()
        pw, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        errors = {**identity_errors(form), **password_errors(pw, confirm)}
        if not errors:
            try:
                db = get_db()
                db.execute("INSERT INTO users (username,email,display_name,password_hash) VALUES (?,?,?,?)",
                           (form["username"], form["email"], form["display_name"],
                            generate_password_hash(pw)))
                db.commit()
            except sqlite3.IntegrityError:  # race on unique constraint
                errors["username"] = "That username or email is already in use."
            else:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("auth.login"))
    return render_template("register.html", form=form, errors=errors)

@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("auth.profile"))
    identifier = ""
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        pw = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username=? OR email=?",
                                (identifier, identifier)).fetchone()
        ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, pw)
        if user and ok:
            start_session(user)
            return redirect(url_for("auth.profile"))
        flash("Incorrect username/email or password.", "error")
    return render_template("login.html", identifier=identifier)

@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    u = g.user
    form = {"username": u["username"], "email": u["email"], "display_name": u["display_name"]}
    errors, pw_errors = {}, {}
    if request.method == "POST":
        db = get_db()
        if request.form.get("action") == "profile":
            form = identity_form()
            errors = identity_errors(form, u["id"])
            if not errors:
                try:
                    db.execute("UPDATE users SET username=?, email=?, display_name=? WHERE id=?",
                               (form["username"], form["email"], form["display_name"], u["id"]))
                    db.commit()
                    flash("Profile updated.", "success")
                    return redirect(url_for("auth.profile"))
                except sqlite3.IntegrityError:
                    errors["username"] = "That username or email is already in use."
        elif request.form.get("action") == "password":
            cur = request.form.get("current", "")
            new, confirm = request.form.get("password", ""), request.form.get("confirm", "")
            if not check_password_hash(u["password_hash"], cur):
                pw_errors["current"] = "Current password is incorrect."
            pw_errors.update(password_errors(new, confirm))
            if not pw_errors:
                db.execute("UPDATE users SET password_hash=?, session_version=session_version+1 WHERE id=?",
                           (generate_password_hash(new), u["id"]))
                db.commit()
                fresh = db.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
                start_session(fresh)  # keep this device signed in; other sessions are invalidated
                flash("Password changed. Other devices were signed out.", "success")
                return redirect(url_for("auth.profile"))
        if errors or pw_errors:
            flash("Please fix the highlighted fields.", "error")
    return render_template("profile.html", form=form, errors=errors, pw_errors=pw_errors)

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip()
        user = get_db().execute("SELECT * FROM users WHERE username=? OR email=?", (ident, ident)).fetchone()
        if user:
            minutes = int(os.getenv("RESET_TOKEN_MINUTES", 30))
            token = secrets.token_urlsafe(32)
            db = get_db()
            db.execute("INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?,?,?)",
                       (user["id"], token_hash(token), (now() + timedelta(minutes=minutes)).isoformat()))
            db.commit()
            base = os.getenv("BASE_URL")
            path = url_for("auth.reset", token=token)
            link = base.rstrip("/") + path if base else url_for("auth.reset", token=token, _external=True)
            try:
                send_reset_email(user["email"], link, minutes)
            except Exception as exc:  # don't leak delivery status to the requester
                print("Mail error:", exc)
        # Same response whether or not the account exists (prevents account enumeration)
        flash("If that account exists, a reset link has been sent to its email address.", "success")
        return redirect(url_for("auth.login"))
    return render_template("forgot.html")

def find_valid_reset(token):
    row = get_db().execute("SELECT * FROM password_resets WHERE token_hash=? AND used=0",
                           (token_hash(token),)).fetchone()
    if row and datetime.fromisoformat(row["expires_at"]) > now():
        return row
    return None

@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset(token):
    row = find_valid_reset(token)
    if not row:
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    errors = {}
    if request.method == "POST":
        errors = password_errors(request.form.get("password", ""), request.form.get("confirm", ""))
        if not errors:
            db = get_db()
            db.execute("UPDATE users SET password_hash=?, session_version=session_version+1 WHERE id=?",
                       (generate_password_hash(request.form["password"]), row["user_id"]))
            db.execute("UPDATE password_resets SET used=1 WHERE user_id=?", (row["user_id"],))
            db.commit()
            flash("Password reset. Log in with your new password.", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset.html", errors=errors)

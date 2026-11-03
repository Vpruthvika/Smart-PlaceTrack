import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, g, jsonify, request, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "placetrack.db")
STATUSES = ["Applied", "Shortlisted", "Interview", "Offer", "Rejected"]

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS applications (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        company    TEXT NOT NULL,
        role       TEXT NOT NULL,
        status     TEXT NOT NULL DEFAULT 'Applied',
        deadline   TEXT,
        ctc        REAL,
        notes      TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "user_id" not in session:
            return jsonify(error="Please log in."), 401
        return f(*a, **k)
    return wrapper


@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Resource not found."), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Something went wrong on the server."), 500


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/register", methods=["POST"])
def register():
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    if not name or "@" not in email or len(pw) < 6:
        return jsonify(error="Enter a name, a valid email and a password of 6+ characters."), 400
    db = get_db()
    try:
        db.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                   (name, email, generate_password_hash(pw)))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="An account with this email already exists."), 409
    return jsonify(message="Account created. Please log in."), 201


@app.route("/login", methods=["POST"])
def login():
    d = request.get_json(silent=True) or {}
    row = get_db().execute("SELECT * FROM users WHERE email=?",
                           ((d.get("email") or "").strip().lower(),)).fetchone()
    if not row or not check_password_hash(row["password_hash"], d.get("password") or ""):
        return jsonify(error="Invalid email or password."), 401
    session["user_id"], session["name"] = row["id"], row["name"]
    return jsonify(name=row["name"])


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(message="Logged out.")


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify(error="Not logged in."), 401
    return jsonify(name=session["name"])


def parse_app(data, partial=False):
    """Validate application fields; returns (clean_dict, error)."""
    out = {}
    for f in ("company", "role"):
        if f in data or not partial:
            v = (data.get(f) or "").strip()
            if not v:
                return None, "Company and role are required."
            out[f] = v
    if "status" in data or not partial:
        out["status"] = data.get("status", "Applied")
        if out["status"] not in STATUSES:
            return None, "Invalid status."
    try:
        if "ctc" in data or not partial:
            c = data.get("ctc")
            out["ctc"] = float(c) if c not in (None, "") else None
        if "deadline" in data or not partial:
            dl = data.get("deadline") or None
            if dl:
                datetime.strptime(dl, "%Y-%m-%d")
            out["deadline"] = dl
    except ValueError:
        return None, "Invalid CTC or date format."
    if "notes" in data:
        out["notes"] = (data.get("notes") or "").strip()
    return out, None


@app.route("/api/applications", methods=["GET"])
@login_required
def list_applications():
    rows = get_db().execute(
        "SELECT id, company, role, status, deadline, ctc, notes FROM applications"
        " WHERE user_id=? ORDER BY created_at DESC, id DESC", (session["user_id"],)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/applications", methods=["POST"])
@login_required
def add_application():
    clean, err = parse_app(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    db = get_db()
    db.execute(
        "INSERT INTO applications (user_id, company, role, status, deadline, ctc, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], clean["company"], clean["role"], clean["status"],
         clean["deadline"], clean["ctc"], clean.get("notes")))
    db.commit()
    return jsonify(message="Application saved."), 201


@app.route("/api/applications/<int:app_id>", methods=["PATCH"])
@login_required
def update_application(app_id):
    clean, err = parse_app(request.get_json(silent=True) or {}, partial=True)
    if err:
        return jsonify(error=err), 400
    if not clean:
        return jsonify(error="Nothing to update."), 400
    sets = ", ".join(f"{k}=?" for k in clean)
    db = get_db()
    cur = db.execute(f"UPDATE applications SET {sets} WHERE id=? AND user_id=?",
                     (*clean.values(), app_id, session["user_id"]))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Application not found."), 404
    return jsonify(message="Updated.")


@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
@login_required
def delete_application(app_id):
    db = get_db()
    cur = db.execute("DELETE FROM applications WHERE id=? AND user_id=?",
                     (app_id, session["user_id"]))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Application not found."), 404
    return jsonify(message="Deleted.")


@app.route("/api/stats")
@login_required
def stats():
    db = get_db()
    uid = session["user_id"]
    rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM applications WHERE user_id=? GROUP BY status",
        (uid,)).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    total = sum(counts.values())
    offers = counts.get("Offer", 0)
    nxt = db.execute(
        "SELECT company, deadline FROM applications"
        " WHERE user_id=? AND deadline >= date('now') AND status IN ('Applied','Shortlisted')"
        " ORDER BY deadline LIMIT 1", (uid,)).fetchone()
    return jsonify(total=total, by_status=counts,
                   offer_rate=round(100 * offers / total, 1) if total else 0,
                   next_deadline=dict(nxt) if nxt else None)


init_db()

if __name__ == "__main__":
    app.run(debug=True)

"""Daily Task Observer - Flask backend.

REST API for daily tasks and progress uploads, plus a small static server
for the frontend.

Run it with:   python Backend/app.py
Then open:     http://127.0.0.1:5000
"""

import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from database import BASE_DIR, UPLOADS_DIR, get_connection, init_db, now_str

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB is plenty for text progress files
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5000"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
# Always answer with a friendly message instead of a raw Python traceback page.
app.config["PROPAGATE_EXCEPTIONS"] = False

# Let the frontend call the API during local development. The frontend may be
# opened from file://, Live Server, or served by this app - all are allowed.
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Create database/progress.db and the uploads/ folder if they do not exist yet.
init_db()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def db():
    """Return the SQLite connection for the current request."""
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_connection(exception):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def parse_date(value):
    """Return a datetime.date for a 'YYYY-MM-DD' string, or None if invalid."""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def clean_tags(raw_tags):
    """Turn 'work, study , ' into a tidy 'work, study' string."""
    parts = [part.strip() for part in (raw_tags or "").split(",")]
    return ", ".join(part for part in parts if part)[:300]


def progress_to_dict(row, include_content=True):
    """Turn a progress database row into a JSON friendly dictionary."""
    content = row["content"] or ""
    data = {
        "id": row["id"],
        "date": row["date"],
        "title": row["title"],
        "tags": row["tags"] or "",
        "filename": row["filename"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "preview": content.strip()[:120],
    }
    if include_content:
        data["content"] = content
    return data


def task_to_dict(row):
    """Turn a task database row into a JSON friendly dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "date": row["task_date"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


def fetch_tasks(connection, task_date):
    """All tasks for one day, pending ones first."""
    rows = connection.execute(
        "SELECT * FROM tasks WHERE task_date = ? ORDER BY (status = 'completed'), id",
        (task_date,),
    ).fetchall()
    return [task_to_dict(row) for row in rows]


def all_progress_dates(connection):
    """Every distinct upload date as datetime.date objects."""
    rows = connection.execute("SELECT DISTINCT date FROM progress").fetchall()
    return [parsed for parsed in (parse_date(row["date"]) for row in rows) if parsed]


def calculate_streaks(dates):
    """Return (current_streak, longest_streak) for a set of upload dates.

    A streak is a run of consecutive calendar days. Several uploads on the
    same date count as one streak day. The current streak stays alive if only
    'today' is still missing (you can still upload today).
    """
    dates = set(dates)

    current = 0
    cursor = date.today()
    if cursor not in dates:
        cursor -= timedelta(days=1)  # grace day: yesterday keeps it alive
    while cursor in dates:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    previous = None
    for day in sorted(dates):
        run = run + 1 if previous is not None and (day - previous).days == 1 else 1
        longest = max(longest, run)
        previous = day
    return current, longest


def uploads_path(filename):
    """Full path for a stored filename, guaranteed to stay inside uploads/.

    Returns None when the name is empty or tries to escape the folder.
    """
    clean_name = os.path.basename(filename or "")
    if not clean_name:
        return None
    uploads_real = os.path.realpath(UPLOADS_DIR)
    full_path = os.path.realpath(os.path.join(uploads_real, clean_name))
    if os.path.dirname(full_path) != uploads_real:
        return None
    return full_path


def remove_upload(filename):
    """Delete an uploaded file, ignoring 'already missing' errors."""
    path = uploads_path(filename)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            app.logger.warning("Could not delete uploaded file: %s", path)


# ---------------------------------------------------------------------------
# Error handling - JSON for the API, plain messages elsewhere
# ---------------------------------------------------------------------------

@app.errorhandler(HTTPException)
def handle_http_error(error):
    message = error.description or error.name
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), error.code
    return "%s: %s" % (error.name, error.description), error.code


@app.errorhandler(sqlite3.Error)
def handle_database_error(error):
    app.logger.error("Database error: %s", error)
    if request.path.startswith("/api/"):
        return jsonify({"error": "A database error occurred. Please try again."}), 500
    return "A database error occurred.", 500


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return handle_http_error(error)
    app.logger.error("Unhandled error: %s", error, exc_info=True)
    message = "Something went wrong on the server. Please try again."
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 500
    return message, 500


# ---------------------------------------------------------------------------
# Frontend (kept in frontend/, served for convenience)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    # CSS/JS files. send_from_directory refuses paths outside frontend/.
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

@app.route("/api")
def api_home():
    return jsonify({"message": "Daily Task Observer API is running"})


# ---------------------------------------------------------------------------
# Progress uploads
# ---------------------------------------------------------------------------

@app.route("/api/progress", methods=["GET"])
def list_progress():
    """List progress entries with optional search / tag / date / sort."""
    connection = db()

    search = (request.args.get("search") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    entry_date = (request.args.get("date") or "").strip()
    sort = request.args.get("sort", "newest")

    sql = "SELECT * FROM progress WHERE 1=1"
    params = []

    if search:
        like = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (title LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"
        params += [like, like, like]

    if tag:
        # Match one tag inside the comma separated list (whole word only).
        safe_tag = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql += " AND (',' || tags || ',') LIKE ? ESCAPE '\\'"
        params.append("%," + safe_tag + ",%")

    if entry_date:
        if not parse_date(entry_date):
            return jsonify({"error": "Invalid date. Use YYYY-MM-DD."}), 400
        sql += " AND date = ?"
        params.append(entry_date)

    if sort == "oldest":
        sql += " ORDER BY date ASC, id ASC"
    else:
        sql += " ORDER BY date DESC, id DESC"

    rows = connection.execute(sql, params).fetchall()
    items = [progress_to_dict(row, include_content=False) for row in rows]
    return jsonify({"items": items, "total": len(items)})


@app.route("/api/progress/tags", methods=["GET"])
def list_tags():
    """Every tag that exists on at least one progress entry."""
    rows = db().execute("SELECT tags FROM progress").fetchall()
    tags = set()
    for row in rows:
        for tag in (row["tags"] or "").split(","):
            tag = tag.strip()
            if tag:
                tags.add(tag)
    return jsonify({"tags": sorted(tags, key=str.lower)})


@app.route("/api/progress/<int:progress_id>", methods=["GET"])
def get_progress(progress_id):
    row = db().execute("SELECT * FROM progress WHERE id = ?", (progress_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Progress entry not found."}), 404
    return jsonify(progress_to_dict(row))


@app.route("/api/progress", methods=["POST"])
def create_progress():
    """Upload a .txt file: validate, save to uploads/, record in SQLite."""
    # --- validate the form fields ---
    entry_date = (request.form.get("date") or "").strip()
    if not parse_date(entry_date):
        return jsonify({"error": "Please provide a valid date (YYYY-MM-DD)."}), 400

    title = (request.form.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400
    if len(title) > 300:
        return jsonify({"error": "Title must be 300 characters or fewer."}), 400

    tags = clean_tags(request.form.get("tags"))

    # --- validate the file ---
    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "Please choose a .txt progress file."}), 400

    uploaded = request.files["file"]
    raw_name = uploaded.filename or ""
    if not raw_name.lower().endswith(".txt"):
        return jsonify({"error": "Only .txt files are allowed."}), 400

    raw = uploaded.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"error": "The progress file must be UTF-8 text."}), 400
    if not content.strip():
        return jsonify({"error": "The progress file is empty."}), 400

    # --- build a safe, unique storage name (never trust the client name) ---
    safe_name = secure_filename(raw_name) or "progress.txt"
    stem, extension = os.path.splitext(safe_name)
    if extension.lower() != ".txt":
        extension = ".txt"
    safe_name = stem[:60] + extension
    stored_name = "%s_%s_%s" % (entry_date, uuid.uuid4().hex[:8], safe_name)
    file_path = uploads_path(stored_name)
    if file_path is None:
        return jsonify({"error": "The file name is not valid."}), 400

    try:
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError:
        app.logger.error("Could not save upload: %s", file_path)
        return jsonify({"error": "The progress file could not be saved."}), 500

    # --- store the metadata (and remove the file if the insert fails) ---
    connection = db()
    timestamp = now_str()
    try:
        cursor = connection.execute(
            """
            INSERT INTO progress (date, title, tags, filename, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_date, title, tags, stored_name, content, timestamp, timestamp),
        )
        connection.commit()
    except sqlite3.Error:
        remove_upload(stored_name)
        raise

    row = connection.execute(
        "SELECT * FROM progress WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(progress_to_dict(row)), 201


@app.route("/api/progress/<int:progress_id>", methods=["PUT"])
def update_progress(progress_id):
    """Edit title/date/tags/text; keeps the .txt file on disk in sync."""
    body = request.get_json(silent=True) or {}

    entry_date = (body.get("date") or "").strip()
    title = (body.get("title") or "").strip()
    tags = clean_tags(body.get("tags"))
    content = body.get("content")

    if not parse_date(entry_date):
        return jsonify({"error": "Please provide a valid date (YYYY-MM-DD)."}), 400
    if not title:
        return jsonify({"error": "Title is required."}), 400
    if len(title) > 300:
        return jsonify({"error": "Title must be 300 characters or fewer."}), 400
    if content is None or not str(content).strip():
        return jsonify({"error": "Progress text cannot be empty."}), 400
    content = str(content)

    connection = db()
    row = connection.execute("SELECT * FROM progress WHERE id = ?", (progress_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Progress entry not found."}), 404

    # Keep the uploaded file in sync with the edited text.
    file_path = uploads_path(row["filename"])
    if file_path is not None:
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError:
            app.logger.error("Could not update file: %s", file_path)
            return jsonify({"error": "The progress file could not be updated."}), 500

    connection.execute(
        """
        UPDATE progress
        SET date = ?, title = ?, tags = ?, content = ?, updated_at = ?
        WHERE id = ?
        """,
        (entry_date, title, tags, content, now_str(), progress_id),
    )
    connection.commit()

    row = connection.execute("SELECT * FROM progress WHERE id = ?", (progress_id,)).fetchone()
    return jsonify(progress_to_dict(row))


@app.route("/api/progress/<int:progress_id>", methods=["DELETE"])
def delete_progress(progress_id):
    connection = db()
    row = connection.execute("SELECT * FROM progress WHERE id = ?", (progress_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Progress entry not found."}), 404

    remove_upload(row["filename"])  # delete the file from uploads/ first
    connection.execute("DELETE FROM progress WHERE id = ?", (progress_id,))
    connection.commit()
    return jsonify({"message": "Progress entry deleted."})


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    task_date = (request.args.get("date") or "").strip()
    if not task_date:
        task_date = date.today().isoformat()
    if not parse_date(task_date):
        return jsonify({"error": "Invalid date. Use YYYY-MM-DD."}), 400

    items = fetch_tasks(db(), task_date)
    completed = sum(1 for task in items if task["status"] == "completed")
    return jsonify({
        "date": task_date,
        "items": items,
        "total": len(items),
        "completed": completed,
        "pending": len(items) - completed,
    })


@app.route("/api/tasks", methods=["POST"])
def create_task():
    body = request.get_json(silent=True) or {}

    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Task title is required."}), 400
    if len(title) > 300:
        return jsonify({"error": "Task title must be 300 characters or fewer."}), 400

    task_date = (body.get("date") or "").strip() or date.today().isoformat()
    if not parse_date(task_date):
        return jsonify({"error": "Please provide a valid date (YYYY-MM-DD)."}), 400

    connection = db()
    cursor = connection.execute(
        "INSERT INTO tasks (title, task_date, status, created_at) VALUES (?, ?, 'pending', ?)",
        (title, task_date, now_str()),
    )
    connection.commit()

    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    body = request.get_json(silent=True) or {}
    connection = db()

    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Task not found."}), 404

    title = body.get("title")
    status = body.get("status")
    if title is None and status is None:
        return jsonify({"error": "Nothing to update."}), 400

    new_status = row["status"]
    if status is not None:
        if status not in ("pending", "completed"):
            return jsonify({"error": "Status must be 'pending' or 'completed'."}), 400
        new_status = status

    new_title = row["title"]
    if title is not None:
        new_title = (title or "").strip()
        if not new_title:
            return jsonify({"error": "Task title cannot be empty."}), 400
        if len(new_title) > 300:
            return jsonify({"error": "Task title must be 300 characters or fewer."}), 400

    completed_at = row["completed_at"]
    if new_status == "completed" and row["status"] != "completed":
        completed_at = now_str()
    elif new_status == "pending":
        completed_at = None

    connection.execute(
        "UPDATE tasks SET title = ?, status = ?, completed_at = ? WHERE id = ?",
        (new_title, new_status, completed_at, task_id),
    )
    connection.commit()

    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(task_to_dict(row))


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    connection = db()
    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Task not found."}), 404

    connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    return jsonify({"message": "Task deleted."})


# ---------------------------------------------------------------------------
# Dashboard / calendar / statistics
# ---------------------------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    """Numbers for the dashboard cards, all computed from SQLite."""
    connection = db()

    dates = all_progress_dates(connection)
    total_files = connection.execute("SELECT COUNT(*) AS n FROM progress").fetchone()["n"]
    current_streak, _ = calculate_streaks(dates)

    recent_rows = connection.execute(
        "SELECT * FROM progress ORDER BY date DESC, id DESC LIMIT 5"
    ).fetchall()
    recent = [progress_to_dict(row, include_content=False) for row in recent_rows]

    today = date.today().isoformat()
    items = fetch_tasks(connection, today)
    completed = sum(1 for task in items if task["status"] == "completed")
    total = len(items)

    return jsonify({
        "total_days": len(dates),
        "current_streak": current_streak,
        "total_files": total_files,
        "recent": recent,
        "today": {
            "date": today,
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "percentage": round(completed * 100 / total) if total else 0,
        },
    })


@app.route("/api/calendar", methods=["GET"])
def calendar():
    """Dates that have at least one uploaded progress file, with counts."""
    rows = db().execute(
        "SELECT date, COUNT(*) AS count FROM progress GROUP BY date ORDER BY date DESC"
    ).fetchall()
    days = [{"date": row["date"], "count": row["count"]} for row in rows]
    return jsonify({"days": days})


@app.route("/api/statistics", methods=["GET"])
def statistics():
    """Streaks, weekly/monthly progress and task statistics."""
    connection = db()
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()  # Monday
    month_start = today.replace(day=1).isoformat()

    dates = all_progress_dates(connection)
    current_streak, longest_streak = calculate_streaks(dates)
    total_uploads = connection.execute("SELECT COUNT(*) AS n FROM progress").fetchone()["n"]

    weekly_days = sum(1 for day in dates if day.isoformat() >= week_start)
    monthly_days = sum(1 for day in dates if day.isoformat() >= month_start)
    weekly_uploads = connection.execute(
        "SELECT COUNT(*) AS n FROM progress WHERE date >= ?", (week_start,)
    ).fetchone()["n"]
    monthly_uploads = connection.execute(
        "SELECT COUNT(*) AS n FROM progress WHERE date >= ?", (month_start,)
    ).fetchone()["n"]

    task_row = connection.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
        FROM tasks
        """
    ).fetchone()
    total_tasks = task_row["total"] or 0
    completed_tasks = task_row["completed"] or 0

    completed_this_week = connection.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE status = 'completed' AND date(completed_at) >= ?",
        (week_start,),
    ).fetchone()["n"]
    completed_this_month = connection.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE status = 'completed' AND date(completed_at) >= ?",
        (month_start,),
    ).fetchone()["n"]

    return jsonify({
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_uploads": total_uploads,
        "total_days": len(dates),
        "weekly_days": weekly_days,
        "weekly_uploads": weekly_uploads,
        "monthly_days": monthly_days,
        "monthly_uploads": monthly_uploads,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": round(completed_tasks * 100 / total_tasks, 1) if total_tasks else 0.0,
        "completed_this_week": completed_this_week,
        "completed_this_month": completed_this_month,
    })


if __name__ == "__main__":
    print("Daily Task Observer backend running at http://%s:%s" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=True)

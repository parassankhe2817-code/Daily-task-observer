"""Database setup and helpers for the Daily Task Observer.

This module makes sure the database/ folder and database/progress.db exist,
creates all required tables when the application starts, and provides small
helpers the Flask app uses to talk to SQLite.
"""

import os
import sqlite3
from datetime import datetime

# Project folders, computed from this file so the paths work from any
# working directory.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DATABASE_PATH = os.path.join(DATABASE_DIR, "progress.db")


def now_str():
    """Current local time as a sortable string, e.g. '2026-10-04 13:05:09'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    """Open a fresh SQLite connection where rows can be read by column name.

    A new connection is opened per request and closed by the Flask app, which
    keeps writes safe and avoids 'database is locked' problems.
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _add_column_if_missing(cursor, table, column, definition):
    """Add a column to an existing table (used to upgrade older databases)."""
    columns = [row["name"] for row in cursor.execute("PRAGMA table_info(%s)" % table)]
    if column not in columns:
        cursor.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, definition))


def init_db():
    """Create the folders, tables and indexes if they do not exist yet.

    Safe to call every time the application starts.
    """
    # Never assume these folders exist - create them automatically.
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    connection = get_connection()
    try:
        cursor = connection.cursor()

        # Daily progress uploads (.txt files stored inside uploads/).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)

        # Daily tasks (pending / completed).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                task_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT
            )
        """)

        # Upgrade databases created with the original 5-column progress table.
        _add_column_if_missing(cursor, "progress", "tags", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(cursor, "progress", "created_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(cursor, "progress", "updated_at", "TEXT NOT NULL DEFAULT ''")

        # Fill in timestamps for rows saved before those columns existed.
        # (Two statements: the second one must see the value set by the first.)
        cursor.execute(
            "UPDATE progress SET created_at = ? "
            "WHERE created_at IS NULL OR created_at = ''",
            (now_str(),),
        )
        cursor.execute(
            "UPDATE progress SET updated_at = created_at "
            "WHERE updated_at IS NULL OR updated_at = ''"
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_date ON progress(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(task_date)")

        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print("Database ready at %s" % DATABASE_PATH)

"""
models.py - SQLite database layer for AccessLens AI.

Two tables:
  preferences - one row (id = 1) holding the user's accessibility settings
  history     - one row per piece of text that was processed

The database file (accesslens.db) is created automatically by init_db().
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "accesslens.db")

# Settings used on first run and when the user presses "Reset".
DEFAULT_PREFS = {"font_size": 18, "line_spacing": 1.6, "dark_mode": 0, "high_contrast": 0}


@contextmanager
def db():
    """Open a connection, commit on success, always close (important on Windows)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they do not exist and make sure the preferences row exists."""
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                id            INTEGER PRIMARY KEY CHECK (id = 1),
                font_size     INTEGER NOT NULL,
                line_spacing  REAL    NOT NULL,
                dark_mode     INTEGER NOT NULL,
                high_contrast INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                original_text     TEXT    NOT NULL,
                simplified_text   TEXT    NOT NULL,
                words_before      INTEGER NOT NULL,
                words_after       INTEGER NOT NULL,
                avg_sentence_before REAL  NOT NULL,
                avg_sentence_after  REAL  NOT NULL,
                ease_before       REAL    NOT NULL,
                ease_after        REAL    NOT NULL,
                highlight_count   INTEGER NOT NULL,
                created_at        TEXT    NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO preferences "
            "(id, font_size, line_spacing, dark_mode, high_contrast) VALUES (1, ?, ?, ?, ?)",
            (
                DEFAULT_PREFS["font_size"],
                DEFAULT_PREFS["line_spacing"],
                DEFAULT_PREFS["dark_mode"],
                DEFAULT_PREFS["high_contrast"],
            ),
        )


# ---------------------------------------------------------------- preferences
def get_preferences():
    with db() as conn:
        row = conn.execute(
            "SELECT font_size, line_spacing, dark_mode, high_contrast FROM preferences WHERE id = 1"
        ).fetchone()
    return dict(row)


def validate_preferences(data):
    """Check incoming settings and return a cleaned dict. Raises ValueError if invalid."""
    if not isinstance(data, dict):
        raise ValueError("Preferences must be sent as a JSON object.")
    clean = {}
    if "font_size" in data:
        v = data["font_size"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 14 <= v <= 32:
            raise ValueError("font_size must be a number between 14 and 32.")
        clean["font_size"] = int(round(v))
    if "line_spacing" in data:
        v = data["line_spacing"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 1.2 <= v <= 2.4:
            raise ValueError("line_spacing must be a number between 1.2 and 2.4.")
        clean["line_spacing"] = round(float(v), 1)
    for key in ("dark_mode", "high_contrast"):
        if key in data:
            v = data[key]
            if not isinstance(v, (bool, int)) or v not in (0, 1):
                raise ValueError(f"{key} must be true or false.")
            clean[key] = 1 if v else 0
    if not clean:
        raise ValueError("No valid preference fields were provided.")
    return clean


def update_preferences(data):
    """Validate and save the given settings, then return all current settings."""
    clean = validate_preferences(data)
    # Keys come from the validated whitelist above, so building the SQL is safe.
    assignments = ", ".join(f"{key} = ?" for key in clean)
    with db() as conn:
        conn.execute(f"UPDATE preferences SET {assignments} WHERE id = 1", list(clean.values()))
    return get_preferences()


def reset_preferences():
    with db() as conn:
        conn.execute(
            "UPDATE preferences SET font_size = ?, line_spacing = ?, dark_mode = ?, "
            "high_contrast = ? WHERE id = 1",
            (
                DEFAULT_PREFS["font_size"],
                DEFAULT_PREFS["line_spacing"],
                DEFAULT_PREFS["dark_mode"],
                DEFAULT_PREFS["high_contrast"],
            ),
        )
    return get_preferences()


# -------------------------------------------------------------------- history
def add_history(original, result):
    """Save one processed text. `result` is the dict returned by text_processor.process()."""
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO history (original_text, simplified_text, words_before, words_after, "
            "avg_sentence_before, avg_sentence_after, ease_before, ease_after, "
            "highlight_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                original,
                result["simplified"],
                result["before"]["words"],
                result["after"]["words"],
                result["before"]["avg_sentence"],
                result["after"]["avg_sentence"],
                result["before"]["ease"],
                result["after"]["ease"],
                result["highlight_count"],
                created,
            ),
        )
        return cur.lastrowid


def get_history_list(limit=50):
    """Newest first, with a short preview of the original text."""
    with db() as conn:
        rows = conn.execute(
            "SELECT id, original_text, words_before, highlight_count, created_at "
            "FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items = []
    for row in rows:
        preview = " ".join(row["original_text"].split())
        if len(preview) > 110:
            preview = preview[:110].rstrip() + "..."
        items.append(
            {
                "id": row["id"],
                "preview": preview,
                "words_before": row["words_before"],
                "highlight_count": row["highlight_count"],
                "created_at": row["created_at"],
            }
        )
    return items


def get_history_item(item_id):
    with db() as conn:
        return conn.execute("SELECT * FROM history WHERE id = ?", (item_id,)).fetchone()


def delete_history_item(item_id):
    with db() as conn:
        cur = conn.execute("DELETE FROM history WHERE id = ?", (item_id,))
        return cur.rowcount > 0


def clear_history():
    with db() as conn:
        cur = conn.execute("DELETE FROM history")
        return cur.rowcount


# ---------------------------------------------------------------------- stats
def get_stats():
    """Every number here is calculated from the history table - nothing is hard-coded."""
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(words_before), 0) AS words, "
            "COALESCE(AVG(avg_sentence_before - avg_sentence_after), 0) AS sentence_drop, "
            "COALESCE(AVG(ease_after - ease_before), 0) AS ease_gain, "
            "COALESCE(SUM(highlight_count), 0) AS highlights "
            "FROM history"
        ).fetchone()
    return {
        "total_texts": row["total"],
        "total_words": row["words"],
        "avg_sentence_reduction": round(row["sentence_drop"], 1),
        "avg_ease_gain": round(row["ease_gain"], 1),
        "total_highlights": row["highlights"],
    }

# ============================================================
# backend/db/user_store.py
# NeuroAgent - User & Session Database (SQLite)
# ============================================================
# Manages user registration, login, and per-user settings.
# Uses SQLite (no setup required) for lightweight persistence.
# Pinecone handles long-term memory; this handles auth/prefs.
# ============================================================

import sqlite3
import os
import json
from datetime import datetime

# Path to the SQLite database file
DB_PATH = os.path.join(os.path.dirname(__file__), "neuroagent.db")


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # Rows behave like dicts
    return conn


def init_db() -> None:
    """
    Create all tables if they don't already exist.
    Call once at app startup.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    # ── Users table ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            created_at  TEXT    NOT NULL,
            last_login  TEXT
        )
    """)

    # ── User preferences table ────────────────────────────────
    # Stores selected model and any other per-user preferences
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id         INTEGER PRIMARY KEY,
            selected_model  TEXT    NOT NULL DEFAULT 'llama-3.3-70b-versatile',
            voice_enabled   INTEGER NOT NULL DEFAULT 0,
            preferences_json TEXT  NOT NULL DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── Conversation history table ────────────────────────────
    # Short-term history stored locally; long-term goes to Pinecone
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            role        TEXT    NOT NULL,   -- 'user' or 'assistant'
            content     TEXT    NOT NULL,
            model_used  TEXT,
            timestamp   TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialised.")


def get_or_create_user(username: str) -> dict:
    """
    Return the user record for `username`, creating one if needed.
    Also updates last_login timestamp.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()

    # Try to find existing user
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user is None:
        # Create new user
        cursor.execute(
            "INSERT INTO users (username, created_at, last_login) VALUES (?, ?, ?)",
            (username, now, now)
        )
        user_id = cursor.lastrowid

        # Create default preferences
        cursor.execute(
            "INSERT INTO user_preferences (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        print(f"[DB] New user created: {username}")
    else:
        # Update last_login
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now, user["id"])
        )
        conn.commit()
        print(f"[DB] Existing user logged in: {username}")

    result = dict(user)
    conn.close()
    return result


def get_user_preferences(user_id: int) -> dict:
    """Return preferences dict for a given user_id."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {"selected_model": "llama-3.3-70b-versatile", "voice_enabled": False}

    prefs = dict(row)
    prefs["voice_enabled"] = bool(prefs["voice_enabled"])
    prefs["preferences_json"] = json.loads(prefs.get("preferences_json", "{}"))
    return prefs


def update_user_model(user_id: int, model_id: str) -> None:
    """Update the selected model for a user."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_preferences SET selected_model = ? WHERE user_id = ?",
        (model_id, user_id)
    )
    conn.commit()
    conn.close()


def update_voice_setting(user_id: int, enabled: bool) -> None:
    """Toggle voice mode for a user."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_preferences SET voice_enabled = ? WHERE user_id = ?",
        (1 if enabled else 0, user_id)
    )
    conn.commit()
    conn.close()


def save_message(user_id: int, role: str, content: str, model_used: str = "") -> None:
    """Persist a single chat message to the conversation history."""
    conn = _get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        """
        INSERT INTO conversations (user_id, role, content, model_used, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, role, content, model_used, now)
    )
    conn.commit()
    conn.close()


def get_recent_history(user_id: int, limit: int = 20) -> list[dict]:
    """
    Return the last `limit` messages for a user as a list of dicts.
    Ordered oldest → newest for LangChain message history.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT role, content, model_used, timestamp
        FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    # Reverse so oldest message is first
    return [dict(r) for r in reversed(rows)]


def clear_history(user_id: int) -> None:
    """Delete all conversation history for a user."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.config import DATABASE_URL

def get_db_path() -> str:
    url = DATABASE_URL
    if url.startswith("sqlite:////"):
        path = url[9:]  # e.g. /data/app.db
    elif url.startswith("sqlite:///"):
        path = url[10:] # e.g. ./data/app.db or path
    else:
        path = url
    # Handle Windows paths if needed
    if os.name == 'nt' and path.startswith('/') and len(path) > 2 and path[2] == ':':
        path = path[1:]
    return path

DB_PATH = get_db_path()

def get_connection() -> sqlite3.Connection:
    # Ensure directory exists
    dir_name = os.path.dirname(os.path.abspath(DB_PATH))
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
        """)
        conn.commit()
    finally:
        conn.close()

def check_db_health() -> bool:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception:
        return False

def add_message(session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata) if metadata is not None else None
        cursor.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, meta_str, now_iso)
        )
        conn.commit()
    finally:
        conn.close()

def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,)
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            msg = {
                "role": row["role"],
                "content": row["content"]
            }
            if row["metadata"]:
                try:
                    msg["metadata"] = json.loads(row["metadata"])
                except Exception:
                    msg["metadata"] = row["metadata"]
            result.append(msg)
        return result
    finally:
        conn.close()

def session_exists(session_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
            (session_id,)
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()

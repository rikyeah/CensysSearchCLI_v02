"""
State management for Censys CLI using SQLite.
Stores job state for resuming interrupted queries.
"""
import sqlite3
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

DEFAULT_DB = "./censys_state.sqlite"

DDL = """
CREATE TABLE IF NOT EXISTS job_state (
  job_id TEXT PRIMARY KEY,
  query TEXT NOT NULL,
  idx TEXT NOT NULL,
  fields TEXT,
  cursor TEXT,
  total INTEGER DEFAULT 0,
  updated_at TEXT NOT NULL
);
"""

def _connect(db_path: str) -> sqlite3.Connection:
    """Connect to the SQLite database with WAL mode."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(DDL)
    return conn

def make_job_id(index: str, query: str, fields: Optional[list]) -> str:
    """Generate a unique job ID based on index, query, and fields."""
    key = json.dumps({
        "index": index,
        "query": query,
        "fields": fields or []
    }, sort_keys=True).encode("utf-8")
    return hashlib.sha1(key).hexdigest()

def get_state(db_path: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve job state from the database."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT job_id, query, idx, fields, cursor, total, updated_at FROM job_state WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "job_id": row[0],
            "query": row[1],
            "index": row[2],
            "fields": json.loads(row[3]) if row[3] else None,
            "cursor": row[4],
            "total": row[5],
            "updated_at": row[6],
        }
    finally:
        conn.close()

def upsert_state(db_path: str, job_id: str, index: str, query: str, fields: Optional[list], cursor: Optional[str], total: int) -> None:
    """Insert or update job state in the database."""
    conn = _connect(db_path)
    try:
        now = datetime.utcnow().isoformat() + "Z"
        fields_json = json.dumps(fields) if fields else None
        conn.execute("""
            INSERT INTO job_state (job_id, query, idx, fields, cursor, total, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                cursor=excluded.cursor,
                total=excluded.total,
                updated_at=excluded.updated_at
        """, (job_id, query, index, fields_json, cursor, total, now))
        conn.commit()
    finally:
        conn.close()
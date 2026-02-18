import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime

class DB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT,
            result TEXT NOT NULL,
            confidence REAL,
            note TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    def set_setting(self, key: str, value: str):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        conn.commit()
        conn.close()

    def get_setting(self, key: str, default: Optional[str] = None) -> str:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else (default if default is not None else "")

    def add_event(self, name: Optional[str], result: str, confidence: Optional[float], note: str = ""):
        conn = self._connect()
        cur = conn.cursor()
        ts = datetime.now().isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO events(ts, name, result, confidence, note) VALUES(?,?,?,?,?)",
            (ts, name, result, confidence, note)
        )
        conn.commit()
        conn.close()

    def latest_events(self, limit: int = 30) -> List[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def clear_events(self):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM events")
        self.conn.commit()

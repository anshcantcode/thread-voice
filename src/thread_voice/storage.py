"""Small local notebook. A proposal ID is also its durable idempotency key."""

from pathlib import Path
from contextlib import closing
import sqlite3


class Notebook:
    def __init__(self, path: Path):
        self.path = path

    def save(self, proposal: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=3)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("INSERT OR IGNORE INTO notes (id, title, content) VALUES (?, ?, ?)",
                               (proposal["id"], proposal["title"], proposal["content"]))
            row = connection.execute("SELECT id, title, content, created_at FROM notes WHERE id = ?", (proposal["id"],)).fetchone()
        return dict(zip(("id", "title", "content", "created_at"), row))

    def recent(self) -> list[dict]:
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path, timeout=3)) as connection:
            rows = connection.execute("SELECT id, title, content, created_at FROM notes ORDER BY rowid DESC LIMIT 50").fetchall()
        return [dict(zip(("id", "title", "content", "created_at"), row)) for row in rows]

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  external_user_id TEXT,
  title TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
  content TEXT NOT NULL,
  external_msg_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
CREATE TABLE IF NOT EXISTS wechat_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_external_msg_id
  ON messages(external_msg_id)
  WHERE external_msg_id IS NOT NULL;
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_conversation(self, conversation_id: str, source: str, external_user_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations(id, source, external_user_id, title)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                """,
                (conversation_id, source, external_user_id, external_user_id),
            )

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        external_msg_id: str | None = None,
    ) -> bool:
        try:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO messages(conversation_id, role, content, external_msg_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (conversation_id, role, content, external_msg_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def recent_messages(self, conversation_id: str, limit: int) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at FROM messages
                WHERE conversation_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def list_conversations(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source, external_user_id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_messages(self, conversation_id: str, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, external_msg_id, created_at
                FROM messages
                WHERE conversation_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def recent_messages_all(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
                FROM messages m
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

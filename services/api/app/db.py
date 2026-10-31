from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  provider TEXT NOT NULL,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  created_at TEXT NOT NULL
);
"""

MIGRATION_2 = """
CREATE INDEX IF NOT EXISTS conversations_project_idx ON conversations(project_id);
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS memories_category_idx ON memories(category, updated_at);
CREATE INDEX IF NOT EXISTS memories_project_idx ON memories(project_id, updated_at);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(title, content, content='memories', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid,title,content) VALUES(new.rowid,new.title,new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts,rowid,title,content) VALUES('delete',old.rowid,old.title,old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts,rowid,title,content) VALUES('delete',old.rowid,old.title,old.content);
  INSERT INTO memories_fts(rowid,title,content) VALUES(new.rowid,new.title,new.content);
END;
CREATE TABLE IF NOT EXISTS conversation_summaries (
  conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  message_count INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  request TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','in_progress','blocked','done','cancelled')),
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks(status, updated_at);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  detail_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_events_created_idx ON audit_events(created_at);
CREATE TABLE IF NOT EXISTS agent_plans (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  steps_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS tool_registry (
  tool_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_approvals (
  id TEXT PRIMARY KEY,
  tool_id TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  args_json TEXT NOT NULL,
  preview TEXT NOT NULL,
  action_hash TEXT NOT NULL,
  risk_level INTEGER NOT NULL CHECK (risk_level BETWEEN 0 AND 3),
  status TEXT NOT NULL CHECK (status IN ('pending','approved','executed','cancelled','revoked','expired','failed')),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  result_json TEXT
);
CREATE INDEX IF NOT EXISTS tool_approvals_status_idx ON tool_approvals(status, created_at);
CREATE TABLE IF NOT EXISTS system_controls (
  control_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO system_controls(control_id,enabled,updated_at) VALUES('emergency_stop',0,'1970-01-01T00:00:00+00:00');
"""

MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL CHECK (job_type IN ('reminder')),
  title TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  due_at TEXT NOT NULL,
  interval_seconds INTEGER,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done','failed','cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_due_idx ON jobs(status,due_at);
CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  read_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notifications_created_idx ON notifications(created_at);
CREATE TABLE IF NOT EXISTS telemetry_devices (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telemetry_samples (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES telemetry_devices(id) ON DELETE CASCADE,
  sensor TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS telemetry_device_idx ON telemetry_samples(device_id,recorded_at);
"""

MIGRATION_5 = """
CREATE TABLE IF NOT EXISTS login_attempts (
  id TEXT PRIMARY KEY,
  remote_key TEXT NOT NULL,
  attempted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS login_attempts_key_idx ON login_attempts(remote_key,attempted_at);
"""

MIGRATION_6 = """
CREATE TABLE IF NOT EXISTS google_oauth_states (
  state_hash TEXT PRIMARY KEY,
  service TEXT NOT NULL CHECK (service IN ('gmail', 'calendar')),
  verifier_encrypted TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS google_oauth_states_expiry_idx ON google_oauth_states(expires_at);
CREATE TABLE IF NOT EXISTS google_connections (
  service TEXT PRIMARY KEY CHECK (service IN ('gmail', 'calendar')),
  refresh_token_encrypted TEXT NOT NULL,
  scopes_json TEXT NOT NULL,
  connected_at TEXT NOT NULL
);
"""

DB_SCHEMA_VERSION = 6


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: Path) -> None:
    with connect(path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.executescript(SCHEMA)
        if version < 2:
            columns = {
                item["name"]
                for item in connection.execute("PRAGMA table_info(conversations)")
            }
            if "project_id" not in columns:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN project_id TEXT REFERENCES projects(id)"
                )
            if "agent_id" not in columns:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN agent_id TEXT NOT NULL DEFAULT 'orchestrator'"
                )
            connection.executescript(MIGRATION_2)
            connection.execute("PRAGMA user_version = 2")
            version = 2
        if version < 3:
            connection.executescript(MIGRATION_3)
            connection.execute("PRAGMA user_version = 3")
            version = 3
        if version < 4:
            connection.executescript(MIGRATION_4)
            connection.execute("PRAGMA user_version = 4")
            version = 4
        if version < 5:
            connection.executescript(MIGRATION_5)
            connection.execute("PRAGMA user_version = 5")
            version = 5
        if version < 6:
            connection.executescript(MIGRATION_6)
            connection.execute("PRAGMA user_version = 6")


def rows(connection: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def row(connection: sqlite3.Connection, query: str, params: tuple = ()) -> dict | None:
    result = connection.execute(query, params).fetchone()
    return dict(result) if result else None

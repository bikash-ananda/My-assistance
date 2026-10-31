import sqlite3

import pytest

from app import db
from scripts import database_maintenance as maintenance


def make_v6_backup(path):
    db.initialize(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("INSERT INTO projects(id,name,notes,created_at) VALUES('restored-project','Restored project','','2026-10-31T00:00:00+00:00')")
        connection.execute("DROP TABLE sales_opportunities")
        connection.execute("DROP TABLE business_contacts")
        connection.execute("PRAGMA user_version=6")


def test_restore_migrates_older_backup_and_preserves_pre_restore_snapshot(tmp_path, monkeypatch):
    selected = tmp_path / "older.sqlite3"
    live = tmp_path / "live.sqlite3"
    make_v6_backup(selected)
    db.initialize(live)
    with sqlite3.connect(live) as connection:
        connection.execute("INSERT INTO projects(id,name,notes,created_at) VALUES('current-project','Current project','','2026-10-31T00:00:00+00:00')")

    monkeypatch.setattr(maintenance, "ROOT", tmp_path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "RESTORE")
    maintenance.restore(live, selected)

    with sqlite3.connect(live) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == db.DB_SCHEMA_VERSION
        projects = connection.execute("SELECT id FROM projects ORDER BY id").fetchall()
        assert projects == [("restored-project",)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='business_contacts'").fetchone()
    with sqlite3.connect(selected) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
    backups = list((tmp_path / "backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT id FROM projects").fetchone()[0] == "current-project"


def test_restore_rejects_a_backup_from_a_newer_release(tmp_path):
    selected = tmp_path / "future.sqlite3"
    with sqlite3.connect(selected) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="not supported"):
        maintenance.prepare_restore(selected)

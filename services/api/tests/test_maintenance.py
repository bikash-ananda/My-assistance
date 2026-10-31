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


def test_backup_keeps_a_supported_older_schema(tmp_path, monkeypatch):
    older = tmp_path / "older-live.sqlite3"
    make_v6_backup(older)
    monkeypatch.setattr(maintenance, "ROOT", tmp_path)
    saved = maintenance.backup(older)
    with sqlite3.connect(saved) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6


def test_restore_failure_rolls_back_an_older_live_database(tmp_path, monkeypatch):
    selected = tmp_path / "selected.sqlite3"
    live = tmp_path / "live.sqlite3"
    make_v6_backup(selected)
    make_v6_backup(live)
    with sqlite3.connect(live) as connection:
        connection.execute("UPDATE projects SET name='Must survive' WHERE id='restored-project'")
    monkeypatch.setattr(maintenance, "ROOT", tmp_path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "RESTORE")
    real_copy = maintenance.copy_database
    attempts = 0

    def fail_first_copy(source, destination, *, allow_older=False):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated restore copy failure")
        return real_copy(source, destination, allow_older=allow_older)

    monkeypatch.setattr(maintenance, "copy_database", fail_first_copy)
    with pytest.raises(RuntimeError, match="simulated restore copy failure"):
        maintenance.restore(live, selected)
    with sqlite3.connect(live) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        assert connection.execute("SELECT name FROM projects WHERE id='restored-project'").fetchone()[0] == "Must survive"

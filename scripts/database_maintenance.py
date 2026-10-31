from __future__ import annotations

import argparse
from contextlib import closing
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app import db  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import DB_SCHEMA_VERSION  # noqa: E402


def verify(connection: sqlite3.Connection, *, allow_older: bool = False) -> int:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if result != "ok":
        raise RuntimeError("SQLite integrity check failed.")
    if version > DB_SCHEMA_VERSION or version < 0:
        raise RuntimeError(f"Backup schema version {version} is not supported by this release.")
    if not allow_older and version != DB_SCHEMA_VERSION:
        raise RuntimeError(f"Expected schema version {DB_SCHEMA_VERSION}; backup has version {version}.")
    return version


def prepare_restore(source_path: Path) -> tuple[tempfile.TemporaryDirectory, Path, int]:
    """Validate and migrate a private working copy without changing the selected backup."""
    temporary = tempfile.TemporaryDirectory(prefix="bikash-ai-restore-")
    prepared_path = Path(temporary.name) / "workspace.sqlite3"
    try:
        with closing(sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=10)) as source:
            source_version = verify(source, allow_older=True)
            with closing(sqlite3.connect(prepared_path, timeout=10)) as prepared:
                source.backup(prepared)
        db.initialize(prepared_path)
        with closing(sqlite3.connect(prepared_path, timeout=10)) as prepared:
            verify(prepared)
        return temporary, prepared_path, source_version
    except Exception:
        temporary.cleanup()
        raise


def copy_database(source_path: Path, destination_path: Path) -> None:
    """Copy and validate in a short-lived frame so Windows releases the file handle."""
    with closing(sqlite3.connect(source_path, timeout=10)) as source:
        with closing(sqlite3.connect(destination_path, timeout=10)) as target:
            source.backup(target)
            verify(target)


def backup(database: Path) -> Path:
    if not database.exists():
        raise RuntimeError("Workspace database was not found.")
    destination_dir = ROOT / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    name = "bikash-ai-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".sqlite3"
    destination = destination_dir / name
    with sqlite3.connect(database, timeout=10) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        verify(target)
    return destination


def restore(database: Path, source_path: Path) -> None:
    source_path = source_path.expanduser().resolve(strict=True)
    database = database.resolve()
    if source_path == database:
        raise RuntimeError("The backup path must be different from the live database.")
    temporary, prepared_path, source_version = prepare_restore(source_path)
    try:
        if source_version < DB_SCHEMA_VERSION:
            print(f"The selected schema version {source_version} will be upgraded to {DB_SCHEMA_VERSION} before restore.")
        print(f"This will replace workspace data in: {database}")
        print("Stop the API and worker before continuing. A pre-restore backup will be created first.")
        if input("Type RESTORE to continue: ").strip() != "RESTORE":
            print("Restore cancelled.")
            return
        pre_restore = backup(database)
        try:
            copy_database(prepared_path, database)
        except Exception:
            copy_database(pre_restore, database)
            raise
        print(f"Workspace restored. Previous data saved to: {pre_restore}")
    finally:
        temporary.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bikash AI SQLite maintenance")
    parser.add_argument("action", choices=("backup", "restore", "check"))
    parser.add_argument("--from", dest="source", type=Path)
    args = parser.parse_args()
    database = Settings.from_env().database_path
    if args.action == "backup":
        print(backup(database))
    elif args.action == "restore":
        if args.source is None:
            parser.error("restore requires --from <backup-path>")
        restore(database, args.source)
    else:
        with sqlite3.connect(database, timeout=10) as connection:
            verify(connection)
        print("Database integrity check passed.")


if __name__ == "__main__":
    main()

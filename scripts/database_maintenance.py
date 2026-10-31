from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.config import Settings  # noqa: E402


def verify(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if result != "ok":
        raise RuntimeError("SQLite integrity check failed.")
    if version != 8:
        raise RuntimeError(f"Expected schema version 8; backup has version {version}.")


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
    with sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=10) as source:
        verify(source)
        check = source.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError("The selected backup did not pass integrity check.")
    print(f"This will replace workspace data in: {database}")
    print("Stop the API and worker before continuing. A pre-restore backup will be created first.")
    if input("Type RESTORE to continue: ").strip() != "RESTORE":
        print("Restore cancelled.")
        return
    pre_restore = backup(database)
    try:
        with sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=10) as source:
            with sqlite3.connect(database, timeout=10) as target:
                source.backup(target)
                verify(target)
    except Exception:
        with sqlite3.connect(f"file:{pre_restore.as_posix()}?mode=ro", uri=True, timeout=10) as source:
            with sqlite3.connect(database, timeout=10) as target:
                source.backup(target)
                verify(target)
        raise
    print(f"Workspace restored. Previous database saved to: {pre_restore}")


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

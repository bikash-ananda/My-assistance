from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from . import db
from .config import Settings


def register_phase10_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    @app.get("/api/v1/maintenance/status")
    def maintenance_status(_: None = Depends(require_owner)) -> dict:
        try:
            with db.connect(settings.database_path) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                pending = connection.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]
            return {"database": "ok" if integrity == "ok" else "error", "schema_version": version, "size_bytes": settings.database_path.stat().st_size if settings.database_path.exists() else 0, "pending_jobs": pending}
        except sqlite3.Error:
            raise HTTPException(503, "Database health check failed.")

    @app.get("/api/v1/maintenance/backup")
    def download_backup(_: None = Depends(require_owner)) -> Response:
        if not settings.database_path.exists():
            raise HTTPException(404, "Workspace database is not available.")
        file_size = settings.database_path.stat().st_size
        if file_size > 500 * 1024 * 1024:
            raise HTTPException(413, "Database is larger than the in-memory backup limit.")
        try:
            with sqlite3.connect(settings.database_path, timeout=10) as source:
                snapshot = sqlite3.connect(":memory:")
                source.backup(snapshot)
                data = snapshot.serialize()
                snapshot.close()
        except sqlite3.Error:
            raise HTTPException(503, "A consistent database snapshot could not be created.")
        filename = "bikash-ai-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".sqlite3"
        return Response(
            content=data,
            media_type="application/vnd.sqlite3",
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
        )

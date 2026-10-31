from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .config import Settings
from .google_integration import register_google_routes
from .knowledge import contains_secret


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReminderBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=800)
    due_at: str = Field(min_length=20, max_length=40)
    interval_seconds: int | None = Field(default=None, ge=60, le=31_536_000)


def register_phase4_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    register_google_routes(app, settings, require_owner)

    @app.get("/api/v1/jobs")
    def list_jobs(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            jobs = db.rows(connection, "SELECT * FROM jobs ORDER BY due_at LIMIT 200")
        for job in jobs:
            job["payload"] = json.loads(job.pop("payload_json"))
        return jobs

    @app.post("/api/v1/jobs", status_code=201)
    def create_reminder(body: ReminderBody, _: None = Depends(require_owner)) -> dict:
        if contains_secret(body.title + "\n" + body.body):
            raise HTTPException(400, "Remove credentials from the reminder.")
        try:
            due = datetime.fromisoformat(body.due_at)
            if due.tzinfo is None:
                raise ValueError("timezone required")
            due = due.astimezone(timezone.utc)
        except ValueError:
            raise HTTPException(400, "Reminder time must include a timezone.")
        if due < datetime.now(timezone.utc) - timedelta(minutes=1) or due > datetime.now(timezone.utc) + timedelta(days=366):
            raise HTTPException(400, "Choose a time from now through one year ahead.")
        job_id, now = str(uuid4()), stamp()
        with db.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO jobs(id,job_type,title,payload_json,due_at,interval_seconds,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'pending',?,?)",
                (job_id, "reminder", body.title.strip(), json.dumps({"body": body.body.strip()}, ensure_ascii=False), due.isoformat(), body.interval_seconds, now, now),
            )
            connection.execute(
                "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid4()), "job.reminder.created", "job", job_id, json.dumps({"interval_seconds": body.interval_seconds}), now),
            )
            return db.row(connection, "SELECT * FROM jobs WHERE id=?", (job_id,)) or {}

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=? AND status='pending'", (stamp(), job_id)).rowcount
            if not changed:
                raise HTTPException(404, "Pending reminder not found.")
        return {"id": job_id, "status": "cancelled"}

    @app.get("/api/v1/notifications")
    def list_notifications(
        unread_only: bool = False,
        limit: int = Query(default=50, ge=1, le=200),
        _: None = Depends(require_owner),
    ) -> list[dict]:
        where = " WHERE read_at IS NULL" if unread_only else ""
        with db.connect(settings.database_path) as connection:
            return db.rows(connection, "SELECT * FROM notifications" + where + " ORDER BY created_at DESC LIMIT ?", (limit,))

    @app.post("/api/v1/notifications/{notification_id}/read")
    def mark_notification_read(notification_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE notifications SET read_at=? WHERE id=? AND read_at IS NULL", (stamp(), notification_id)).rowcount
            if not changed:
                raise HTTPException(404, "Unread notification not found.")
        return {"id": notification_id, "read": True}

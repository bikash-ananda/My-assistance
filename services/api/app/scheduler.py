from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from . import db

logger = logging.getLogger("bikash.scheduler")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_once(database_path) -> int:
    """Atomically turn due reminder jobs into in-app notifications."""
    with db.connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        now = timestamp()
        job = db.row(
            connection,
            "SELECT * FROM jobs WHERE status='pending' AND due_at<=? ORDER BY due_at LIMIT 1",
            (now,),
        )
        if not job:
            return 0
        payload = json.loads(job["payload_json"])
        connection.execute(
            "INSERT INTO notifications(id,job_id,title,body,created_at) VALUES(?,?,?,?,?)",
            (str(uuid4()), job["id"], job["title"], payload.get("body", ""), now),
        )
        if job["interval_seconds"]:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=job["interval_seconds"])).isoformat()
            connection.execute(
                "UPDATE jobs SET status='pending',attempts=attempts+1,due_at=?,updated_at=? WHERE id=?",
                (next_run, now, job["id"]),
            )
        else:
            connection.execute(
                "UPDATE jobs SET status='done',attempts=attempts+1,updated_at=? WHERE id=?",
                (now, job["id"]),
            )
        return 1


def serve(database_path, poll_seconds: float = 5) -> None:
    logger.info("Reminder worker started; polling every %.1f seconds", poll_seconds)
    while True:
        try:
            while run_once(database_path):
                pass
        except Exception:
            logger.exception("Reminder worker tick failed; it will retry on the next poll")
        time.sleep(poll_seconds)

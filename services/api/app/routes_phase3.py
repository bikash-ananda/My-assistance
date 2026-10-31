from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import db
from .config import Settings
from .tools_runtime import BY_ID, CATALOG, ToolInputError, execute, preview_text, project_root, safe_path, validate


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(tool_id: str, project_id: str, args: dict) -> str:
    exact = json.dumps({"tool_id": tool_id, "project_id": project_id, "args": args}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(exact.encode("utf-8")).hexdigest()


def write_audit(connection, action: str, target_id: str | None, detail: dict) -> None:
    connection.execute(
        "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid4()), action, "tool", target_id, json.dumps(detail, ensure_ascii=False), stamp()),
    )


def install_catalog(connection) -> None:
    time = stamp()
    for tool in CATALOG:
        connection.execute(
            "INSERT OR IGNORE INTO tool_registry(tool_id,enabled,updated_at) VALUES(?,?,?)",
            (tool["id"], 1, time),
        )


class PreviewBody(BaseModel):
    tool_id: str = Field(min_length=1, max_length=80)
    project_id: str = Field(min_length=1, max_length=80)
    args: dict[str, Any] = Field(default_factory=dict)


class ToolToggle(BaseModel):
    enabled: bool


class StopBody(BaseModel):
    enabled: bool


def register_phase3_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    @app.get("/api/v1/tools")
    def get_tools(_: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            install_catalog(connection)
            enabled = {row["tool_id"]: bool(row["enabled"]) for row in db.rows(connection, "SELECT tool_id,enabled FROM tool_registry")}
            control = db.row(connection, "SELECT enabled FROM system_controls WHERE control_id='emergency_stop'")
        return {"tools": [{**tool, "enabled": enabled.get(tool["id"], False)} for tool in CATALOG], "emergency_stop": bool(control and control["enabled"])}

    @app.patch("/api/v1/tools/{tool_id}")
    def update_tool(tool_id: str, body: ToolToggle, _: None = Depends(require_owner)) -> dict:
        if tool_id not in BY_ID:
            raise HTTPException(404, "Tool not found.")
        with db.connect(settings.database_path) as connection:
            install_catalog(connection)
            connection.execute("UPDATE tool_registry SET enabled=?,updated_at=? WHERE tool_id=?", (int(body.enabled), stamp(), tool_id))
            if not body.enabled:
                connection.execute("UPDATE tool_approvals SET status='revoked',updated_at=? WHERE tool_id=? AND status IN ('pending','approved')", (stamp(), tool_id))
            write_audit(connection, "tool.enabled" if body.enabled else "tool.disabled", tool_id, {})
        return {"tool_id": tool_id, "enabled": body.enabled}

    @app.post("/api/v1/tools/preview", status_code=201)
    def create_preview(body: PreviewBody, _: None = Depends(require_owner)) -> dict:
        if body.tool_id not in BY_ID:
            raise HTTPException(404, "Tool not found.")
        try:
            args = validate(body.tool_id, body.args)
        except ToolInputError as exc:
            raise HTTPException(400, str(exc))
        approval_id, time = str(uuid4()), stamp()
        with db.connect(settings.database_path) as connection:
            install_catalog(connection)
            tool_status = db.row(connection, "SELECT enabled FROM tool_registry WHERE tool_id=?", (body.tool_id,))
            if not tool_status or not tool_status["enabled"]:
                raise HTTPException(403, "This tool is disabled.")
            project = db.row(connection, "SELECT id,name,root_path,status FROM projects WHERE id=?", (body.project_id,))
            if body.tool_id != "system.version" and (not project or project["status"] != "active"):
                raise HTTPException(404, "Active project not found.")
            if body.tool_id != "system.version":
                try:
                    root = project_root(project["root_path"])
                    if body.tool_id in {"files.list", "files.search"}:
                        folder = safe_path(root, args.get("path", "."))
                        if not folder.is_dir():
                            raise ToolInputError("That folder does not exist.")
                    if body.tool_id == "files.read":
                        target = safe_path(root, args["path"])
                        if not target.is_file():
                            raise ToolInputError("That file does not exist.")
                    if body.tool_id == "files.create":
                        target = safe_path(root, args["path"])
                        if target.exists():
                            raise ToolInputError("The destination already exists; this tool never overwrites files.")
                except ToolInputError as exc:
                    raise HTTPException(400, str(exc))
            name = project["name"] if project else "system"
            level = BY_ID[body.tool_id]["risk_level"]
            text = preview_text(body.tool_id, name, args)
            digest = canonical_hash(body.tool_id, body.project_id, args)
            expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            connection.execute(
                "INSERT INTO tool_approvals(id,tool_id,project_id,args_json,preview,action_hash,risk_level,status,expires_at,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (approval_id, body.tool_id, body.project_id, json.dumps(args, ensure_ascii=False, sort_keys=True), text, digest, level, "pending", expires, time, time),
            )
            write_audit(connection, "tool.preview.created", approval_id, {"tool_id": body.tool_id, "risk_level": level, "action_hash": digest})
            return {"id": approval_id, "tool_id": body.tool_id, "project_id": body.project_id, "args": args, "preview": text, "action_hash": digest, "risk_level": level, "status": "pending", "expires_at": expires, "requires_approval": level >= 2}

    @app.get("/api/v1/approvals")
    def get_approvals(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            return db.rows(connection, "SELECT id,tool_id,project_id,args_json,preview,action_hash,risk_level,status,expires_at,created_at,updated_at,result_json FROM tool_approvals ORDER BY created_at DESC LIMIT 100")

    @app.post("/api/v1/approvals/{approval_id}/approve")
    def approve(approval_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            record = db.row(connection, "SELECT * FROM tool_approvals WHERE id=?", (approval_id,))
            if not record:
                raise HTTPException(404, "Action preview not found.")
            if datetime.fromisoformat(record["expires_at"]) <= datetime.now(timezone.utc):
                connection.execute("UPDATE tool_approvals SET status='expired',updated_at=? WHERE id=?", (stamp(), approval_id))
                raise HTTPException(410, "Action preview expired. Create a new preview.")
            args = json.loads(record["args_json"])
            if canonical_hash(record["tool_id"], record["project_id"], args) != record["action_hash"]:
                connection.execute("UPDATE tool_approvals SET status='revoked',updated_at=? WHERE id=?", (stamp(), approval_id))
                raise HTTPException(409, "Action details changed; create a new preview.")
            if record["status"] != "pending" or record["risk_level"] < 2:
                raise HTTPException(409, "This action is not awaiting owner approval.")
            connection.execute("UPDATE tool_approvals SET status='approved',updated_at=? WHERE id=?", (stamp(), approval_id))
            write_audit(connection, "tool.action.approved", approval_id, {"tool_id": record["tool_id"], "action_hash": record["action_hash"]})
            return {"id": approval_id, "status": "approved", "action_hash": record["action_hash"]}

    @app.post("/api/v1/approvals/{approval_id}/execute")
    def execute_preview(approval_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            record = db.row(connection, "SELECT * FROM tool_approvals WHERE id=?", (approval_id,))
            if not record:
                raise HTTPException(404, "Action preview not found.")
            stop = db.row(connection, "SELECT enabled FROM system_controls WHERE control_id='emergency_stop'")
            if stop and stop["enabled"]:
                raise HTTPException(423, "Emergency stop is active.")
            if datetime.fromisoformat(record["expires_at"]) <= datetime.now(timezone.utc):
                connection.execute("UPDATE tool_approvals SET status='expired',updated_at=? WHERE id=?", (stamp(), approval_id))
                raise HTTPException(410, "Action preview expired. Create a new preview.")
            args = json.loads(record["args_json"])
            if canonical_hash(record["tool_id"], record["project_id"], args) != record["action_hash"]:
                connection.execute("UPDATE tool_approvals SET status='revoked',updated_at=? WHERE id=?", (stamp(), approval_id))
                raise HTTPException(409, "Action details changed; create a new preview.")
            tool_status = db.row(connection, "SELECT enabled FROM tool_registry WHERE tool_id=?", (record["tool_id"],))
            if not tool_status or not tool_status["enabled"]:
                raise HTTPException(403, "This tool is disabled.")
            allowed = record["status"] == "approved" if record["risk_level"] >= 2 else record["status"] == "pending"
            if not allowed:
                raise HTTPException(409, "This action is not ready to run.")
            project = db.row(connection, "SELECT root_path FROM projects WHERE id=? AND status='active'", (record["project_id"],))
            if record["tool_id"] != "system.version" and not project:
                raise HTTPException(404, "Active project not found.")
            try:
                safe_args = validate(record["tool_id"], args)
                root = project_root(project["root_path"]) if project else None
                result = execute(record["tool_id"], root, safe_args)
            except (ToolInputError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
                connection.execute("UPDATE tool_approvals SET status='failed',updated_at=? WHERE id=?", (stamp(), approval_id))
                write_audit(connection, "tool.action.failed", approval_id, {"tool_id": record["tool_id"], "reason": type(exc).__name__})
                raise HTTPException(400, str(exc) if isinstance(exc, ToolInputError) else "Tool execution failed safely.")
            output = {"untrusted": True, **result}
            stamp_now = stamp()
            connection.execute("UPDATE tool_approvals SET status='executed',result_json=?,updated_at=? WHERE id=?", (json.dumps(output, ensure_ascii=False), stamp_now, approval_id))
            write_audit(connection, "tool.action.executed", approval_id, {"tool_id": record["tool_id"], "action_hash": record["action_hash"]})
            return {"id": approval_id, "status": "executed", "result": output}

    @app.post("/api/v1/approvals/{approval_id}/cancel")
    def cancel_preview(approval_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE tool_approvals SET status='cancelled',updated_at=? WHERE id=? AND status IN ('pending','approved')", (stamp(), approval_id)).rowcount
            if not changed:
                raise HTTPException(404, "Open action preview not found.")
            write_audit(connection, "tool.action.cancelled", approval_id, {})
        return {"id": approval_id, "status": "cancelled"}

    @app.get("/api/v1/system/emergency-stop")
    def get_emergency_stop(_: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            record = db.row(connection, "SELECT enabled,updated_at FROM system_controls WHERE control_id='emergency_stop'")
        return {"enabled": bool(record and record["enabled"]), "updated_at": record["updated_at"] if record else None}

    @app.put("/api/v1/system/emergency-stop")
    def set_emergency_stop(body: StopBody, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            now = stamp()
            connection.execute("UPDATE system_controls SET enabled=?,updated_at=? WHERE control_id='emergency_stop'", (int(body.enabled), now))
            if body.enabled:
                connection.execute("UPDATE tool_approvals SET status='revoked',updated_at=? WHERE status IN ('pending','approved')", (now,))
            write_audit(connection, "system.emergency_stop.enabled" if body.enabled else "system.emergency_stop.disabled", None, {})
        return {"enabled": body.enabled, "updated_at": now}

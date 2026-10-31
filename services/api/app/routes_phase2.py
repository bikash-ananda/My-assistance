from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .agents import AGENTS, BY_ID, list_agents, make_plan, route_intent
from .config import Settings
from .knowledge import CATEGORIES, KINDS, contains_secret, extractive_summary, search_memories


MemoryCategory = Literal[
    "owner_preference",
    "professional_profile",
    "project",
    "technical_decision",
    "business",
    "customer_contact",
    "conversation_summary",
    "task_history",
    "research",
    "operations",
]
MemoryKind = Literal["confirmed", "preference", "temporary", "assumption", "unverified"]
TaskStatus = Literal["planned", "in_progress", "blocked", "done", "cancelled"]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(connection, action: str, target_type: str, target_id: str | None, detail: dict) -> None:
    connection.execute(
        "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid4()), action, target_type, target_id, json.dumps(detail, ensure_ascii=False), timestamp()),
    )


def active_project(connection, project_id: str | None) -> dict | None:
    if not project_id:
        return None
    project = db.row(
        connection,
        "SELECT id,name,notes,root_path FROM projects WHERE id=? AND status='active'",
        (project_id,),
    )
    if not project:
        raise HTTPException(404, "Active project not found.")
    return project


class MemoryBody(BaseModel):
    category: MemoryCategory
    kind: MemoryKind = "confirmed"
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None
    source: str = Field(default="owner", min_length=1, max_length=240)
    confidence: float | None = Field(default=None, ge=0, le=1)


class MemoryPatch(BaseModel):
    category: MemoryCategory | None = None
    kind: MemoryKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    project_id: str | None = None
    source: str | None = Field(default=None, min_length=1, max_length=240)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    project_id: str | None = None
    agent_id: str | None = None


class RouteBody(BaseModel):
    request: str = Field(min_length=1, max_length=8000)


class PlanBody(RouteBody):
    agent_id: str | None = None
    project_id: str | None = None


class TaskPatch(BaseModel):
    status: TaskStatus


def register_phase2_routes(
    app: FastAPI,
    settings: Settings,
    require_owner,
) -> None:
    @app.get("/api/v1/agents")
    def get_agents(_: None = Depends(require_owner)) -> list[dict]:
        return list_agents()

    @app.post("/api/v1/agents/route")
    def route_agent(body: RouteBody, _: None = Depends(require_owner)) -> dict:
        return route_intent(body.request)

    @app.post("/api/v1/agents/plan", status_code=201)
    def create_agent_plan(body: PlanBody, _: None = Depends(require_owner)) -> dict:
        selected = body.agent_id
        if selected is None:
            selected = route_intent(body.request)["agent"]
        if selected not in BY_ID:
            raise HTTPException(400, "Unknown agent.")
        stamp, task_id, plan_id = timestamp(), str(uuid4()), str(uuid4())
        with db.connect(settings.database_path) as connection:
            active_project(connection, body.project_id)
            if contains_secret(body.request):
                raise HTTPException(400, "Remove credentials before saving this task.")
            title = " ".join(body.request.split())[:120]
            steps = make_plan(selected, body.request)
            connection.execute(
                "INSERT INTO tasks(id,title,request,agent_id,status,project_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (task_id, title, body.request, selected, "planned", body.project_id, stamp, stamp),
            )
            connection.execute(
                "INSERT INTO agent_plans(id,task_id,steps_json,created_at,updated_at) VALUES(?,?,?,?,?)",
                (plan_id, task_id, json.dumps(steps), stamp, stamp),
            )
            audit(connection, "agent.plan.created", "task", task_id, {"agent_id": selected})
            return {"task": db.row(connection, "SELECT * FROM tasks WHERE id=?", (task_id,)), "steps": steps}

    @app.patch("/api/v1/conversations/{conversation_id}")
    def update_conversation(
        conversation_id: str, body: ConversationPatch, _: None = Depends(require_owner)
    ) -> dict:
        fields = body.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(400, "No changes supplied.")
        for key in ("title", "agent_id"):
            if key in fields and fields[key] is None:
                raise HTTPException(400, "This conversation field cannot be cleared.")
        if fields.get("title") and contains_secret(fields["title"]):
            raise HTTPException(400, "Remove credentials from the conversation title.")
        if fields.get("agent_id") and fields["agent_id"] not in BY_ID:
            raise HTTPException(400, "Unknown agent.")
        stamp = timestamp()
        with db.connect(settings.database_path) as connection:
            if not db.row(connection, "SELECT id FROM conversations WHERE id=?", (conversation_id,)):
                raise HTTPException(404, "Conversation not found.")
            if "project_id" in fields:
                active_project(connection, fields["project_id"])
            assignments = ", ".join(key + "=?" for key in fields)
            connection.execute(
                "UPDATE conversations SET " + assignments + ",updated_at=? WHERE id=?",
                (*fields.values(), stamp, conversation_id),
            )
            audit(connection, "conversation.updated", "conversation", conversation_id, {"fields": sorted(fields)})
            return db.row(connection, "SELECT * FROM conversations WHERE id=?", (conversation_id,)) or {}
    @app.get("/api/v1/tasks")
    def list_tasks(
        status: TaskStatus | None = None,
        project_id: str | None = None,
        _: None = Depends(require_owner),
    ) -> list[dict]:
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        if project_id:
            where.append("project_id=?")
            params.append(project_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with db.connect(settings.database_path) as connection:
            tasks = db.rows(connection, "SELECT * FROM tasks" + clause + " ORDER BY updated_at DESC", tuple(params))
            for task in tasks:
                plan = db.row(
                    connection,
                    "SELECT steps_json FROM agent_plans WHERE task_id=? ORDER BY updated_at DESC LIMIT 1",
                    (task["id"],),
                )
                task["steps"] = json.loads(plan["steps_json"]) if plan else []
            return tasks

    @app.patch("/api/v1/tasks/{task_id}")
    def update_task(task_id: str, body: TaskPatch, _: None = Depends(require_owner)) -> dict:
        stamp = timestamp()
        with db.connect(settings.database_path) as connection:
            changed = connection.execute(
                "UPDATE tasks SET status=?,updated_at=? WHERE id=?",
                (body.status, stamp, task_id),
            ).rowcount
            if not changed:
                raise HTTPException(404, "Task not found.")
            audit(connection, "task.status.updated", "task", task_id, {"status": body.status})
            task = db.row(connection, "SELECT * FROM tasks WHERE id=?", (task_id,)) or {}
            plan = db.row(connection, "SELECT steps_json FROM agent_plans WHERE task_id=?", (task_id,))
            task["steps"] = json.loads(plan["steps_json"]) if plan else []
            return task

    @app.post("/api/v1/tasks/{task_id}/steps/{step_id}/complete")
    def complete_task_step(task_id: str, step_id: str, _: None = Depends(require_owner)) -> dict:
        stamp = timestamp()
        with db.connect(settings.database_path) as connection:
            plan = db.row(
                connection,
                "SELECT id,steps_json FROM agent_plans WHERE task_id=? ORDER BY updated_at DESC LIMIT 1",
                (task_id,),
            )
            if not plan:
                raise HTTPException(404, "Task plan not found.")
            steps = json.loads(plan["steps_json"])
            match = next((step for step in steps if step["id"] == step_id), None)
            if match is None:
                raise HTTPException(404, "Plan step not found.")
            match["status"] = "done"
            connection.execute(
                "UPDATE agent_plans SET steps_json=?,updated_at=? WHERE id=?",
                (json.dumps(steps), stamp, plan["id"]),
            )
            status = "done" if all(step["status"] == "done" for step in steps) else "in_progress"
            connection.execute(
                "UPDATE tasks SET status=?,updated_at=? WHERE id=?", (status, stamp, task_id)
            )
            audit(connection, "task.step.completed", "task", task_id, {"step_id": step_id})
            return {"task_id": task_id, "status": status, "steps": steps}

    @app.get("/api/v1/memories")
    def list_memories(
        category: MemoryCategory | None = None,
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=250),
        _: None = Depends(require_owner),
    ) -> list[dict]:
        where, params = [], []
        if category:
            where.append("category=?")
            params.append(category)
        if project_id:
            where.append("(project_id=? OR project_id IS NULL)")
            params.append(project_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with db.connect(settings.database_path) as connection:
            return db.rows(
                connection,
                "SELECT * FROM memories" + clause + " ORDER BY updated_at DESC LIMIT ?",
                (*params, limit),
            )

    @app.get("/api/v1/memories/search")
    def search_memory_records(
        q: str = Query(min_length=1, max_length=160),
        limit: int = Query(default=20, ge=1, le=100),
        _: None = Depends(require_owner),
    ) -> list[dict]:
        pattern = "%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%"
        with db.connect(settings.database_path) as connection:
            return db.rows(
                connection,
                "SELECT * FROM memories WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' "
                "ORDER BY updated_at DESC LIMIT ?",
                (pattern, pattern, limit),
            )

    @app.get("/api/v1/memories/export")
    def export_memories(_: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            records = db.rows(connection, "SELECT * FROM memories ORDER BY category,title")
        return {"exported_at": timestamp(), "memories": records}

    @app.post("/api/v1/memories", status_code=201)
    def create_memory(body: MemoryBody, _: None = Depends(require_owner)) -> dict:
        if contains_secret(body.title + "\n" + body.content):
            raise HTTPException(400, "This looks like a credential. Store secrets in a secret manager, not memory.")
        memory_id, stamp = str(uuid4()), timestamp()
        with db.connect(settings.database_path) as connection:
            active_project(connection, body.project_id)
            connection.execute(
                "INSERT INTO memories(id,category,kind,title,content,project_id,source,confidence,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    memory_id, body.category, body.kind, body.title.strip(), body.content.strip(),
                    body.project_id, body.source.strip(), body.confidence, stamp, stamp,
                ),
            )
            audit(connection, "memory.created", "memory", memory_id, {"category": body.category, "kind": body.kind})
            return db.row(connection, "SELECT * FROM memories WHERE id=?", (memory_id,)) or {}

    @app.patch("/api/v1/memories/{memory_id}")
    def update_memory(memory_id: str, body: MemoryPatch, _: None = Depends(require_owner)) -> dict:
        fields = body.model_dump(exclude_unset=True)
        if any(fields.get(key) is None for key in ("category", "kind", "title", "content", "source") if key in fields):
            raise HTTPException(400, "Memory fields cannot be cleared.")
        if not fields:
            raise HTTPException(400, "No changes supplied.")
        with db.connect(settings.database_path) as connection:
            existing = db.row(connection, "SELECT * FROM memories WHERE id=?", (memory_id,))
            if not existing:
                raise HTTPException(404, "Memory not found.")
            combined_title = fields.get("title", existing["title"]) or existing["title"]
            combined_content = fields.get("content", existing["content"]) or existing["content"]
            if contains_secret(combined_title + "\n" + combined_content):
                raise HTTPException(400, "This looks like a credential. Store secrets in a secret manager, not memory.")
            if "project_id" in fields:
                active_project(connection, fields["project_id"])
            assignments = ", ".join(key + "=?" for key in fields)
            connection.execute(
                "UPDATE memories SET " + assignments + ",updated_at=? WHERE id=?",
                (*fields.values(), timestamp(), memory_id),
            )
            audit(connection, "memory.updated", "memory", memory_id, {"fields": sorted(fields)})
            return db.row(connection, "SELECT * FROM memories WHERE id=?", (memory_id,)) or {}

    @app.delete("/api/v1/memories/{memory_id}")
    def delete_memory(memory_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("DELETE FROM memories WHERE id=?", (memory_id,)).rowcount
            if not changed:
                raise HTTPException(404, "Memory not found.")
            audit(connection, "memory.deleted", "memory", memory_id, {})
        return {"deleted": True}

    @app.get("/api/v1/conversations/{conversation_id}/summary")
    def get_summary(conversation_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            if not db.row(connection, "SELECT id FROM conversations WHERE id=?", (conversation_id,)):
                raise HTTPException(404, "Conversation not found.")
            summary = db.row(
                connection,
                "SELECT summary,message_count,updated_at FROM conversation_summaries WHERE conversation_id=?",
                (conversation_id,),
            )
        return summary or {"summary": "", "message_count": 0, "updated_at": None}

    @app.post("/api/v1/conversations/{conversation_id}/summarize")
    def summarize_conversation(conversation_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            if not db.row(connection, "SELECT id FROM conversations WHERE id=?", (conversation_id,)):
                raise HTTPException(404, "Conversation not found.")
            messages = db.rows(
                connection,
                "SELECT role,content FROM messages WHERE conversation_id=? "
                "ORDER BY created_at DESC,rowid DESC LIMIT 200",
                (conversation_id,),
            )
            messages.reverse()
            if not messages:
                raise HTTPException(400, "There are no messages to summarize.")
            if any(contains_secret(message["content"]) for message in messages):
                raise HTTPException(400, "Remove credentials from the conversation before summarizing it.")
            summary = extractive_summary(messages)
            stamp = timestamp()
            connection.execute(
                "INSERT INTO conversation_summaries(conversation_id,summary,message_count,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET "
                "summary=excluded.summary,message_count=excluded.message_count,updated_at=excluded.updated_at",
                (conversation_id, summary, len(messages), stamp),
            )
            audit(connection, "conversation.summarized", "conversation", conversation_id, {"messages": len(messages)})
        return {"summary": summary, "message_count": len(messages), "updated_at": stamp}

    @app.get("/api/v1/audit")
    def list_audit(
        limit: int = Query(default=100, ge=1, le=500),
        _: None = Depends(require_owner),
    ) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            events = db.rows(connection, "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,))
        for event in events:
            event["detail"] = json.loads(event.pop("detail_json"))
        return events
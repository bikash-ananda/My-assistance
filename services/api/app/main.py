from __future__ import annotations

import logging
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .agents import BY_ID
from .config import Settings
from .knowledge import contains_secret, make_context, search_memories
from .routes_phase2 import register_phase2_routes
from .routes_phase3 import register_phase3_routes
from .routes_phase4 import register_phase4_routes
from .routes_phase9 import register_phase9_routes
from .routes_phase10 import register_phase10_routes
from .providers import Completion, Provider, configured_provider
from .security import make_session, valid_session, verify_password


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("bikash.api")
MAX_CONTEXT_CHARS = 12_000


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=2000)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    root_path: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class ConversationBody(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)
    project_id: str | None = None
    agent_id: str = "orchestrator"


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


def create_app(settings: Settings | None = None, provider: Provider | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db.initialize(settings.database_path)
    selected_provider = provider if provider is not None else configured_provider(settings)
    app = FastAPI(title="Bikash AI API", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.provider = selected_provider
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def require_owner(request: Request) -> None:
        if not settings.auth_configured:
            raise HTTPException(503, "Owner setup is required. Run scripts/setup.ps1.")
        if not valid_session(request.cookies.get("bikash_session"), settings.session_secret):
            raise HTTPException(401, "Sign in to continue.")

    @app.get("/health/live")
    def live() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict:
        try:
            with db.connect(settings.database_path) as connection:
                connection.execute("SELECT 1")
            return {"status": "ready", "database": "ok"}
        except Exception:
            logger.exception("Readiness check failed")
            raise HTTPException(503, "Service is not ready.")

    @app.get("/api/v1/setup/status")
    def setup_status() -> dict:
        return {
            "configured": settings.auth_configured,
            "provider": selected_provider.name if selected_provider else "disabled",
            "chat_ready": selected_provider is not None,
        }

    @app.post("/api/v1/auth/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict:
        if not settings.auth_configured:
            raise HTTPException(503, "Owner setup is required. Run scripts/setup.ps1.")
        remote = request.client.host if request.client else "unknown"
        remote_key = hmac.new(settings.session_secret.encode("utf-8"), remote.encode("utf-8"), hashlib.sha256).hexdigest()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        with db.connect(settings.database_path) as connection:
            connection.execute("DELETE FROM login_attempts WHERE attempted_at<?", (cutoff,))
            failures = db.row(connection, "SELECT COUNT(*) AS count FROM login_attempts WHERE remote_key=? AND attempted_at>=?", (remote_key, cutoff))
        if failures and failures["count"] >= 8:
            raise HTTPException(429, "Too many failed sign-in attempts. Wait 15 minutes and try again.")
        if not verify_password(body.password, settings.owner_salt, settings.owner_hash):
            with db.connect(settings.database_path) as connection:
                connection.execute("INSERT INTO login_attempts(id,remote_key,attempted_at) VALUES(?,?,?)", (str(uuid4()), remote_key, now()))
            raise HTTPException(401, "Password was not accepted.")
        with db.connect(settings.database_path) as connection:
            connection.execute("DELETE FROM login_attempts WHERE remote_key=?", (remote_key,))
        response.set_cookie(
            "bikash_session",
            make_session(settings.session_secret, settings.session_minutes),
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_minutes * 60,
            path="/",
        )
        return {"authenticated": True}

    @app.post("/api/v1/auth/logout")
    def logout(response: Response) -> dict:
        response.delete_cookie("bikash_session", path="/", httponly=True, samesite="lax")
        return {"authenticated": False}

    @app.get("/api/v1/auth/me")
    def me(_: None = Depends(require_owner)) -> dict:
        return {"authenticated": True}

    @app.get("/api/v1/projects")
    def list_projects(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            return db.rows(
                connection,
                "SELECT * FROM projects WHERE status='active' ORDER BY name COLLATE NOCASE",
            )

    @app.post("/api/v1/projects", status_code=201)
    def create_project(body: ProjectBody, _: None = Depends(require_owner)) -> dict:
        if contains_secret(body.name + "\n" + body.notes):
            raise HTTPException(400, "Remove credentials from project notes.")
        project_id, created = str(uuid4()), now()
        with db.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO projects(id,name,root_path,notes,created_at) VALUES(?,?,?,?,?)",
                (project_id, body.name.strip(), body.root_path, body.notes, created),
            )
            return db.row(connection, "SELECT * FROM projects WHERE id=?", (project_id,)) or {}

    @app.patch("/api/v1/projects/{project_id}")
    def update_project(
        project_id: str, body: ProjectPatch, _: None = Depends(require_owner)
    ) -> dict:
        fields = body.model_dump(exclude_unset=True)
        if contains_secret(str(fields.get("name", "")) + "\n" + str(fields.get("notes", ""))):
            raise HTTPException(400, "Remove credentials from project notes.")
        if not fields:
            raise HTTPException(400, "No changes supplied.")
        with db.connect(settings.database_path) as connection:
            if not db.row(connection, "SELECT id FROM projects WHERE id=?", (project_id,)):
                raise HTTPException(404, "Project not found.")
            assignments = ", ".join(key + "=?" for key in fields)
            connection.execute(
                "UPDATE projects SET " + assignments + " WHERE id=?",
                (*[value.strip() if key == "name" and value else value for key, value in fields.items()], project_id),
            )
            return db.row(connection, "SELECT * FROM projects WHERE id=?", (project_id,)) or {}

    @app.post("/api/v1/projects/{project_id}/archive")
    def archive_project(project_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute(
                "UPDATE projects SET status='archived' WHERE id=?", (project_id,)
            ).rowcount
            if not changed:
                raise HTTPException(404, "Project not found.")
        return {"archived": True}

    @app.get("/api/v1/conversations")
    def list_conversations(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            return db.rows(connection, "SELECT * FROM conversations ORDER BY updated_at DESC")

    @app.post("/api/v1/conversations", status_code=201)
    def create_conversation(
        body: ConversationBody, _: None = Depends(require_owner)
    ) -> dict:
        if contains_secret(body.title):
            raise HTTPException(400, "Remove credentials from the conversation title.")
        if body.agent_id not in BY_ID:
            raise HTTPException(400, "Unknown agent.")
        conversation_id, created = str(uuid4()), now()
        with db.connect(settings.database_path) as connection:
            if body.project_id and not db.row(
                connection,
                "SELECT id FROM projects WHERE id=? AND status='active'",
                (body.project_id,),
            ):
                raise HTTPException(404, "Active project not found.")
            connection.execute(
                "INSERT INTO conversations(id,title,project_id,agent_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (conversation_id, body.title.strip(), body.project_id, body.agent_id, created, created),
            )
            return db.row(
                connection, "SELECT * FROM conversations WHERE id=?", (conversation_id,)
            ) or {}

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    def list_messages(
        conversation_id: str, _: None = Depends(require_owner)
    ) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            if not db.row(connection, "SELECT id FROM conversations WHERE id=?", (conversation_id,)):
                raise HTTPException(404, "Conversation not found.")
            return db.rows(
                connection,
                "SELECT id,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY created_at,rowid",
                (conversation_id,),
            )

    @app.post("/api/v1/conversations/{conversation_id}/chat")
    async def chat(
        conversation_id: str, body: ChatBody, _: None = Depends(require_owner)
    ) -> dict:
        if contains_secret(body.message):
            raise HTTPException(400, "Remove credentials before sending this message.")
        current_provider = app.state.provider
        if current_provider is None:
            raise HTTPException(
                503,
                "Chat is paused until a model provider is explicitly configured. Local hardware has not been checked.",
            )
        with db.connect(settings.database_path) as connection:
            conversation = db.row(
                connection,
                "SELECT project_id,agent_id FROM conversations WHERE id=?",
                (conversation_id,),
            )
            if not conversation:
                raise HTTPException(404, "Conversation not found.")
            project = None
            if conversation["project_id"]:
                project = db.row(
                    connection,
                    "SELECT id,name,notes FROM projects WHERE id=? AND status='active'",
                    (conversation["project_id"],),
                )
            summary = db.row(
                connection,
                "SELECT summary FROM conversation_summaries WHERE conversation_id=?",
                (conversation_id,),
            )
            memories = search_memories(
                connection, body.message, conversation["project_id"], limit=3
            )
            if summary and contains_secret(summary["summary"]):
                summary = None
            retrieval = make_context(project, summary, memories)
            agent = BY_ID.get(conversation["agent_id"], BY_ID["orchestrator"])
            agent_context = ""
            if agent.id != "orchestrator":
                agent_context = (
                    "You are acting as " + agent.name + ". " + agent.purpose
                    + " Analyze and draft only. You have no tools and must not claim to perform actions."
                )
            context_text = "\n\n".join(part for part in (agent_context, retrieval) if part)
            history_limit = 6 if context_text else 7
            history = db.rows(
                connection,
                "SELECT role,content FROM messages WHERE conversation_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (conversation_id, history_limit),
            )
        context = []
        if context_text:
            context.append({"role": "system", "content": context_text})
        remaining = MAX_CONTEXT_CHARS - len(body.message) - len(context_text)
        for item in reversed(history):
            if remaining <= 0:
                break
            content = item["content"]
            if len(content) > remaining:
                content = content[-remaining:]
            context.append({"role": item["role"], "content": content})
            remaining -= len(content)

        context.append({"role": "user", "content": body.message})
        try:
            completion: Completion = await current_provider.complete(context)
        except Exception as exc:
            logger.warning("Provider request failed (%s)", type(exc).__name__)
            raise HTTPException(502, "The configured model did not respond. Try again later.")
        if not completion.text.strip():
            raise HTTPException(502, "The configured model returned an empty response.")
        stamp = now()
        with db.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (str(uuid4()), conversation_id, "user", body.message, stamp),
            )
            connection.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (str(uuid4()), conversation_id, "assistant", completion.text, stamp),
            )
            connection.execute(
                "INSERT INTO usage_events(id,conversation_id,provider,prompt_tokens,completion_tokens,created_at) VALUES(?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    conversation_id,
                    current_provider.name,
                    completion.prompt_tokens,
                    completion.completion_tokens,
                    stamp,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?", (stamp, conversation_id)
            )
        return {
            "role": "assistant",
            "content": completion.text,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
        }

    @app.get("/api/v1/usage")
    def usage(_: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            summary = db.row(
                connection,
                "SELECT COUNT(*) AS requests, SUM(prompt_tokens) AS prompt_tokens, "
                "SUM(completion_tokens) AS completion_tokens FROM usage_events",
            ) or {}
            providers = db.rows(
                connection,
                "SELECT provider, COUNT(*) AS requests FROM usage_events GROUP BY provider ORDER BY provider",
            )
        return {
            "requests": summary.get("requests", 0),
            "prompt_tokens": summary.get("prompt_tokens") or 0,
            "completion_tokens": summary.get("completion_tokens") or 0,
            "providers": providers,
        }

    register_phase2_routes(app, settings, require_owner)
    register_phase3_routes(app, settings, require_owner)
    register_phase4_routes(app, settings, require_owner)
    register_phase9_routes(app, settings, require_owner)
    register_phase10_routes(app, settings, require_owner)
    return app


app = create_app()

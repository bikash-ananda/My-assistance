from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers import Completion


class StubProvider:
    name = "test"

    async def complete(self, messages):
        assert len(messages) <= 8
        assert sum(len(message["content"]) for message in messages) <= 12_000
        return Completion("A short local test response.", 11, 7)


def make_client(tmp_path: Path, provider=None):
    settings = Settings(
        database_path=tmp_path / "test.sqlite3",
        owner_salt="00112233445566778899aabbccddeeff",
        owner_hash="bad",
        session_secret="test-secret-with-enough-entropy-for-tests",
        provider="none",
    )
    client = TestClient(create_app(settings, provider))
    return client, settings


def test_health_and_setup_status(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json()["database"] == "ok"
    assert client.get("/api/v1/setup/status").json()["configured"] is True


def test_login_rejects_bad_password_and_unauthenticated_data(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.get("/api/v1/projects").status_code == 401


def test_login_throttles_repeated_failures(tmp_path):
    client, _ = make_client(tmp_path)
    for _ in range(8):
        assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 429


def test_project_create_update_and_archive(tmp_path):
    client, settings = make_client(tmp_path)
    import hashlib

    settings = Settings(
        database_path=settings.database_path,
        owner_salt=settings.owner_salt,
        owner_hash=hashlib.pbkdf2_hmac(
            "sha256", b"owner-password", bytes.fromhex(settings.owner_salt), 600_000
        ).hex(),
        session_secret=settings.session_secret,
    )
    client = TestClient(create_app(settings))
    assert client.post("/api/v1/auth/login", json={"password": "owner-password"}).status_code == 200
    created = client.post("/api/v1/projects", json={"name": "Bikash AI", "notes": "private"}).json()
    assert created["status"] == "active"
    assert client.patch(
        "/api/v1/projects/" + created["id"], json={"notes": "updated"}
    ).json()["notes"] == "updated"
    assert client.post("/api/v1/projects/" + created["id"] + "/archive").status_code == 200
    assert client.get("/api/v1/projects").json() == []


def test_chat_persists_messages_and_usage(tmp_path):
    client, settings = make_client(tmp_path, StubProvider())
    settings = Settings(
        database_path=settings.database_path,
        owner_salt=settings.owner_salt,
        owner_hash=__import__("hashlib").pbkdf2_hmac(
            "sha256", b"owner-password", bytes.fromhex(settings.owner_salt), 600_000
        ).hex(),
        session_secret=settings.session_secret,
    )
    client = TestClient(create_app(settings, StubProvider()))
    client.post("/api/v1/auth/login", json={"password": "owner-password"})
    conversation = client.post("/api/v1/conversations", json={"title": "Test"}).json()
    import sqlite3

    with sqlite3.connect(settings.database_path) as raw:
        for index in range(7):
            raw.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (
                    str(index),
                    conversation["id"],
                    "user" if index % 2 == 0 else "assistant",
                    "p" * 3000,
                    "2026-01-01T00:00:" + str(index).zfill(2) + "+00:00",
                ),
            )
    result = client.post(
        "/api/v1/conversations/" + conversation["id"] + "/chat",
        json={"message": "x" * 8000},
    )
    assert result.status_code == 200
    assert len(client.get("/api/v1/conversations/" + conversation["id"] + "/messages").json()) == 9
    usage = client.get("/api/v1/usage").json()
    assert usage["prompt_tokens"] == 11
    assert usage["completion_tokens"] == 7


def test_chat_stays_disabled_without_explicit_provider(tmp_path):
    client, settings = make_client(tmp_path)
    import hashlib

    settings = Settings(
        database_path=settings.database_path,
        owner_salt=settings.owner_salt,
        owner_hash=hashlib.pbkdf2_hmac(
            "sha256", b"owner-password", bytes.fromhex(settings.owner_salt), 600_000
        ).hex(),
        session_secret=settings.session_secret,
    )
    client = TestClient(create_app(settings))
    client.post("/api/v1/auth/login", json={"password": "owner-password"})
    conversation = client.post("/api/v1/conversations", json={"title": "Test"}).json()
    import sqlite3

    with sqlite3.connect(settings.database_path) as raw:
        for index in range(7):
            raw.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (
                    str(index),
                    conversation["id"],
                    "user" if index % 2 == 0 else "assistant",
                    "p" * 3000,
                    "2026-01-01T00:00:" + str(index).zfill(2) + "+00:00",
                ),
            )
    response = client.post(
        "/api/v1/conversations/" + conversation["id"] + "/chat",
        json={"message": "Should remain local."},
    )
    assert response.status_code == 503
def test_ollama_provider_rejects_non_loopback_target(tmp_path):
    from app.providers import configured_provider

    settings = Settings(
        database_path=tmp_path / 'test.sqlite3',
        owner_salt='salt',
        owner_hash='hash',
        session_secret='secret',
        provider='ollama',
        ollama_url='https://example.com',
        ollama_model='model',
    )
    assert configured_provider(settings) is None

class ContextProvider:
    name = "context-test"

    def __init__(self):
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return Completion("Context verified.", 13, 5)


def signed_in_client(tmp_path, provider=None):
    import hashlib

    salt = "00112233445566778899aabbccddeeff"
    owner_passphrase = b"owner" + b"-password"
    settings = Settings(
        database_path=tmp_path / "phase2.sqlite3",
        owner_salt=salt,
        owner_hash=hashlib.pbkdf2_hmac(
            "sha256", owner_passphrase, bytes.fromhex(salt), 600_000
        ).hex(),
        session_secret="phase2-test-session-secret-with-enough-entropy",
    )
    client = TestClient(create_app(settings, provider))
    response = client.post("/api/v1/auth/login", json={"password": owner_passphrase.decode()})
    assert response.status_code == 200
    return client, settings


def test_memories_are_searchable_editable_deletable_and_secret_checked(tmp_path):
    from app import db
    from app.knowledge import search_memories

    client, settings = signed_in_client(tmp_path)
    saved = client.post(
        "/api/v1/memories",
        json={
            "category": "owner_preference",
            "kind": "preference",
            "title": "Reply style",
            "content": "Use concise answers for engineering reviews.",
            "source": "owner",
            "confidence": 0.95,
        },
    )
    assert saved.status_code == 201
    memory_id = saved.json()["id"]
    uncertain = client.post(
        "/api/v1/memories",
        json={
            "category": "research",
            "kind": "unverified",
            "title": "Unverified note",
            "content": "A distinctive unverified phrase.",
        },
    )
    assert uncertain.status_code == 201
    with db.connect(settings.database_path) as connection:
        assert len(search_memories(connection, "concise answers")) == 1
        assert search_memories(connection, "distinctive unverified phrase") == []
    assert client.post(
        "/api/v1/memories",
        json={
            "category": "operations",
            "title": "Credential",
            "content": "api" + "_key=secret_value_123456",
        },
    ).status_code == 400
    changed = client.patch(
        "/api/v1/memories/" + memory_id,
        json={"content": "Use concise actionable reviews."},
    )
    assert changed.status_code == 200
    with db.connect(settings.database_path) as connection:
        assert search_memories(connection, "engineering") == []
        assert len(search_memories(connection, "actionable reviews")) == 1
    assert client.delete("/api/v1/memories/" + memory_id).json() == {"deleted": True}
    assert client.get("/api/v1/memories/export").status_code == 200


def test_agents_route_and_persist_trackable_plans(tmp_path):
    client, _ = signed_in_client(tmp_path)
    agents = client.get("/api/v1/agents").json()
    assert len(agents) == 10
    route = client.post(
        "/api/v1/agents/route",
        json={"request": "Plan greenhouse irrigation monitoring"},
    ).json()
    assert route["agent"] == "agriculture"
    created = client.post(
        "/api/v1/agents/plan",
        json={"request": "Plan greenhouse irrigation monitoring"},
    )
    assert created.status_code == 201
    task_id = created.json()["task"]["id"]
    steps = created.json()["steps"]
    assert len(steps) >= 3
    assert client.post(
        "/api/v1/tasks/" + task_id + "/steps/" + steps[0]["id"] + "/complete"
    ).json()["status"] == "in_progress"
    assert client.patch(
        "/api/v1/tasks/" + task_id, json={"status": "blocked"}
    ).json()["status"] == "blocked"
    assert client.get("/api/v1/tasks").json()[0]["id"] == task_id
    assert client.get("/api/v1/audit").json()


class PlanProvider:
    name = "ollama"

    def __init__(self, text):
        self.text = text
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return Completion(self.text, 17, 9)


def test_agent_plan_uses_local_model_for_bounded_steps(tmp_path):
    provider = PlanProvider('{"steps":["Review the requirements", "Draft two implementation tasks", "Check the result"]}')
    client, _ = signed_in_client(tmp_path, provider)
    response = client.post("/api/v1/agents/plan", json={"agent_id": "software_development", "request": "Build a secure local feature."})
    assert response.status_code == 201
    assert response.json()["planner"] == "local_model"
    assert [step["title"] for step in response.json()["steps"]] == ["Review the requirements", "Draft two implementation tasks", "Check the result"]
    assert [message["role"] for message in provider.calls[0]] == ["system", "user"]
    assert "do not use tools" in provider.calls[0][0]["content"].lower()


def test_agent_plan_falls_back_when_local_model_returns_invalid_plan(tmp_path):
    provider = PlanProvider("not structured output")
    client, _ = signed_in_client(tmp_path, provider)
    response = client.post("/api/v1/agents/plan", json={"agent_id": "agriculture", "request": "Review greenhouse readings."})
    assert response.status_code == 201
    assert response.json()["planner"] == "deterministic"
    assert len(response.json()["steps"]) == 4


def test_project_agent_context_and_local_summary(tmp_path):
    provider = ContextProvider()
    client, _ = signed_in_client(tmp_path, provider)
    project = client.post(
        "/api/v1/projects",
        json={"name": "Greenhouse", "notes": "Monitor soil and irrigation."},
    ).json()
    memory = client.post(
        "/api/v1/memories",
        json={
            "category": "project",
            "kind": "confirmed",
            "title": "Greenhouse goal",
            "content": "Keep reports concise and include sensor units.",
            "project_id": project["id"],
        },
    )
    assert memory.status_code == 201
    conversation = client.post(
        "/api/v1/conversations",
        json={
            "title": "Greenhouse planning",
            "project_id": project["id"],
            "agent_id": "agriculture",
        },
    ).json()
    response = client.post(
        "/api/v1/conversations/" + conversation["id"] + "/chat",
        json={"message": "Include sensor units."},
    )
    assert response.status_code == 200
    system_context = provider.calls[0][0]["content"]
    assert "Agriculture" in system_context
    assert "Selected project: Greenhouse" in system_context
    assert "sensor units" in system_context
    summary = client.post(
        "/api/v1/conversations/" + conversation["id"] + "/summarize"
    )
    assert summary.status_code == 200
    assert summary.json()["message_count"] == 2
    assert client.get(
        "/api/v1/conversations/" + conversation["id"] + "/summary"
    ).json()["summary"]


def test_local_tools_are_contained_audited_and_approval_bound(tmp_path):
    client, _ = signed_in_client(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("Local safe notes.\n", encoding="utf-8")
    (root / ".env").write_text("TOKEN=never-read", encoding="utf-8")
    project = client.post(
        "/api/v1/projects",
        json={"name": "Tool test", "root_path": str(root)},
    ).json()
    listing = client.post(
        "/api/v1/tools/preview",
        json={"tool_id": "files.list", "project_id": project["id"], "args": {}},
    )
    assert listing.status_code == 201
    result = client.post("/api/v1/approvals/" + listing.json()["id"] + "/execute")
    assert result.status_code == 200
    assert result.json()["result"]["untrusted"] is True
    assert result.json()["result"]["files"] == ["README.md"]
    traversal = client.post(
        "/api/v1/tools/preview",
        json={"tool_id": "files.read", "project_id": project["id"], "args": {"path": "../outside.txt"}},
    )
    assert traversal.status_code == 400
    created = client.post(
        "/api/v1/tools/preview",
        json={
            "tool_id": "files.create",
            "project_id": project["id"],
            "args": {"path": "notes/new.md", "content": "Reviewed exact content."},
        },
    )
    assert created.status_code == 201 and created.json()["requires_approval"] is True
    action_id = created.json()["id"]
    assert client.post("/api/v1/approvals/" + action_id + "/execute").status_code == 409
    assert client.post("/api/v1/approvals/" + action_id + "/approve").json()["status"] == "approved"
    assert client.post("/api/v1/approvals/" + action_id + "/execute").json()["status"] == "executed"
    assert (root / "notes" / "new.md").read_text(encoding="utf-8") == "Reviewed exact content."


def test_emergency_stop_revokes_pending_tool_previews(tmp_path):
    client, _ = signed_in_client(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    project = client.post(
        "/api/v1/projects", json={"name": "Stop test", "root_path": str(root)}
    ).json()
    action = client.post(
        "/api/v1/tools/preview",
        json={
            "tool_id": "files.create", "project_id": project["id"],
            "args": {"path": "file.md", "content": "safe"},
        },
    ).json()
    assert client.put("/api/v1/system/emergency-stop", json={"enabled": True}).json()["enabled"]
    assert client.get("/api/v1/approvals").json()[0]["status"] == "revoked"
    assert client.post("/api/v1/approvals/" + action["id"] + "/execute").status_code == 423


def test_durable_reminder_worker_creates_local_notification(tmp_path):
    from datetime import datetime, timedelta, timezone
    from app.scheduler import run_once

    client, settings = signed_in_client(tmp_path)
    due = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    reminder = client.post(
        "/api/v1/jobs",
        json={"title": "Check irrigation", "body": "Review the sensor dashboard.", "due_at": due},
    )
    assert reminder.status_code == 201
    assert run_once(settings.database_path) == 1
    assert run_once(settings.database_path) == 0
    items = client.get("/api/v1/notifications?unread_only=true").json()
    assert items[0]["title"] == "Check irrigation"
    assert client.post("/api/v1/notifications/" + items[0]["id"] + "/read").json()["read"] is True
    assert client.get("/api/v1/jobs").json()[0]["status"] == "done"


def test_sensor_tokens_are_one_time_and_ingestion_is_read_only(tmp_path):
    client, _ = signed_in_client(tmp_path)
    created = client.post("/api/v1/devices", json={"name": "Bench sensor"})
    assert created.status_code == 201
    device = created.json()
    token = device.pop("token")
    assert device["token_displayed_once"] is True
    bad = client.post(
        "/api/v1/telemetry/" + device["id"],
        headers={"Authorization": "Bearer invalid"},
        json={"readings": [{"sensor": "temperature", "value": 20, "unit": "C"}]},
    )
    assert bad.status_code == 401
    accepted = client.post(
        "/api/v1/telemetry/" + device["id"],
        headers={"Authorization": "Bearer " + token},
        json={"readings": [{"sensor": "temperature", "value": 20.5, "unit": "C"}]},
    )
    assert accepted.status_code == 202
    assert client.get("/api/v1/devices").json()[0]["latest"][0]["value"] == 20.5
    assert client.post("/api/v1/devices/" + device["id"] + "/disable").status_code == 200
    assert client.post(
        "/api/v1/telemetry/" + device["id"],
        headers={"Authorization": "Bearer " + token},
        json={"readings": [{"sensor": "temperature", "value": 20, "unit": "C"}]},
    ).status_code == 401


def test_owner_can_check_health_and_download_consistent_database_backup(tmp_path):
    import sqlite3

    client, _ = signed_in_client(tmp_path)
    health = client.get("/api/v1/maintenance/status")
    assert health.status_code == 200
    assert health.json()["database"] == "ok"
    assert health.json()["schema_version"] == 8
    backup = client.get("/api/v1/maintenance/backup")
    assert backup.status_code == 200
    backup_path = tmp_path / "downloaded.sqlite3"
    backup_path.write_bytes(backup.content)
    with sqlite3.connect(backup_path) as snapshot:
        assert snapshot.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert snapshot.execute("PRAGMA user_version").fetchone()[0] == 8

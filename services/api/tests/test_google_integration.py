import hashlib
import json
import sqlite3
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings
from app import google_integration
from app.main import create_app
from app.security import make_session


def make_google_client(tmp_path, configured=False):
    salt = "11" * 32
    settings = Settings(
        database_path=tmp_path / "google.sqlite3",
        owner_salt=salt,
        owner_hash=hashlib.pbkdf2_hmac("sha256", b"owner-password", bytes.fromhex(salt), 600_000).hex(),
        session_secret="integration-tests-session-secret-with-entropy",
        google_oauth_client_id="client-id" if configured else "",
        google_oauth_client_secret="client-secret" if configured else "",
        google_oauth_redirect_uri="http://localhost:3000/api/v1/integrations/google/callback" if configured else "",
        google_token_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    client = TestClient(create_app(settings))
    client.cookies.set("bikash_session", make_session(settings.session_secret, settings.session_minutes))
    return client, settings


def test_google_status_is_authenticated_and_uses_read_only_scopes(tmp_path):
    client, _ = make_google_client(tmp_path)
    client.cookies.clear()
    assert client.get("/api/v1/integrations").status_code == 401

    client, _ = make_google_client(tmp_path)
    response = client.get("/api/v1/integrations")
    assert response.status_code == 200
    status = {item["service"]: item for item in response.json()}
    assert status["gmail"]["state"] == "needs_client_credentials"
    assert status["gmail"]["scopes"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert status["calendar"]["scopes"] == ["https://www.googleapis.com/auth/calendar.events.readonly"]
    assert "client-secret" not in response.text


def test_google_connect_uses_state_pkce_and_offline_read_only_scope(tmp_path):
    client, settings = make_google_client(tmp_path, configured=True)
    response = client.get("/api/v1/integrations/google/gmail/connect", follow_redirects=False)
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    params = parse_qs(location.query)
    assert location.netloc == "accounts.google.com"
    assert params["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert params["access_type"] == ["offline"]
    assert params["code_challenge_method"] == ["S256"]
    assert len(params["code_challenge"][0]) == 43
    assert len(params["state"][0]) >= 40
    assert "client-secret" not in response.headers["location"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "no-store" in response.headers["cache-control"]
    with sqlite3.connect(settings.database_path) as connection:
        row = connection.execute("SELECT service,expires_at FROM google_oauth_states").fetchone()
    assert row[0] == "gmail"


def test_google_callback_rejects_state_not_bound_to_browser_cookie(tmp_path):
    client, _ = make_google_client(tmp_path, configured=True)
    response = client.get("/api/v1/integrations/google/gmail/connect", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    session = client.cookies.get("bikash_session")
    client.cookies.clear()
    client.cookies.set("bikash_session", session)
    callback = client.get("/api/v1/integrations/google/callback", params={"state": state, "code": "one-time-code"})
    assert callback.status_code == 400


def test_google_callback_encrypts_refresh_token_without_external_network(tmp_path, monkeypatch):
    client, settings = make_google_client(tmp_path, configured=True)
    start = client.get("/api/v1/integrations/google/gmail/connect", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, data=None, **_kwargs):
            assert url == google_integration.TOKEN_URL
            assert data["code_verifier"]
            return httpx.Response(200, json={
                "access_token": "short-lived-access-token",
                "refresh_token": "long-lived-refresh-token",
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            })

    monkeypatch.setattr(google_integration.httpx, "AsyncClient", FakeAsyncClient)
    callback = client.get(
        "/api/v1/integrations/google/callback",
        params={"state": state, "code": "one-time-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/?integration=google_connected"
    with sqlite3.connect(settings.database_path) as connection:
        encrypted = connection.execute("SELECT refresh_token_encrypted FROM google_connections WHERE service='gmail'").fetchone()[0]
    assert "long-lived-refresh-token" not in encrypted
    assert Fernet(settings.google_token_encryption_key.encode("ascii")).decrypt(encrypted.encode("ascii")) == b"long-lived-refresh-token"


def test_google_read_endpoints_require_connection_and_owner(tmp_path):
    client, _ = make_google_client(tmp_path, configured=True)
    assert client.get("/api/v1/integrations/google/gmail/messages").status_code == 409
    assert client.get("/api/v1/integrations/google/calendar/events").status_code == 409
    client.cookies.clear()
    assert client.get("/api/v1/integrations/google/gmail/messages").status_code == 401
    assert client.get("/api/v1/integrations/google/calendar/events").status_code == 401


def test_google_previews_are_bounded_and_mark_external_content_untrusted(tmp_path, monkeypatch):
    client, settings = make_google_client(tmp_path, configured=True)
    cipher = Fernet(settings.google_token_encryption_key.encode("ascii"))
    with sqlite3.connect(settings.database_path) as connection:
        for service, scope in (
            ("gmail", "https://www.googleapis.com/auth/gmail.readonly"),
            ("calendar", "https://www.googleapis.com/auth/calendar.events.readonly"),
        ):
            connection.execute(
                "INSERT INTO google_connections(service,refresh_token_encrypted,scopes_json,connected_at) VALUES(?,?,?,?)",
                (service, cipher.encrypt((service + "-refresh-token").encode()).decode(), json.dumps([scope]), "2026-10-31T00:00:00+00:00"),
            )

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, data=None, **_kwargs):
            return httpx.Response(200, json={"access_token": "short-lived-access-token"})

        async def get(self, url, params=None, **_kwargs):
            if url.endswith("/messages"):
                return httpx.Response(200, json={"messages": [{"id": "message-1"}]})
            if "/messages/" in url:
                return httpx.Response(200, json={
                    "threadId": "thread-1", "snippet": "Short preview",
                    "payload": {"headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": "Question"},
                        {"name": "Date", "value": "Sat, 31 Oct 2026 00:00:00 +0000"},
                    ]},
                })
            return httpx.Response(200, json={"items": [{
                "id": "event-1", "summary": "Review", "start": {"dateTime": "2026-11-01T10:00:00Z"},
                "end": {"dateTime": "2026-11-01T10:30:00Z"}, "location": "Office",
            }]})

    monkeypatch.setattr(google_integration.httpx, "AsyncClient", FakeAsyncClient)
    mail = client.get("/api/v1/integrations/google/gmail/messages?limit=1")
    events = client.get("/api/v1/integrations/google/calendar/events")
    assert mail.status_code == events.status_code == 200
    assert mail.json()["messages"][0]["snippet"] == "Short preview"
    assert mail.json()["messages"][0]["untrusted"] is True
    assert events.json()["events"][0]["summary"] == "Review"
    assert events.json()["events"][0]["untrusted"] is True
    assert mail.headers["cache-control"] == events.headers["cache-control"] == "no-store"


def test_google_disconnect_deletes_encrypted_refresh_token(tmp_path):
    client, settings = make_google_client(tmp_path)
    encrypted = Fernet(settings.google_token_encryption_key.encode("ascii")).encrypt(b"refresh-token").decode("ascii")
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            "INSERT INTO google_connections(service,refresh_token_encrypted,scopes_json,connected_at) VALUES(?,?,?,?)",
            ("gmail", encrypted, json.dumps(["https://www.googleapis.com/auth/gmail.readonly"]), "2026-10-31T00:00:00+00:00"),
        )
    response = client.delete("/api/v1/integrations/google/gmail")
    assert response.status_code == 200
    assert response.json() == {"service": "gmail", "connected": False}
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM google_connections").fetchone()[0] == 0

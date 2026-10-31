from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from . import db
from .config import Settings


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SERVICE_SPECS = {
    "gmail": {
        "id": "google-gmail",
        "name": "Gmail",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
    },
    "calendar": {
        "id": "google-calendar",
        "name": "Google Calendar",
        "scope": "https://www.googleapis.com/auth/calendar.events.readonly",
    },
}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fernet(settings: Settings) -> Fernet | None:
    if not settings.google_token_encryption_key:
        return None
    try:
        return Fernet(settings.google_token_encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None


def _configured(settings: Settings) -> bool:
    if not all((settings.google_oauth_client_id, settings.google_oauth_client_secret, settings.google_oauth_redirect_uri)):
        return False
    target = urlparse(settings.google_oauth_redirect_uri)
    local_http = target.scheme == "http" and target.hostname in {"localhost", "127.0.0.1", "::1"}
    return bool((target.scheme == "https" or local_http) and target.hostname and not target.username and not target.password and not target.query and not target.fragment)


def _service(service: str) -> dict:
    spec = SERVICE_SPECS.get(service)
    if spec is None:
        raise HTTPException(404, "Google integration not found.")
    return spec


def _require_setup(settings: Settings) -> Fernet:
    if not _configured(settings):
        raise HTTPException(503, "Configure the Google OAuth client values in the private .env file first.")
    cipher = _fernet(settings)
    if cipher is None:
        raise HTTPException(503, "Run scripts/setup.ps1 or add a valid Google token encryption key to .env.")
    return cipher


def _encrypt(cipher: Fernet, value: str) -> str:
    return cipher.encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(cipher: Fernet, value: str) -> str:
    try:
        return cipher.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError):
        raise HTTPException(503, "Google credentials cannot be unlocked. Check the private encryption key and reconnect.")


def _audit(connection, action: str, service: str) -> None:
    connection.execute(
        "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid4()), action, "integration", service, json.dumps({"service": service}), _stamp()),
    )


def register_google_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    @app.get("/api/v1/integrations")
    def google_status(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            connected = {item["service"]: item for item in db.rows(connection, "SELECT service,scopes_json,connected_at FROM google_connections")}
        cipher_ready = _fernet(settings) is not None
        client_ready = _configured(settings)
        result = []
        for service, spec in SERVICE_SPECS.items():
            record = connected.get(service)
            if record:
                state = "connected" if client_ready and cipher_ready else ("needs_client_credentials" if not client_ready else "needs_encryption_key")
            else:
                state = "needs_client_credentials" if not client_ready else ("needs_encryption_key" if not cipher_ready else "ready_to_connect")
            scopes = json.loads(record["scopes_json"]) if record else [spec["scope"]]
            result.append({
                "id": spec["id"], "name": spec["name"], "service": service,
                "state": state, "scopes": scopes, "connected_at": record["connected_at"] if record else None,
                "can_connect": client_ready and cipher_ready, "connected": record is not None,
            })
        return result

    @app.get("/api/v1/integrations/google/{service}/connect")
    def connect_google(service: str, _: None = Depends(require_owner)) -> Response:
        spec = _service(service)
        cipher = _require_setup(settings)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        created = datetime.now(timezone.utc)
        expires = created + timedelta(minutes=10)
        state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()
        with db.connect(settings.database_path) as connection:
            connection.execute("DELETE FROM google_oauth_states WHERE expires_at<?", (created.isoformat(),))
            existing = db.row(connection, "SELECT service FROM google_connections WHERE service=?", (service,))
            connection.execute(
                "INSERT INTO google_oauth_states(state_hash,service,verifier_encrypted,created_at,expires_at) VALUES(?,?,?,?,?)",
                (state_hash, service, _encrypt(cipher, verifier), created.isoformat(), expires.isoformat()),
            )
            _audit(connection, "integration.google.connect_started", service)
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": spec["scope"],
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if existing is None:
            params["prompt"] = "consent"
        redirect = RedirectResponse(AUTHORIZATION_URL + "?" + urlencode(params), status_code=303)
        redirect.set_cookie(
            "bikash_google_state_" + service, state, max_age=600, httponly=True,
            secure=settings.cookie_secure, samesite="lax", path="/api/v1/integrations/google",
        )
        redirect.headers["Cache-Control"] = "no-store"
        return redirect

    @app.get("/api/v1/integrations/google/callback")
    async def google_callback(request: Request, _: None = Depends(require_owner)) -> Response:
        state = request.query_params.get("state", "")
        if not state or len(state) > 256:
            raise HTTPException(400, "Google authorization could not be verified.")
        state_hash = hashlib.sha256(state.encode("ascii", errors="ignore")).hexdigest()
        with db.connect(settings.database_path) as connection:
            record = db.row(connection, "SELECT * FROM google_oauth_states WHERE state_hash=?", (state_hash,))
            if not record:
                raise HTTPException(400, "Google authorization expired. Start the connection again.")
            cookie = request.cookies.get("bikash_google_state_" + record["service"], "")
            if not hmac.compare_digest(state, cookie):
                raise HTTPException(400, "Google authorization could not be verified.")
            connection.execute("DELETE FROM google_oauth_states WHERE state_hash=?", (state_hash,))
            _audit(connection, "integration.google.callback_received", record["service"])
        service = record["service"]
        cipher = _require_setup(settings)
        result = RedirectResponse("/?integration=google_denied", status_code=303)
        result.delete_cookie("bikash_google_state_" + service, path="/api/v1/integrations/google")
        result.headers["Cache-Control"] = "no-store"
        if request.query_params.get("error"):
            return result
        code = request.query_params.get("code", "")
        if not code or len(code) > 4096:
            raise HTTPException(400, "Google authorization did not return a valid code.")
        verifier = _decrypt(cipher, record["verifier_encrypted"])
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
                response = await client.post(TOKEN_URL, data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                })
        except httpx.RequestError:
            raise HTTPException(502, "Google could not be reached. Try the connection again.")
        if response.status_code != 200:
            raise HTTPException(502, "Google did not complete authorization. Check the client and redirect settings.")
        try:
            tokens = response.json()
            if not isinstance(tokens, dict):
                raise ValueError
            access_token = tokens["access_token"]
            if not isinstance(access_token, str) or not access_token:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise HTTPException(502, "Google returned an invalid authorization response.")
        scopes = sorted(set(tokens.get("scope", SERVICE_SPECS[service]["scope"]).split()))
        if SERVICE_SPECS[service]["scope"] not in scopes:
            raise HTTPException(403, "Google did not grant the required read-only permission.")
        refresh_token = tokens.get("refresh_token")
        connected_at = _stamp()
        with db.connect(settings.database_path) as connection:
            previous = db.row(connection, "SELECT refresh_token_encrypted FROM google_connections WHERE service=?", (service,))
            if not refresh_token and previous:
                encrypted_refresh = previous["refresh_token_encrypted"]
            elif isinstance(refresh_token, str) and refresh_token:
                encrypted_refresh = _encrypt(cipher, refresh_token)
            else:
                raise HTTPException(502, "Google did not provide offline access. Reconnect and approve access.")
            connection.execute(
                "INSERT INTO google_connections(service,refresh_token_encrypted,scopes_json,connected_at) VALUES(?,?,?,?) "
                "ON CONFLICT(service) DO UPDATE SET refresh_token_encrypted=excluded.refresh_token_encrypted,scopes_json=excluded.scopes_json,connected_at=excluded.connected_at",
                (service, encrypted_refresh, json.dumps(scopes), connected_at),
            )
            _audit(connection, "integration.google.connected", service)
        result = RedirectResponse("/?integration=google_connected", status_code=303)
        result.delete_cookie("bikash_google_state_" + service, path="/api/v1/integrations/google")
        result.headers["Cache-Control"] = "no-store"
        return result

    @app.delete("/api/v1/integrations/google/{service}")
    def disconnect_google(service: str, _: None = Depends(require_owner)) -> dict:
        _service(service)
        with db.connect(settings.database_path) as connection:
            connection.execute("DELETE FROM google_connections WHERE service=?", (service,))
            connection.execute("DELETE FROM google_oauth_states WHERE service=?", (service,))
            _audit(connection, "integration.google.disconnected", service)
        return {"service": service, "connected": False}

    async def access_token(service: str) -> str:
        spec = _service(service)
        with db.connect(settings.database_path) as connection:
            record = db.row(connection, "SELECT refresh_token_encrypted FROM google_connections WHERE service=?", (service,))
        if not record:
            raise HTTPException(409, "Connect this Google service first.")
        cipher = _require_setup(settings)
        refresh = _decrypt(cipher, record["refresh_token_encrypted"])
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
                response = await client.post(TOKEN_URL, data={
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                })
        except httpx.RequestError:
            raise HTTPException(502, "Google could not be reached. Try again later.")
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if response.status_code != 200:
            if payload.get("error") == "invalid_grant":
                with db.connect(settings.database_path) as connection:
                    connection.execute("DELETE FROM google_connections WHERE service=?", (service,))
                raise HTTPException(401, "Google authorization expired. Reconnect this integration.")
            raise HTTPException(502, "Google could not refresh access. Try again later.")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise HTTPException(502, "Google returned an invalid access token response.")
        return token

    async def google_get(client: httpx.AsyncClient, token: str, url: str, params: dict) -> dict:
        try:
            response = await client.get(url, params=params, headers={"Authorization": "Bearer " + token})
        except httpx.RequestError:
            raise HTTPException(502, "Google could not be reached. Try again later.")
        if response.status_code == 401:
            raise HTTPException(401, "Google authorization expired. Reconnect this integration.")
        if response.status_code == 403:
            raise HTTPException(403, "Google did not grant the requested read-only permission.")
        if response.status_code != 200:
            raise HTTPException(502, "Google returned an error while reading this data.")
        try:
            value = response.json()
        except ValueError:
            raise HTTPException(502, "Google returned an invalid response.")
        return value if isinstance(value, dict) else {}

    @app.get("/api/v1/integrations/google/gmail/messages")
    async def gmail_messages(
        response: Response,
        q: str = Query(default="newer_than:7d", max_length=200),
        limit: int = Query(default=10, ge=1, le=25),
        _: None = Depends(require_owner),
    ) -> dict:
        token = await access_token("gmail")
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            listing = await google_get(client, token, "https://gmail.googleapis.com/gmail/v1/users/me/messages", {"q": q, "maxResults": limit})
            items = []
            for item in (listing.get("messages") or [])[:limit]:
                message_id = item.get("id") if isinstance(item, dict) else None
                if not isinstance(message_id, str) or not message_id:
                    continue
                details = await google_get(
                    client, token,
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/" + quote(message_id, safe=""),
                    {"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                )
                payload = details.get("payload") if isinstance(details.get("payload"), dict) else {}
                headers = payload.get("headers") or []
                selected = {h.get("name", "").lower(): h.get("value", "") for h in headers if isinstance(h, dict)}
                items.append({
                    "id": message_id,
                    "thread_id": details.get("threadId", ""),
                    "from": str(selected.get("from", ""))[:300],
                    "subject": str(selected.get("subject", "(no subject)"))[:300],
                    "date": str(selected.get("date", ""))[:100],
                    "snippet": str(details.get("snippet", ""))[:500],
                    "untrusted": True,
                })
        response.headers["Cache-Control"] = "no-store"
        return {"messages": items, "count": len(items), "untrusted": True}

    @app.get("/api/v1/integrations/google/calendar/events")
    async def calendar_events(response: Response, _: None = Depends(require_owner)) -> dict:
        token = await access_token("calendar")
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=14)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            listing = await google_get(
                client, token,
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                {"timeMin": start.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": 50},
            )
        events = []
        for event in (listing.get("items") or [])[:50]:
            if not isinstance(event, dict):
                continue
            event_start = event.get("start") if isinstance(event.get("start"), dict) else {}
            event_end = event.get("end") if isinstance(event.get("end"), dict) else {}
            events.append({
                "id": str(event.get("id", ""))[:200],
                "summary": str(event.get("summary", "(no title)"))[:300],
                "start": event_start,
                "end": event_end,
                "location": str(event.get("location", ""))[:250],
                "untrusted": True,
            })
        response.headers["Cache-Control"] = "no-store"
        return {"events": events, "count": len(events), "untrusted": True}

import hashlib
import json
import sqlite3

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import make_session


def make_client(tmp_path):
    salt = "22" * 32
    settings = Settings(
        database_path=tmp_path / "business.sqlite3",
        owner_salt=salt,
        owner_hash=hashlib.pbkdf2_hmac("sha256", b"owner-password", bytes.fromhex(salt), 600_000).hex(),
        session_secret="business-tests-session-secret-with-entropy",
    )
    client = TestClient(create_app(settings))
    client.cookies.set("bikash_session", make_session(settings.session_secret, settings.session_minutes))
    return client, settings


def test_business_contacts_are_owner_only_local_and_secret_checked(tmp_path):
    client, settings = make_client(tmp_path)
    client.cookies.clear()
    assert client.get("/api/v1/business/contacts").status_code == 401
    client.cookies.set("bikash_session", make_session(settings.session_secret, settings.session_minutes))

    response = client.post("/api/v1/business/contacts", json={
        "name": "Bikash Contact", "email": "contact@example.com", "organization": "Example Works",
        "next_follow_up_at": "2026-11-02T09:00:00+05:45",
    })
    assert response.status_code == 201
    contact = response.json()
    assert contact["next_follow_up_at"] == "2026-11-02T03:15:00+00:00"
    assert client.get("/api/v1/business/contacts?search=Example").json()[0]["id"] == contact["id"]
    assert client.post("/api/v1/business/contacts", json={"name": "Bad", "email": "invalid"}).status_code == 400
    assert client.post("/api/v1/business/contacts", json={"name": "Bad", "notes": "api" + "_key=private-value"}).status_code == 400

    with sqlite3.connect(settings.database_path) as connection:
        details = connection.execute("SELECT detail_json FROM audit_events WHERE target_id=?", (contact["id"],)).fetchone()[0]
    assert "contact@example.com" not in details
    assert json.loads(details)["fields"]


def test_business_opportunity_partial_update_preserves_fields_and_can_archive(tmp_path):
    client, _ = make_client(tmp_path)
    contact = client.post("/api/v1/business/contacts", json={"name": "Pipeline contact"}).json()
    response = client.post("/api/v1/business/opportunities", json={
        "contact_id": contact["id"], "title": "Greenhouse installation", "amount": 25000,
        "currency": "npr", "expected_close_date": "2026-12-10",
    })
    assert response.status_code == 201
    opportunity = response.json()
    assert opportunity["currency"] == "NPR"

    updated = client.patch(f"/api/v1/business/opportunities/{opportunity['id']}", json={"stage": "proposal"})
    assert updated.status_code == 200
    assert updated.json()["stage"] == "proposal"
    assert updated.json()["title"] == "Greenhouse installation"
    assert updated.json()["amount"] == 25000
    assert client.post(f"/api/v1/business/opportunities/{opportunity['id']}/archive").status_code == 200
    assert client.get("/api/v1/business/opportunities").json() == []


def test_archiving_contact_keeps_linked_opportunity_and_audit(tmp_path):
    client, _ = make_client(tmp_path)
    contact = client.post("/api/v1/business/contacts", json={"name": "Keep relationship"}).json()
    opportunity = client.post("/api/v1/business/opportunities", json={"contact_id": contact["id"], "title": "Follow up"}).json()
    assert client.post(f"/api/v1/business/contacts/{contact['id']}/archive").json()["archived"] is True
    assert client.get("/api/v1/business/contacts").json() == []
    assert client.get("/api/v1/business/opportunities").json()[0]["contact_name"] == "Keep relationship"
    assert opportunity["contact_id"] == contact["id"]

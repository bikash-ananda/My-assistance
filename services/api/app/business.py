from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .config import Settings
from .knowledge import contains_secret

STAGES = ("lead", "qualified", "proposal", "negotiation", "won", "lost")
CONTACT_FIELDS = ("name", "email", "phone", "organization", "notes", "next_follow_up_at")
OPPORTUNITY_FIELDS = ("contact_id", "title", "amount", "currency", "stage", "expected_close_date", "notes")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def reject_secrets(values: dict) -> None:
    if contains_secret("\n".join(str(value or "") for value in values.values())):
        raise HTTPException(400, "Remove credentials from business records.")


def normalize_contact(values: dict, current: dict | None = None) -> dict:
    result = {key: (current or {}).get(key, "") for key in CONTACT_FIELDS}
    result["next_follow_up_at"] = (current or {}).get("next_follow_up_at")
    for key, value in values.items():
        if key == "next_follow_up_at":
            if value in (None, ""):
                result[key] = None
                continue
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    raise ValueError
                result[key] = parsed.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                raise HTTPException(400, "Follow-up time must include a timezone.")
        else:
            result[key] = (value or "").strip()
    if not result["name"]:
        raise HTTPException(400, "Contact name is required.")
    if result["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", result["email"]):
        raise HTTPException(400, "Enter a valid email address.")
    reject_secrets(result)
    return result


def normalize_opportunity(values: dict, current: dict | None = None) -> dict:
    result = {"contact_id": None, "title": "", "amount": 0, "currency": "USD", "stage": "lead", "expected_close_date": None, "notes": ""}
    if current:
        result.update({key: current.get(key) for key in OPPORTUNITY_FIELDS})
    for key, value in values.items():
        if key in ("contact_id", "expected_close_date") and value in (None, ""):
            result[key] = None
        elif key == "currency":
            result[key] = (value or "").strip().upper()
        elif key in ("title", "notes"):
            result[key] = (value or "").strip()
        else:
            result[key] = value
    if not result["title"]:
        raise HTTPException(400, "Opportunity title is required.")
    if not re.fullmatch(r"[A-Z]{3}", result["currency"] or ""):
        raise HTTPException(400, "Currency must be a three-letter code.")
    if result["stage"] not in STAGES:
        raise HTTPException(400, "Choose a valid opportunity stage.")
    if result["expected_close_date"]:
        try:
            result["expected_close_date"] = date.fromisoformat(result["expected_close_date"]).isoformat()
        except (TypeError, ValueError):
            raise HTTPException(400, "Expected close date must use YYYY-MM-DD.")
    reject_secrets(result)
    return result


def audit(connection, action: str, kind: str, item_id: str, fields: list[str], at: str) -> None:
    connection.execute(
        "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid4()), action, kind, item_id, json.dumps({"fields": fields}), at),
    )


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    organization: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1200)
    next_follow_up_at: str | None = Field(default=None, max_length=40)


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    organization: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1200)
    next_follow_up_at: str | None = Field(default=None, max_length=40)


class OpportunityCreate(BaseModel):
    contact_id: str | None = Field(default=None, max_length=36)
    title: str = Field(min_length=1, max_length=140)
    amount: int = Field(default=0, ge=0, le=1_000_000_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stage: Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"] = "lead"
    expected_close_date: str | None = Field(default=None, max_length=10)
    notes: str = Field(default="", max_length=1200)


class OpportunityUpdate(BaseModel):
    contact_id: str | None = Field(default=None, max_length=36)
    title: str | None = Field(default=None, max_length=140)
    amount: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    stage: Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"] | None = None
    expected_close_date: str | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=1200)


def register_business_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    @app.get("/api/v1/business/contacts")
    def list_contacts(
        search: str = Query(default="", max_length=120),
        include_archived: bool = False,
        _: None = Depends(require_owner),
    ) -> list[dict]:
        clauses, params = [], []
        if not include_archived:
            clauses.append("archived_at IS NULL")
        if search.strip():
            clauses.append("(name LIKE ? OR email LIKE ? OR organization LIKE ?)")
            params.extend([f"%{search.strip()}%"] * 3)
        query = "SELECT * FROM business_contacts"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT 200"
        with db.connect(settings.database_path) as connection:
            return db.rows(connection, query, tuple(params))

    @app.post("/api/v1/business/contacts", status_code=201)
    def create_contact(body: ContactCreate, _: None = Depends(require_owner)) -> dict:
        values = normalize_contact(body.model_dump())
        item_id, at = str(uuid4()), stamp()
        with db.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO business_contacts(id,name,email,phone,organization,notes,next_follow_up_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (item_id, values["name"], values["email"], values["phone"], values["organization"], values["notes"], values["next_follow_up_at"], at, at),
            )
            audit(connection, "business.contact.created", "contact", item_id, sorted(values), at)
            return db.row(connection, "SELECT * FROM business_contacts WHERE id=?", (item_id,)) or {}

    @app.patch("/api/v1/business/contacts/{contact_id}")
    def update_contact(contact_id: str, body: ContactUpdate, _: None = Depends(require_owner)) -> dict:
        values = body.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(400, "Provide at least one contact field.")
        with db.connect(settings.database_path) as connection:
            current = db.row(connection, "SELECT * FROM business_contacts WHERE id=? AND archived_at IS NULL", (contact_id,))
            if not current:
                raise HTTPException(404, "Active contact not found.")
            normalized = normalize_contact(values, current)
            at = stamp()
            connection.execute(
                "UPDATE business_contacts SET name=?,email=?,phone=?,organization=?,notes=?,next_follow_up_at=?,updated_at=? WHERE id=?",
                tuple(normalized[key] for key in CONTACT_FIELDS) + (at, contact_id),
            )
            audit(connection, "business.contact.updated", "contact", contact_id, sorted(values), at)
            return db.row(connection, "SELECT * FROM business_contacts WHERE id=?", (contact_id,)) or {}

    @app.post("/api/v1/business/contacts/{contact_id}/archive")
    def archive_contact(contact_id: str, _: None = Depends(require_owner)) -> dict:
        at = stamp()
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE business_contacts SET archived_at=?,updated_at=? WHERE id=? AND archived_at IS NULL", (at, at, contact_id)).rowcount
            if not changed:
                raise HTTPException(404, "Active contact not found.")
            audit(connection, "business.contact.archived", "contact", contact_id, [], at)
        return {"id": contact_id, "archived": True}

    @app.get("/api/v1/business/opportunities")
    def list_opportunities(
        search: str = Query(default="", max_length=120),
        include_archived: bool = False,
        _: None = Depends(require_owner),
    ) -> list[dict]:
        clauses, params = [], []
        if not include_archived:
            clauses.append("o.archived_at IS NULL")
        if search.strip():
            clauses.append("(o.title LIKE ? OR c.name LIKE ? OR c.organization LIKE ?)")
            params.extend([f"%{search.strip()}%"] * 3)
        query = "SELECT o.*, c.name AS contact_name FROM sales_opportunities o LEFT JOIN business_contacts c ON c.id=o.contact_id"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY o.updated_at DESC LIMIT 200"
        with db.connect(settings.database_path) as connection:
            return db.rows(connection, query, tuple(params))

    @app.post("/api/v1/business/opportunities", status_code=201)
    def create_opportunity(body: OpportunityCreate, _: None = Depends(require_owner)) -> dict:
        values = normalize_opportunity(body.model_dump())
        item_id, at = str(uuid4()), stamp()
        with db.connect(settings.database_path) as connection:
            if values["contact_id"] and not db.row(connection, "SELECT id FROM business_contacts WHERE id=?", (values["contact_id"],)):
                raise HTTPException(404, "Contact not found.")
            connection.execute(
                "INSERT INTO sales_opportunities(id,contact_id,title,amount,currency,stage,expected_close_date,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (item_id, values["contact_id"], values["title"], values["amount"], values["currency"], values["stage"], values["expected_close_date"], values["notes"], at, at),
            )
            audit(connection, "business.opportunity.created", "opportunity", item_id, sorted(values), at)
            return db.row(connection, "SELECT * FROM sales_opportunities WHERE id=?", (item_id,)) or {}

    @app.patch("/api/v1/business/opportunities/{opportunity_id}")
    def update_opportunity(opportunity_id: str, body: OpportunityUpdate, _: None = Depends(require_owner)) -> dict:
        values = body.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(400, "Provide at least one opportunity field.")
        with db.connect(settings.database_path) as connection:
            current = db.row(connection, "SELECT * FROM sales_opportunities WHERE id=? AND archived_at IS NULL", (opportunity_id,))
            if not current:
                raise HTTPException(404, "Active opportunity not found.")
            normalized = normalize_opportunity(values, current)
            if normalized["contact_id"] and not db.row(connection, "SELECT id FROM business_contacts WHERE id=?", (normalized["contact_id"],)):
                raise HTTPException(404, "Contact not found.")
            at = stamp()
            connection.execute(
                "UPDATE sales_opportunities SET contact_id=?,title=?,amount=?,currency=?,stage=?,expected_close_date=?,notes=?,updated_at=? WHERE id=?",
                tuple(normalized[key] for key in OPPORTUNITY_FIELDS) + (at, opportunity_id),
            )
            audit(connection, "business.opportunity.updated", "opportunity", opportunity_id, sorted(values), at)
            return db.row(connection, "SELECT * FROM sales_opportunities WHERE id=?", (opportunity_id,)) or {}

    @app.post("/api/v1/business/opportunities/{opportunity_id}/archive")
    def archive_opportunity(opportunity_id: str, _: None = Depends(require_owner)) -> dict:
        at = stamp()
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE sales_opportunities SET archived_at=?,updated_at=? WHERE id=? AND archived_at IS NULL", (at, at, opportunity_id)).rowcount
            if not changed:
                raise HTTPException(404, "Active opportunity not found.")
            audit(connection, "business.opportunity.archived", "opportunity", opportunity_id, [], at)
        return {"id": opportunity_id, "archived": True}

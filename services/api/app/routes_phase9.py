from __future__ import annotations

import hashlib
import json
import math
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import db
from .config import Settings
from .knowledge import contains_secret


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeviceBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class Reading(BaseModel):
    sensor: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=20)
    recorded_at: str | None = Field(default=None, max_length=40)


class TelemetryBody(BaseModel):
    readings: list[Reading] = Field(min_length=1, max_length=20)


def register_phase9_routes(app: FastAPI, settings: Settings, require_owner) -> None:
    @app.get("/api/v1/devices")
    def list_devices(_: None = Depends(require_owner)) -> list[dict]:
        with db.connect(settings.database_path) as connection:
            devices = db.rows(connection, "SELECT id,name,active,created_at FROM telemetry_devices ORDER BY created_at DESC")
            for device in devices:
                device["latest"] = db.rows(
                    connection,
                    "SELECT sensor,value,unit,recorded_at FROM telemetry_samples WHERE device_id=? ORDER BY recorded_at DESC LIMIT 20",
                    (device["id"],),
                )
            return devices

    @app.post("/api/v1/devices", status_code=201)
    def create_device(body: DeviceBody, _: None = Depends(require_owner)) -> dict:
        if contains_secret(body.name):
            raise HTTPException(400, "Remove credentials from the device name.")
        device_id, token, now = str(uuid4()), secrets.token_urlsafe(32), stamp()
        with db.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO telemetry_devices(id,name,token_hash,active,created_at) VALUES(?,?,?,1,?)",
                (device_id, body.name.strip(), hashlib.sha256(token.encode("utf-8")).hexdigest(), now),
            )
            connection.execute(
                "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid4()), "telemetry.device.created", "device", device_id, json.dumps({"name": body.name.strip()}), now),
            )
        return {"id": device_id, "name": body.name.strip(), "token": token, "token_displayed_once": True}

    @app.post("/api/v1/devices/{device_id}/disable")
    def disable_device(device_id: str, _: None = Depends(require_owner)) -> dict:
        with db.connect(settings.database_path) as connection:
            changed = connection.execute("UPDATE telemetry_devices SET active=0 WHERE id=? AND active=1", (device_id,)).rowcount
            if not changed:
                raise HTTPException(404, "Active device not found.")
            connection.execute(
                "INSERT INTO audit_events(id,action,target_type,target_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid4()), "telemetry.device.disabled", "device", device_id, "{}", stamp()),
            )
        return {"id": device_id, "active": False}

    @app.post("/api/v1/telemetry/{device_id}", status_code=202)
    def ingest(
        device_id: str,
        body: TelemetryBody,
        authorization: str | None = Header(default=None),
    ) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Device token is required.")
        presented = authorization[7:].strip()
        digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
        now_dt = datetime.now(timezone.utc)
        prepared = []
        for sample in body.readings:
            if contains_secret(sample.sensor + " " + sample.unit):
                raise HTTPException(400, "Remove credentials from sensor labels.")
            if not math.isfinite(sample.value) or abs(sample.value) > 1_000_000_000:
                raise HTTPException(400, "Sensor value is outside the accepted range.")
            try:
                recorded = datetime.fromisoformat(sample.recorded_at) if sample.recorded_at else now_dt
                if recorded.tzinfo is None:
                    raise ValueError("timezone required")
                recorded = recorded.astimezone(timezone.utc)
            except ValueError:
                raise HTTPException(400, "Sensor timestamp must include a timezone.")
            if recorded > now_dt + timedelta(minutes=5) or recorded < now_dt - timedelta(days=30):
                raise HTTPException(400, "Sensor timestamp is outside the accepted window.")
            prepared.append((str(uuid4()), sample.sensor.strip(), sample.value, sample.unit.strip(), recorded.isoformat()))
        with db.connect(settings.database_path) as connection:
            device = db.row(connection, "SELECT id FROM telemetry_devices WHERE id=? AND token_hash=? AND active=1", (device_id, digest))
            if not device:
                raise HTTPException(401, "Device token is invalid or disabled.")
            recent = db.row(connection, "SELECT COUNT(*) AS count FROM telemetry_samples WHERE device_id=? AND received_at>=?", (device_id, (now_dt - timedelta(minutes=1)).isoformat()))
            if recent and recent["count"] >= 200:
                raise HTTPException(429, "Device telemetry limit reached; retry shortly.")
            connection.executemany(
                "INSERT INTO telemetry_samples(id,device_id,sensor,value,unit,recorded_at,received_at) VALUES(?,?,?,?,?,?,?)",
                [(sample_id, device_id, sensor, value, unit, recorded, now_dt.isoformat()) for sample_id, sensor, value, unit, recorded in prepared],
            )
        return {"accepted": len(prepared), "device_id": device_id}

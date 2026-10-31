# Read-only telemetry

Register a device from **Sensors & devices**. Its random bearer token is shown once; store it in the device's secret storage. Do not commit it, send it in a URL, or put it in project memory.

Send HTTPS `POST /api/v1/telemetry/{device_id}` with:

```http
Authorization: Bearer <one-time-device-token>
Content-Type: application/json
```

```json
{
  "readings": [
    {"sensor": "temperature", "value": 22.4, "unit": "C", "recorded_at": "2026-10-31T12:00:00+05:45"},
    {"sensor": "soil_moisture", "value": 38, "unit": "%"}
  ]
}
```

The API accepts up to 20 readings per request, values within ±1,000,000,000, timestamps from the last 30 days to five minutes ahead, and up to 200 readings per minute per device. Disable a device from the dashboard to revoke its token. The database stores only a token hash; the token cannot be recovered.

This endpoint accepts measurements only. It has no relay, motor, pump, robot, camera, or other actuation operation. Do not expose it to the public internet without a reviewed TLS route and device network policy.

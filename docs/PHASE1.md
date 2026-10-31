# Phase 1 — Local Foundation

## Local startup

1. Run `./scripts/install.ps1` once.
2. Run `./scripts/setup.ps1` once and set your owner password.
3. Start `./scripts/run-api.ps1`, `./scripts/run-web.ps1`, and, for reminders, `./scripts/run-worker.ps1` in separate terminals.
4. Open <http://127.0.0.1:3000>.

The API and development web server bind to loopback. The database is local SQLite and the `.env` file is excluded from Git. Keep the model disabled until hardware, quality, and privacy requirements are checked.

## Foundation features

Owner password hashing uses PBKDF2-HMAC-SHA256 with 600,000 rounds. Sessions are signed HttpOnly SameSite=Lax cookies, with an HTTPS Secure-cookie option. Projects, chats, usage, selective memory, task plans, tool approvals, reminders, telemetry, Google OAuth connections, and maintenance APIs were added in later phases. The current database schema version is 6.

## Current limits

Chat remains paused without an explicitly configured model. Ollama accepts loopback endpoints only. No cloud fallback, Gmail/Calendar access, external MCP connection, shell command execution, physical actuation, or public endpoint is enabled.

See [implementation status](IMPLEMENTATION_STATUS.md) for current verification and remaining dependencies.

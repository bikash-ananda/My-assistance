# Bikash AI

Bikash AI is a private, single-owner workspace with specialist agents, project memory, guarded local tools, reminders, and read-only sensor ingestion. The project defines **11 phases, numbered 0–10**. See [the implementation status](docs/IMPLEMENTATION_STATUS.md) for what is built and what still needs your accounts, hardware, or server.

## Run locally

1. In PowerShell at this folder, run `./scripts/install.ps1` once.
2. Run `./scripts/setup.ps1` and create your own 14+ character owner password. It saves a derived hash, not the password.
3. In one terminal run `./scripts/run-api.ps1`.
4. In a second terminal run `./scripts/run-web.ps1`.
5. For scheduled reminders, keep `./scripts/run-worker.ps1` running in a third terminal.
6. Open <http://127.0.0.1:3000> and sign in.

For a hidden production-mode local stack, run `./scripts/start-local.ps1`; stop it with `./scripts/stop-local.ps1`. `./scripts/install-startup.ps1` optionally registers it to start at your Windows sign-in, and `./scripts/uninstall-startup.ps1` removes that task. No startup task was registered during development. This only runs while the PC is on and the owner is signed in.

The first two services bind to loopback. The database and `.env` remain on this PC. The model stays paused until you deliberately configure a provider; Ollama must be on loopback. No cloud fallback is enabled.

## What works locally

- Owner login, project registry, persistent chats, measured provider usage, compact context, and private owner-edited memory.
- Ten specialist profiles, task routing, and plan tracking.
- A local tool registry for safe text files, Git status, and Python version. File creation needs approval bound to the exact preview. Emergency stop revokes queued tool actions.
- Durable reminders and in-app notifications. The reminder worker does not run shell commands or send external messages.
- Private local contact and sales-opportunity tracking with follow-up dates; records stay out of assistant prompts.
- Owner-initiated, read-only Gmail and Calendar OAuth with encrypted refresh-token storage; requires your own Google client and consent.
- Installable PWA shell, browser dictation/playback, and read-only device telemetry ingestion.
- Database health checks, downloadable snapshots, and offline backup/restore scripts.

Each chat request is limited to 8 messages and 12,000 characters. Memory is saved only when you add it. Tool output is marked as untrusted data.

## Verify

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest services\api\tests -q -p no:cacheprovider
```

From `apps/web`:

```powershell
npm run typecheck
npm run build
```

## Deployment artifacts

An isolated Docker Compose setup is in `docker-compose.yml`; it binds the web port to `127.0.0.1:3080`, keeps the API private, and persists data in its own named volume. Docker is not installed or verified on this PC, and the VPS has not been inspected. Do not attach it to an existing proxy or deploy until its ports, networks, resources, backups, and TLS route are reviewed.

GitHub/browser MCP connectors, native desktop speech, and physical device control are not connected. Gmail/Calendar remain disconnected until you add private Google OAuth client values and consent. See the phase status before enabling any external integration.

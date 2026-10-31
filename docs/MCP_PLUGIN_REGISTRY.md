# Bikash AI — Codex Plugin and MCP Registry

**Snapshot:** 2026-10-31

## Codex configuration inspected

Enabled entries included Codex app tools, Browser, Unified Computer Use, Visualize, Documents, PDF, Spreadsheets, Presentations, and Template Creator. Local Codex configuration exposed one MCP server name, node_repl. The resource-template inventory was empty. No Bikash AI server was configured or installed.

This session exposes Figma, GitHub, Plugin Management, and Pets integrations. They are Codex capabilities; Bikash AI cannot call them without separate runtime integration and credentials.

| Candidate | Phase | Initial scope | Decision |
| --- | --- | --- | --- |
| Workspace files | 3 | Scoped text list/read/search; new-file creation needs exact approval | Local adapter implemented; project root must be explicitly set. |
| Git/GitHub | 3 | Git status read only; pushes require approval | Git status implemented. GitHub runtime connector is separate and not configured. |
| Search/fetch | 0–1 | Read-only, preserve source URLs | No Bikash AI browser/fetch tool. Codex search is development-time only. |
| PostgreSQL | 1+ | Approved dev database | SQLite schema v5 is used. No PostgreSQL adapter or migration exists. |
| Browser automation | 3 | Isolated profile and explicit domains | Not implemented; pages remain untrusted input. |
| Ollama | 1 | Loopback only; no implicit cloud fallback | Adapter exists and is disabled until hardware/model verification. |
| Gmail/Calendar | 4 | Read-only OAuth scopes first | OAuth state/PKCE flow, encrypted refresh-token storage, revocation, and bounded read APIs are implemented. Client credentials and owner consent are still required to connect an account. |
| Notifications | 6 | Device-local first | Durable in-app reminders implemented; worker must be running. |
| IoT/physical tools | 9 | Read-only telemetry first | One-time-token sensor ingestion implemented. No actuation. |

## Installation policy

Discover and inspect each integration before installation. Prefer official/reputable maintained sources, pin versions, and record license, permissions, outbound traffic, and update process. Keep secrets out of prompts, logs, and memory. Test with mocks or sandbox accounts. Mark integrations installed only after verifying the running service and its permissions.

## Runtime boundary

No external MCP server is installed in Bikash AI. Use the app API for local data, permissions, and usage. Keep Codex integrations as development-time assistance. No Figma file or frame was supplied, so no Figma file was changed.

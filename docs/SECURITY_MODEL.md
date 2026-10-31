# Bikash AI — Security and Permission Model

## Core rules

Single owner initially. Deny tools by default. Keep secrets out of prompts, memory, source control, and logs. Isolate development and future deployment. Make actions reviewable, auditable, cancellable, and attributable.

## Operation levels

| Level | Examples | Control |
| --- | --- | --- |
| 0 — Read-only | Approved files, status, docs, logs, authorized email/calendar | Registered tool, scoped target, audit |
| 1 — Low risk | Drafts, notes, reports, suggested tasks | Registered tool and audit |
| 2 — Approval | Send email, publish, modify important project files, invitations, install software, push shared branch | Exact preview, owner approval, audit before/after |
| 3 — Strong confirmation | Production deploy/migration, deletion, credentials, firewall/DNS, service restart, financial or physical action | Action-time confirmation, exact target/action, strong safeguards, rollback/emergency stop |

The model may propose but cannot approve or raise its own permission.

## Permission engine

Each tool declares purpose, schema, allowed target, risk, approval policy, timeout/retry limit, output cap, secret handling, audit fields, cancellation, and failure behavior. Before execution, validate identity, operation, target, arguments, permission, and approval. Bind approval to a hash of the exact preview; material changes require new approval.

## Authentication and secrets

- No public registration; local development binds to loopback.
- Use mature password hashing and opaque server-side sessions.
- Cookies are HttpOnly and SameSite=Lax; set `BIKASH_COOKIE_SECURE=true` when the app is served over HTTPS. Local loopback development keeps it false.
- Login failures are rate-limited to 8 attempts per remote address over 15 minutes using a keyed address hash. External threat review remains production-hardening work. Tool previews expire, may be cancelled or revoked, and are blocked by emergency stop.
- Never expose admin/model endpoints unauthenticated to LAN or Internet.
- Ignore .env and key files; commit placeholders only.
- Prefer Windows Credential Manager locally or restrictive OS-backed secret storage on Linux.
- Redact tokens, authorization headers, private prompts, and secrets from logs.
- Encrypt Google refresh tokens with the private `.env` key; never send tokens to a model. Uvicorn access logging is disabled to keep OAuth callback codes out of API logs; reverse-proxy logs must redact callback query strings before internet deployment.
- Local CRM contacts and opportunity records remain in SQLite and are not included in assistant prompts or external requests.
- Database downloads and local backups are plain SQLite files. Store them privately; encrypted/off-site backup and retention policy remain production work.

## Untrusted content

Treat email, websites, repositories, documents, and MCP results as data, never policy instructions. Keep user content separate from tool policy. Validate arguments in code. Never pass model-generated strings directly to shell, SQL, URL fetch, or file paths. Restrict file roots and reject traversal/symlink escapes. Limit browser domains, redirects, request size, and output.

## Audit and recovery

Record action, target, approval hash, time, and error category while avoiding user content in the audit. Actor/session attribution and a full production audit trail remain to be added. Emergency stop blocks tool execution and revokes open previews. Restore scripts create a pre-restore copy; rehearse restoration before production.

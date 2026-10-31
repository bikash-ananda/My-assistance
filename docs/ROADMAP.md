# Bikash AI — Roadmap

**Status date:** 2026-10-31  
**Phase count:** 11 total, numbered 0 through 10.

| Phase | Status | Delivered / remaining |
| --- | --- | --- |
| 0 — Environment and feasibility | Audited; hardware details still unknown | Python 3.14.10 and Node are available; local model and hardware selection remain unverified. |
| 1 — Foundation | Implemented; owner setup pending | Owner-only web/API, SQLite, projects, conversations, provider boundary, usage view. Run `scripts/setup.ps1` yourself to set the owner password. |
| 2 — Intelligence and memory | Implemented and verified | Selective retrieval, owner-controlled memory, summaries, project context, 10 agent roles and bounded task plans. |
| 3 — Tools and permissions | Local core implemented and verified | Safe project text operations, Git status, exact-preview approvals, audit, revocation, emergency stop. External MCP, GitHub, and browser connectors remain unconfigured. |
| 4 — Business operations | Local CRM and read-only integration implemented | Contacts, queued follow-up reminders, and a staged sales pipeline stay local; Gmail/Calendar use PKCE, encrypted refresh tokens, bounded reads, and explicit disconnect. Google credentials and owner consent are still needed. |
| 5 — Specialist agents | Profiles and planner implemented | All 10 roles route and produce tracked plans; a configured loopback model can generate bounded plan steps with deterministic fallback. Tool execution remains separate and owner-gated. |
| 6 — Background automation | Local reminder queue and opt-in startup prepared | SQLite queue, recurring reminders and contact follow-ups, persistent notifications, restart recovery, hidden local launcher and optional logon-task scripts. Worker runs only after you start/register it; no task was installed. |
| 7 — Voice and mobile | Browser/PWA slice implemented | Installable web app, browser speech dictation and playback. Native desktop shell and local STT/TTS model are not installed. |
| 8 — VPS deployment | Isolated artifacts prepared; not deployed | API/web/worker Compose files use a dedicated volume/network and loopback web bind. Docker and VPS state are unverified; no server changes made. |
| 9 — Advanced capabilities | Read-only telemetry implemented | One-time device tokens, bounded sensor ingestion, latest readings, disable switch. No device hardware, computer vision, Nvidia inference, or actuation configured. |
| 10 — Production hardening | Local safeguards implemented; production review pending | Secure-cookie option, login throttling, audit, health/integrity, database snapshot, and a restore workflow that upgrades supported older schemas. Restore rehearsal, TLS/proxy review, external threat review, and production recovery remain pending. |

## Phase 0 findings

- Python 3.14.10 was installed for the current Windows user after explicit approval. See [PC hardware audit](PC_HARDWARE_AUDIT.md).
- Node.js and Git are available. A restricted local query reports 4 logical processors and about 8 GiB RAM; GPU/VRAM and total disk capacity remain unverified. Docker and Ollama are not on PATH.
- Codex-connected plugins are separate from the Bikash AI runtime. No Figma file was supplied or changed.

## Verification

- API: `& .\.venv\Scripts\python.exe -m pytest services\api\tests -q -p no:cacheprovider` in PowerShell.
- Web: `npm run typecheck` and `npm run build` from `apps/web`.

The current implementation is a local development workspace, not a deployed 24/7 service. See [implementation status](IMPLEMENTATION_STATUS.md) for external dependencies and startup steps.

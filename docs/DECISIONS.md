# Decisions

- 2026-10-31: Use a modular monolith for the first working slice. Keep provider and database boundaries simple.
- 2026-10-31: Use SQLite and local file storage first; keep prompts, projects, sessions, and model calls on the owner's machine.
- 2026-10-31: Require owner authentication. Store only a PBKDF2 password hash and a random session-signing secret in ignored .env.
- 2026-10-31: Bind the API and web dev server to loopback. Do not expose the first build to the LAN or internet.
- 2026-10-31: Default to no model provider. Ollama is opt-in after a hardware check; no cloud fallback or autonomous tools in Phase 1.
- 2026-10-31: Send at most the latest 8 messages per chat request. Record provider-reported token counts without estimating savings.
- 2026-10-31: Use the browser-to-API local Next.js rewrite, avoiding broad CORS access.
- 2026-10-31: Defer Docker, PostgreSQL, LangGraph, Letta, and LiteLLM until they solve a measured need.
- 2026-10-31: Keep 10 role profiles in the modular monolith; use deterministic routing/plans before any model delegation.
- 2026-10-31: Local tools are narrow and owner-triggered. The only write tool creates a new project text file after exact-preview approval; no arbitrary shell or physical action API.
- 2026-10-31: Add a durable local reminder queue; it creates in-app notifications only and does not send email.
- 2026-10-31: Accept telemetry with one-time device tokens but provide no actuator endpoint until hardware and safety policy are reviewed.
- 2026-10-31: Keep Compose isolated and loopback-bound; do not deploy or modify the shared VPS proxy without inspection.
- 2026-10-31: Implement Google OAuth as owner-initiated read-only Gmail and Calendar connections; keep each service disconnected until the owner supplies a client and grants consent.
- 2026-10-31: Encrypt Google refresh tokens with a setup-generated Fernet key kept only in the ignored `.env`; never send them to a model.

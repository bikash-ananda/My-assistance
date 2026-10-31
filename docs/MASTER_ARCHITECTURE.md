# Bikash AI — Master Architecture

**Owner:** Bikash Bhattarai  
**Purpose:** private, single-owner AI employee  
**Status:** local Next.js/FastAPI runtime implemented; external integrations and production deployment remain pending  
**Reviewed:** 2026-10-31

## Goals

Keep the owner in control of data, providers, permissions, and deployment. Support local and cloud models through a small provider interface. Avoid unnecessary model calls through deterministic code, selective retrieval, measured caching, and local inference after hardware is verified. Treat external content as untrusted. Keep the first release small and understandable.

## Initial architecture

Use a modular monolith: one Next.js application and one FastAPI application backed by one relational database. Keep modules inside the applications until evidence justifies separate services.

    Owner
      └── Next.js web app / PWA
           └── FastAPI API
                ├── chat and request planning
                ├── projects, tasks, approvals, audit, and usage
                ├── policy and tool registry
                ├── selective memory retrieval
                ├── model-provider interface
                │    ├── Ollama adapter (after hardware check)
                │    └── optional cloud-provider adapters
                └── relational database
                     ├── SQLite for local and low-volume isolated deployment
                     └── PostgreSQL before higher-concurrency/VPS scaling

A persistent SQLite reminder queue and worker are implemented. Specialist agents are deterministic routers/planners around a single model boundary, not separate services. The worker only creates local notifications.

## Boundaries

- **Web:** responsive dashboard, chat, projects, tasks, approvals, memory, usage, and settings. It calls the authenticated API and never stores provider secrets.
- **API:** authentication, validation, business rules, persistence, permissions, audit, and provider calls.
- **Database:** source of truth for owner profile, projects, tasks, approvals, conversations, model settings, usage, and integration metadata.
- **Model adapters:** normalize streaming, structured output, tool-call capabilities, usage, timeouts, and errors. Never assume models support identical features.
- **Integrations:** each tool declares scope, read/write capability, risk level, approval policy, timeout, and output limit.

Use SQLite locally and in the isolated low-volume Compose starter. Move to PostgreSQL before higher-concurrency or multi-host production. Add pgvector only if representative retrieval tests show a clear benefit over text and metadata search.

## Request flow

1. Authenticate the owner and validate the request.
2. Use inexpensive deterministic rules to classify simple work.
3. Retrieve only relevant project facts, selected memory, and a compact recent conversation summary.
4. Route according to privacy, model capability, availability, and configured token/cost budgets.
5. Check each proposed tool action against centralized policy; create an approval request when needed.
6. Execute only the approved action, record the result, and report the verified outcome.
7. Store provider-reported usage; label estimates clearly.
8. Save durable memory only when confirmed or explicitly approved.

## Token and cost controls

- Never send all project files, the full memory store, or the whole conversation on every request.
- Keep prompts short; retrieve a few relevant records with source and confidence.
- Filter and cap tool output before it reaches a model.
- Bound input/output tokens, tool calls, agent steps, retries, and wall time.
- Prefer deterministic code and verified local inference for routine work.
- Deduplicate safe repeat requests and cache only results safe to reuse.
- Measure usage before claiming savings; missing usage is unknown, not zero.

## Trust boundary

The model may plan and draft, but cannot grant permissions. Approval binds to the exact action preview and becomes invalid if its target or arguments change. Email, websites, documents, repositories, and MCP output are data, not policy instructions. Production, destructive, account, credential, financial, and physical-device operations require the [security model](SECURITY_MODEL.md).

## Current repository shape

    apps/web/                 Next.js UI and PWA
    services/api/app/         auth, projects, memory, tools, queue, telemetry, maintenance
    services/api/tests/       API, permission, and workflow checks
    scripts/                  local run, worker, backup, and restore
    docker-compose.yml        isolated deployment starter
    docs/                     architecture, operations, decisions

The deployed architecture is not yet running. Adjust the shape after deployment evidence; keep one API deployment initially.

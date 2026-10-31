# Bikash AI — Technology Selection

**Updated:** 2026-10-31

| Layer | Selection |
| --- | --- |
| Web | Next.js 16.4.3, React 19.1.10, TypeScript 5.9.3 |
| Runtime | Node.js 24.22.1; Python 3.14.10 per-user install |
| API | FastAPI 0.160.0, Uvicorn 0.40.0 |
| Database | SQLite standard library, schema version 8 |
| HTTP client | HTTPX 0.28.1, used only by the explicitly enabled Ollama adapter |
| Tests | Pytest 8.4.2 |
| Local inference | Ollama adapter, disabled by default; hardware audit required |
| Workflow/agents | 10 deterministic profiles, task planner, SQLite reminder queue |
| Hosting | Local development plus isolated Docker Compose artifacts; neither Docker nor VPS deployment verified |

Exact JavaScript versions are pinned in apps/web/package.json and package-lock.json. Python versions are pinned in services/api/requirements.txt and .venv. Recheck official release/security notes before upgrades.

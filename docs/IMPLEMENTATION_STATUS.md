# Implementation status

The master prompt contains **11 phases (0–10)**. This status reflects local code, not production deployment. The owner profile is still unconfigured in this checkout; run `scripts/setup.ps1` and choose your own password.

## Built and locally verifiable

- **Phase 0–1:** environment inventory, local owner authentication, project registry, conversations, bounded provider boundary and usage accounting.
- **Phase 2:** 10 agent profiles, deterministic routing/plans, tasks, selective confirmed/preference memory retrieval, local extractive summaries, project context. Automatic memory capture is intentionally off.
- **Phase 3:** local tool registry for safe text files, Git status and Python version; scoped paths and limits; exact action hashes; expiring approvals; audit; revocation; emergency stop. `files.create` is the only write tool and always needs owner approval. Arbitrary shell execution, MCP server launch, external browsing and GitHub calls are not enabled.
- **Phase 4:** local owner-only contacts, follow-up dates, opportunity stages, archive controls, audit entries, and read-only Gmail/Calendar OAuth with PKCE and encrypted refresh-token storage. Google client credentials and consent are still needed for live account access.
- **Phase 5:** all prompt-defined agent roles are present and track task plans. They do not run independently when the model is paused, and a role cannot approve its own tools.
- **Phase 6:** SQLite-backed reminders and notifications, recurring schedules and a separate worker. The queue survives restarts; the worker must be running for due notifications to appear.
- **Phase 7:** installable browser PWA shell, browser-provided speech dictation/playback. It uses the browser's speech capabilities; no local speech model or native desktop shell is included.
- **Phase 9:** one-time device token, bounded read-only telemetry ingestion and owner disable switch. No actuator API exists.
- **Phase 10:** configurable Secure cookie, 8-per-15-minute login throttling, authenticated database health/backup APIs, integrity check and offline restore script with a pre-restore backup.

## Waiting on external setup

- **Google business integrations:** Add a Google OAuth web client, exact redirect URL, and owner consent to connect. Email sending and calendar changes are not implemented. The isolated Compose network has no outbound Google access pending a separate egress security review.
- **Model runtime:** no provider/model was selected. Ollama and machine hardware were not verified. Without a provider, chat is paused while deterministic planners and data views still work.
- **MCP/other accounts:** Codex Figma/GitHub/browser tools do not automatically exist inside this product. No project-owned MCP server, Google account, GitHub token, or browser profile is configured.
- **VPS/24×7:** Compose files are prepared but Docker and server state are unverified. The reported Contabo VPS, current projects, proxy, ports, firewall, data and backups need a read-only inspection before an isolated `/opt/bikash-ai` deployment. No VPS was changed.
- **Hardware:** no ESP32/camera/robot/Nvidia device or protocol is configured. Telemetry accepts readings; physical actions remain absent.

## Local operation

Run the API and web scripts from separate terminals. For reminders, run `scripts/run-worker.ps1` in a third terminal. Alternatively, `scripts/start-local.ps1` launches a hidden production-mode local stack; the optional `scripts/install-startup.ps1` registers it at user sign-in. Neither script was executed, and no scheduled task was registered. The standalone Compose setup uses a new `bikash_private` network and named `bikash_data` volume, with the web port bound only to host loopback; it is not attached to the existing shared proxy.

Use `scripts/backup.ps1` for an offline local backup. Restore with `scripts/restore.ps1 -BackupPath <file>` only after stopping the API and worker; it asks you to type `RESTORE` and creates a pre-restore backup. The download/API backup is a plain SQLite file, so store it privately.

## Figma

The UI was implemented directly in Next.js because no Figma file/frame URL was supplied. No Figma design or file was modified.

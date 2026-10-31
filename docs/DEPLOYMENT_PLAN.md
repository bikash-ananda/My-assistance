# Deployment plan

## Local Windows

Run `scripts/install.ps1`, set your owner password with `scripts/setup.ps1`, then start API and web in separate terminals. Start `scripts/run-worker.ps1` for reminders. The local API and web development server bind to loopback. The model stays disabled until hardware and provider settings are checked.

## Isolated Compose starter

`docker-compose.yml` creates only the `api`, `web`, and reminder `worker` services, a dedicated `bikash_private` network, and `bikash_data` volume. The API is internal-only; the web port binds to `127.0.0.1:3080`. It does not reuse a proxy, volume, network, or container. The database is SQLite and intended for low-volume single-owner operation; migrate to PostgreSQL before higher-concurrency production.

Requirements and steps:

1. Install Docker Compose separately and confirm available memory/disk.
2. Run `scripts/setup.ps1` to create `.env`; set `BIKASH_COOKIE_SECURE=true` when HTTPS is configured.
3. Inspect the Compose file and run `docker compose config` locally.
4. Build and start only after review with `docker compose up --build -d`.
5. Configure the existing reverse proxy to route HTTPS to `127.0.0.1:3080` only after checking its current state and exact route.
6. Verify the health endpoint, browser login, reminders, backup, and restore using disposable data.

No Docker run or service install was made during development.

## Reported Contabo VPS

The owner previously reported an Ubuntu 24.04 VPS and existing projects under `/opt`. That state is user-supplied and was not independently inspected. Before a deployment, inspect resources, containers, networks, ports, firewall, reverse proxy, and backups read-only. Deploy only to `/opt/bikash-ai` after an explicit deployment review. Never modify existing projects, proxy rules, ports, volumes, or networks without a reviewed change plan.

The Compose network is internal and the browser service uses a loopback host port. It has no public TLS endpoint; the shared proxy must be inspected and configured separately. The API currently has no outbound network, so Google OAuth cannot run in Compose yet. Any egress path, public sensor endpoint, remote model access, and device action needs separate security and proxy review before internet exposure. For OAuth, redact query strings on the callback route in reverse-proxy logs.

24/7 uptime still requires a verified host, monitored storage/resources, TLS, encrypted off-site backups, restore rehearsal, alerting, and a rollback plan.

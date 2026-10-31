# Phase 10 — Local operations and recovery

## Health and snapshot

After signing in, open **Tools & safety** to see SQLite integrity, schema version, and pending reminder count. The database snapshot download and backup script produce a plain SQLite database containing private workspace records. Keep it private; it is not encrypted.

## Backup and restore

- Backup: `./scripts/backup.ps1`
- Restore: stop the API and reminder worker, then run `./scripts/restore.ps1 -BackupPath <path>` and type `RESTORE` at the prompt.
- Restore validates SQLite integrity, upgrades supported older backup schemas in a temporary copy, and saves the current database before replacement.

Run the restore rehearsal against a disposable copy before production. Backups newer than this application are rejected. Supported older backups are migrated to schema version 8 before restore; the selected backup file is left unchanged.

## Production work still required

Review HTTPS and Secure-cookie settings at the reverse proxy, rate limits, log retention, backup encryption/off-site storage, restore rehearsal, server resources, monitoring, and rollback before deploying. Docker and VPS access were not verified in this project session.

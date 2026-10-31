# Bikash AI — Model Routing and Token Budget

## Provider interface

The app defines a small completion interface and loopback-only Ollama adapter. Chat is disabled until a provider is explicitly configured; the current machine's hardware and model quality have not been checked. No cloud fallback exists.

## Routing

1. Use deterministic code for validation, classification, duplicate checks, calculations, and formatting.
2. Use local models for routine/private tasks only after hardware and quality are verified.
3. Use cloud models only when needed capabilities are unavailable locally and privacy/cost policy permits.
4. Fall back only to an owner-configured provider allowed for the data class.

Never silently send private content to cloud because local inference is unavailable.

## Context controls

Use short stable instructions, recent turns plus compact summary, a few relevant project/memory records with source IDs, filtered/capped tool output, and per-task input/output/step/tool/retry/time limits. Ask for clarification instead of repeating ambiguous calls. Never forward all project files or memory.

## Measurement and caching

Record provider/model, reported token counts or labeled estimates, latency/retries/status, dated price basis, local/cloud route, cache result, task class, and budget. Show estimates separately; missing usage is unknown, not zero. Measure a baseline before claiming savings.

Cache only deterministic/reference lookups with short TTL. Do not cache time-sensitive answers or tool actions. Scope keys by project/privacy. Deduplicate idempotent repeats by normalized hash and bounded TTL. Keep semantic caching disabled until false-hit testing. Use provider prompt caching only when supported and beneficial.

The implemented token guard is 8 messages and 12,000 total characters; the Ollama adapter caps generation at 512 tokens. Deterministic routing and task plans use no model calls. There is no recursive delegation or automatic model-selected tool execution.

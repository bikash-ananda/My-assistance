# Bikash AI — Memory Design

## Principle

The application database is the source of truth. Memory is selectively retrieved context, not an ever-growing prompt. User statements are not automatically permanent facts. Credentials and tokens are never memory items.

## Categories and record shape

Categories: owner preferences, professional profile, project facts/decisions, business knowledge, customer/contact records, conversation summaries, task history, research findings, operational knowledge, and temporary notes with expiry.

Current records store stable ID, category, kind/verification, project, title, concise content, source label, optional confidence, and timestamps. The owner can review, edit, export, or delete them. Expiry, source URLs, deduplication, and contradiction resolution remain future work.

## Retrieval by phase

- **Implemented:** compact extractive summaries, SQLite FTS5 search, selected project context, owner review/edit/export/delete. No embeddings or model calls for memory retrieval.
- **Remaining:** retention/expiry, source URLs, deduplication, contradiction resolution, and robust backup retention.

Retrieve a small top-k set filtered by project/privacy. Include source and confidence, cap tokens, and rebuild embeddings after edits. Keep assumptions unverified. Research findings include source and date. Preserve contradictions with provenance until the owner resolves them.

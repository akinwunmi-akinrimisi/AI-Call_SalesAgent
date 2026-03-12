# Phase 2: Data Layer - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy Supabase schema (isolated `sales_agent` schema) with leads, call_logs, and pipeline_logs tables, seed Firestore knowledge base from 5 PDFs, and create CSV import script. Every downstream component (voice agent, n8n workflows, OpenClaw) reads and writes data through these stores.

</domain>

<decisions>
## Implementation Decisions

### Lead Fields & Lifecycle
- Full 10-stage pipeline status tracking: new → outreach_sent → responded → booked → call_scheduled → call_in_progress → committed/follow_up/declined → payment_sent → paid
- Rich profile fields: name, phone, email, company, role, experience_level, cloud_background, motivation, preferred_programme — all populated by Sarah during the call (CSV only provides name/phone/email)
- Soft status enforcement: log warnings on skipped transitions, but allow them. Strict enforcement deferred to v2
- Key milestone timestamps on leads table: created_at, outreach_sent_at, booked_at, call_started_at, call_ended_at, payment_sent_at, paid_at (not every transition — pipeline_logs has full history)
- Priority field: integer 1-5, default 3. Enables smart call ordering by n8n
- Retry tracking on leads table: retry_count (int, max 2), next_retry_at (timestamp), last_call_attempt_at
- Soft delete: status='archived' with archived_at timestamp. Never hard delete leads

### Firestore Knowledge Structure
- One Firestore document per PDF in `knowledge_base` collection (5 documents total)
- Document IDs match PDF names: 'programmes', 'conversation-sequence', 'faqs', 'payment-details', 'objection-handling'
- Each document stores: content (full markdown text), source_file, page_count, extracted_at, version, keywords[]
- Firestore in vision-gridai project, Native mode, europe-west1 location
- Firestore database must be created first (no existing DB) — seed script creates DB if needed via gcloud
- Seed script runs on VPS #1 via SSH (where gcloud + Python 3.12 are available)
- Idempotent: overwrite existing documents on re-run (safe for PDF updates)

### Call Log Detail Level
- Rich call record: lead_id, call_sid, status, outcome (committed/follow_up/declined), duration_seconds, recording_url, started_at, ended_at, recommended_programme, objections_raised (JSON array), qualification_summary, gemini_model_used
- Full conversation transcript stored in a separate TEXT column
- One call_log row per call attempt (including retries). 3 attempts = 3 rows. Matches Twilio's unique call SID model
- Twilio-aligned statuses: initiated, ringing, in_progress, completed, no_answer, busy, failed, canceled

### CSV Import Rules
- CSV columns: name, phone, email only (Sarah discovers everything else)
- Phone normalization: auto-detect and normalize to E.164, but require explicit country code prefix (reject numbers without +)
- Duplicate handling: skip duplicates (matching on phone), log warning. Safe for re-runs
- Import sets status='new' and default priority=3

### Claude's Discretion
- Exact Supabase SQL migration syntax and RLS policies
- pipeline_logs table schema (must match existing logger.py payload structure)
- Index strategy for leads and call_logs tables
- Error handling in import and seed scripts
- Whether to use Supabase client library or raw REST API in scripts

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/logger.py`: Already implemented async pipeline_logs writer using httpx + Supabase REST API. Schema must match its payload: component, event_type, event_name, message, lead_id, metadata (JSON), created_at
- `scripts/import_leads.py`: Stub with docstring, needs full implementation
- `scripts/seed_firestore.py`: Stub with docstring, needs full implementation
- `backend/tools.py`: Stub for Firestore lookup tools (Phase 3 consumer of seeded data)
- `backend/config.py`: Config dataclass with GCP project, region, credentials, Supabase URL/keys

### Established Patterns
- httpx for async HTTP calls (used in logger.py)
- Supabase REST API with apikey + Bearer token auth (logger.py pattern)
- Service account JSON from secrets/ directory for GCP auth
- python-dotenv for env loading

### Integration Points
- logger.py writes to pipeline_logs — table schema must match its payload
- tools.py (Phase 3) will read from Firestore knowledge_base collection
- n8n workflows (Phase 8) will query leads table for pipeline orchestration
- Twilio handler (Phase 6) will write to call_logs table

</code_context>

<specifics>
## Specific Ideas

- Supabase uses isolated `sales_agent` schema (not public) per PROJECT.md constraint
- Existing Supabase has other tables — must not interfere
- Service account email: openclaw@vision-gridai.iam.gserviceaccount.com (used for Firestore access)
- VPS #1 has gcloud CLI for Firestore database creation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-layer*
*Context gathered: 2026-03-12*

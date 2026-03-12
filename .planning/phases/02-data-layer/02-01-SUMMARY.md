---
phase: 02-data-layer
plan: 01
subsystem: database
tags: [supabase, postgresql, schema, csv-import, phonenumbers, httpx, rest-api]

# Dependency graph
requires:
  - phase: 01-prerequisites
    provides: validated Supabase credentials and .env configuration
provides:
  - sales_agent schema with leads, call_logs, pipeline_logs tables on Supabase
  - logger.py writing to sales_agent.pipeline_logs via Content-Profile header
  - CSV lead import script with E.164 phone validation and duplicate detection
  - SQL migration files for reproducible schema deployment
affects: [voice-agent-backend, twilio-integration, n8n-orchestration, e2e-testing]

# Tech tracking
tech-stack:
  added: [phonenumbers]
  patterns: [Content-Profile/Accept-Profile headers for Supabase custom schema, E.164 phone validation, idempotent CSV import]

key-files:
  created:
    - sql/001_create_schema.sql
    - sql/002_create_tables.sql
    - sql/003_create_indexes.sql
    - scripts/import_leads.py
    - tests/test_leads.csv
  modified:
    - backend/logger.py
    - backend/requirements.txt

key-decisions:
  - "Content-Profile header pattern for all writes to sales_agent schema (POST/PUT/PATCH/DELETE)"
  - "Accept-Profile header pattern for all reads from sales_agent schema (GET/HEAD)"
  - "Phone validation rejects numbers without + prefix before parsing (prevents silent mis-parsing of local numbers)"
  - "Synchronous httpx client for CLI import script (async unnecessary for batch CLI tool)"
  - "metadata field passed as dict directly to Supabase JSONB column instead of json.dumps string"

patterns-established:
  - "Supabase schema isolation: all sales agent data in sales_agent schema, never public"
  - "Content-Profile/Accept-Profile header pair for custom schema REST API access"
  - "Phone validation gate: reject without +, parse with phonenumbers, format to E.164"
  - "Idempotent import: GET check before POST insert, skip duplicates"

requirements-completed: [DATA-01, DATA-02, DATA-04]

# Metrics
duration: 12min
completed: 2026-03-12
---

# Phase 2 Plan 01: Supabase Schema Summary

**Supabase sales_agent schema with leads/call_logs/pipeline_logs tables, Content-Profile REST API access, and idempotent CSV lead import with E.164 phone validation**

## Performance

- **Duration:** ~12 min (across two sessions: Task 1 + checkpoint, then Task 3 continuation)
- **Started:** 2026-03-12T19:55:00Z (estimated, Task 1 session)
- **Completed:** 2026-03-12T20:09:04Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Deployed sales_agent schema on self-hosted Supabase with 3 tables (leads, call_logs, pipeline_logs), 10 indexes, and proper role grants
- Updated logger.py to write to sales_agent.pipeline_logs using Content-Profile header -- verified with live test event
- Implemented CSV lead import with phonenumbers E.164 validation, duplicate detection, and per-row status output -- verified with 2 imports on first run, 0 on re-run

## Task Commits

Each task was committed atomically:

1. **Task 1: Write SQL migrations and update logger.py** - `fe5b36a` (feat)
2. **Task 2: Deploy schema to Supabase on VPS** - checkpoint:human-verify (approved by orchestrator, no code commit)
3. **Task 3: Implement CSV import script and verify data flow** - `ec42328` (feat)

## Files Created/Modified
- `sql/001_create_schema.sql` - Schema creation with GRANT statements for anon, authenticated, service_role
- `sql/002_create_tables.sql` - leads (12 statuses, 20+ columns), call_logs (outcome tracking, JSONB objections), pipeline_logs (flexible event logging)
- `sql/003_create_indexes.sql` - 10 performance indexes including partial index on next_retry_at
- `backend/logger.py` - Added Content-Profile: sales_agent header, fixed metadata to pass as dict (not stringified JSON)
- `backend/requirements.txt` - Added phonenumbers>=8.13.0
- `scripts/import_leads.py` - Full CSV import with phone validation, duplicate detection, summary output
- `tests/test_leads.csv` - 3 test records (2 valid E.164, 1 invalid without + prefix)

## Decisions Made
- **Content-Profile/Accept-Profile pattern**: All Supabase REST calls to sales_agent schema must use these headers. This is the foundational pattern for every downstream component.
- **Phone validation strictness**: Numbers without + prefix are rejected immediately (before phonenumbers parsing). This prevents silent mis-parsing where a local number could be interpreted as a different country's number.
- **Synchronous httpx for CLI**: import_leads.py uses synchronous httpx.Client (not AsyncClient) since it's a sequential CLI tool, not a server endpoint. Simpler code, same functionality.
- **metadata as dict**: Changed logger.py to pass metadata as a Python dict directly to Supabase POST body, since the JSONB column accepts JSON objects natively. Previously used json.dumps() which produced a quoted string in the database.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all three SQL migrations, schema deployment, PostgREST configuration, import script, and verification steps completed without issues.

## User Setup Required

**Schema deployment was handled via checkpoint (Task 2).**
The orchestrator SSH'd into VPS #1 and:
- Executed all 3 SQL migration files against supabase-db-1 container
- Updated PGRST_DB_SCHEMAS in docker-compose.yml to include sales_agent
- Added PG_META_DB_SCHEMAS for Studio visibility
- Recreated rest, meta, and studio containers
- Verified REST API returns [] for /rest/v1/leads with Accept-Profile: sales_agent

No further user setup required for this plan.

## Next Phase Readiness
- sales_agent schema is live and accepting reads/writes via REST API
- 2 test leads exist in the database for downstream testing
- logger.py is ready for use by voice agent backend (Phase 3)
- Plan 02-02 (Firestore knowledge base seed) is the remaining plan in Phase 2
- No blockers for continuing to Plan 02-02

## Self-Check: PASSED

All 7 claimed files verified present on disk. Both commit hashes (fe5b36a, ec42328) verified in git history.

---
*Phase: 02-data-layer*
*Completed: 2026-03-12*

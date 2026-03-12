---
phase: 01-prerequisites
plan: 01
subsystem: infra
tags: [env-config, secrets, pdf-validation, service-reachability, pymupdf, httpx, vertex-ai]

# Dependency graph
requires:
  - phase: none
    provides: first plan in project
provides:
  - Corrected env files with vision-gridai project ID and gemini-live-2.5-flash-native-audio model
  - Vertex AI service account auth pattern (GOOGLE_APPLICATION_CREDENTIALS) replacing API key auth
  - Secured secrets/ directory with service account JSON files
  - PDF validation script (scripts/validate_pdfs.py) using PyMuPDF + pymupdf4llm
  - Service reachability script (scripts/validate_services.py) using httpx + dotenv
  - Phase 1 Python dependencies installed (google-genai, google-auth, pymupdf, pymupdf4llm, resend, supabase, audioop-lts)
affects: [01-02, 02-data-layer, 03-voice-agent, 05-deployment]

# Tech tracking
tech-stack:
  added: [google-genai, google-auth, pymupdf, pymupdf4llm, resend, supabase, audioop-lts]
  patterns: [Vertex AI service account auth via GOOGLE_APPLICATION_CREDENTIALS, PyMuPDF extraction with keyword validation, httpx service reachability with CRITICAL/WARN classification]

key-files:
  created:
    - scripts/validate_pdfs.py
    - scripts/validate_services.py
    - secrets/ (directory)
  modified:
    - .env.example
    - backend/.env.example
    - backend/config.py
    - backend/requirements.txt
    - .gitignore
    - skills.sh
    - .env

key-decisions:
  - "europe-west1 as GCP region -- best latency for UK/Nigeria leads, Tier 1 pricing"
  - "Vertex AI service account auth replaces API key auth -- better access control for production Cloud Run"
  - "objection-handling.pdf replaces coming-soon.pdf as 5th PDF -- user decision from CONTEXT.md"
  - "CRITICAL vs WARN classification in service validation -- only Supabase, Twilio, GCP config are blocking"

patterns-established:
  - "Config via dataclass: backend/config.py with os.getenv() defaults"
  - "Secrets in secrets/ directory, never project root"
  - "Validation scripts in scripts/ with PASS/WARN/FAIL output and exit codes"

requirements-completed: []

# Metrics
duration: 9min
completed: 2026-03-12
---

# Phase 1 Plan 01: Prerequisites Foundation Summary

**Config files corrected to vision-gridai + Vertex AI auth, secrets secured, PDF and service validation scripts created with PyMuPDF and httpx**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-12T17:42:52Z
- **Completed:** 2026-03-12T17:52:15Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- All configuration files (env, config.py, skills.sh) updated from cloudboosta-agent to vision-gridai, from gemini-2.0-flash-live to gemini-live-2.5-flash-native-audio, and from API key auth to Vertex AI service account auth
- Service account JSON files moved from project root to secrets/ directory; secrets/ added to .gitignore
- PDF validation script created -- extracts text with PyMuPDF, checks keywords, reports PASS/WARN/FAIL per PDF
- Service reachability script created -- validates Supabase, n8n, OpenClaw, Resend, Twilio, GCP credentials; all 8 checks pass
- Phase 1 Python dependencies installed (google-genai, pymupdf, pymupdf4llm, resend, supabase, audioop-lts)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix configuration files, secure secrets, and install dependencies** - `5255763` (chore)
2. **Task 2: Copy PDFs and create PDF validation script** - `71719d3` (feat)
3. **Task 3: Create service reachability validation script** - `010b5b1` (feat)

## Files Created/Modified
- `.env.example` - Updated GCP project, model, auth method, added Resend section
- `backend/.env.example` - Aligned with root env template
- `backend/config.py` - Updated defaults, replaced API key field with credentials path, added gcp_region
- `backend/requirements.txt` - Added 7 new Phase 1 dependencies
- `.gitignore` - Added secrets/ entry, removed standalone openclaw-key-google.json
- `skills.sh` - Fixed project ID in error message, changed coming-soon.pdf to objection-handling.pdf
- `scripts/validate_pdfs.py` - PDF extraction and keyword validation for all 5 knowledge base documents
- `scripts/validate_services.py` - Reachability check for Supabase, n8n, OpenClaw, Resend, Twilio, GCP
- `knowledge-base/conversation-sequence.pdf` - Copied from Downloads (4 pages, 10k chars)

## Decisions Made
- europe-west1 selected as GCP region (best latency for UK/Nigeria, Tier 1 pricing, Gemini Live API available)
- Vertex AI service account auth replaces API key auth (production-grade, better access control)
- objection-handling.pdf replaces coming-soon.pdf as 5th PDF (user decision from CONTEXT.md)
- Service validation uses CRITICAL vs WARN classification -- OpenClaw and n8n are WARN-only (not blocking for Phase 1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Unicode encoding error in validate_services.py**
- **Found during:** Task 3 (service validation script)
- **Issue:** Reading .env file with default cp1252 encoding failed on JWT token bytes
- **Fix:** Added `encoding="utf-8", errors="replace"` to file open calls in check_env_completeness()
- **Files modified:** scripts/validate_services.py
- **Verification:** Script runs cleanly, all 8 checks pass
- **Committed in:** 010b5b1 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minimal -- encoding fix necessary for correctness on Windows. No scope creep.

## Issues Encountered

### 4 of 5 PDFs Not Found on Machine
- Only `conversation-sequence.pdf` was found in `C:/Users/DELL/Downloads/`
- The other 4 PDFs (programmes.pdf, faqs.pdf, payment-details.pdf, objection-handling.pdf) were not found anywhere on the machine
- CONTEXT.md stated "All 5 PDFs already exist as .pdf files on this machine, ready to copy into knowledge-base/" but this was not the case during execution
- The validate_pdfs.py script correctly reports FAIL for the 4 missing PDFs
- Documented in `.planning/phases/01-prerequisites/deferred-items.md`
- **User action required:** Create or locate the 4 missing PDFs and place them in `knowledge-base/`

## User Setup Required

User needs to place 4 missing PDFs in `knowledge-base/`:
1. `programmes.pdf` -- Programme details, pricing, duration
2. `faqs.pdf` -- Common questions and answers
3. `payment-details.pdf` -- Bank transfer instructions
4. `objection-handling.pdf` -- Objection response scripts

Then re-run: `python scripts/validate_pdfs.py`

## Next Phase Readiness
- Config foundation is solid: correct project ID, model, auth method, region
- Service reachability validated: Supabase, n8n, OpenClaw, Twilio creds, GCP credentials all pass
- PDF validation script ready to re-run once user places missing PDFs
- Plan 01-02 (Gemini Live API audio validation + Twilio phone verification) is unblocked
- **Partial blocker:** 4 missing PDFs need user action before Phase 2 Firestore seeding

## Self-Check: PASSED

All 11 created/modified files verified present on disk.
All 3 task commits (5255763, 71719d3, 010b5b1) verified in git log.

---
*Phase: 01-prerequisites*
*Completed: 2026-03-12*

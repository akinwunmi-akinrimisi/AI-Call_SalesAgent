---
phase: 03-voice-agent-backend
plan: 01
subsystem: voice-agent
tags: [firestore, adk, gemini, supabase, pytest, system-instruction, tools]

# Dependency graph
requires:
  - phase: 02-data-layer
    provides: "Firestore knowledge_base collection with 5 seeded PDF documents, Supabase sales_agent schema with leads and call_logs tables"
provides:
  - "knowledge_loader.py: load_knowledge_base() and build_system_instruction() for Sarah's persona"
  - "tools.py: update_lead_profile and determine_call_outcome ADK function tools"
  - "tools.py: write_lead_profile_to_supabase and write_call_log_to_supabase async helpers"
  - "conftest.py: shared test fixtures (mock Firestore, Supabase, KB content)"
  - "Full pytest suite: 23 tests covering CALL-02 through CALL-06, CALL-08, CALL-10"
affects: [03-02-PLAN, 03-03-PLAN, 06-twilio-integration]

# Tech tracking
tech-stack:
  added: [pytest, pytest-asyncio, pytest-mock, soxr]
  patterns: [tdd-red-green, mock-firestore-asyncclient, toolcontext-state-management, content-profile-supabase]

key-files:
  created:
    - backend/knowledge_loader.py
    - tests/conftest.py
    - tests/test_knowledge_loader.py
    - tests/test_system_instruction.py
    - tests/test_tools.py
    - pyproject.toml
  modified:
    - backend/tools.py
    - backend/requirements.txt

key-decisions:
  - "AsyncMock with return_value for Firestore doc.get() mock chain -- side_effect with async lambda created double-coroutine issue"
  - "SUPABASE_URL and SUPABASE_SERVICE_KEY read from env at module level in tools.py -- matches logger.py pattern"
  - "Tools store data in ToolContext.state dict, not Supabase directly -- Supabase writes deferred to call cleanup for non-blocking"

patterns-established:
  - "TDD red-green for all backend modules: write failing tests first, then implement"
  - "Mock Firestore chain: MagicMock db -> collection_ref.document -> doc_ref.get = AsyncMock(return_value=mock_doc)"
  - "ADK tool functions return {status, message} dicts and store state in tool_context.state"
  - "Supabase REST helpers use Content-Profile: sales_agent header on all requests"

requirements-completed: [CALL-02, CALL-03, CALL-04, CALL-05, CALL-06, CALL-10]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 3 Plan 01: Knowledge Loader & ADK Tools Summary

**Firestore KB pre-loader with Sarah's full system instruction (persona, AI disclosure, qualification flow, objection handling, commitment thresholds) plus ADK function tools for lead profile updates and outcome determination with Supabase async helpers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T21:21:02Z
- **Completed:** 2026-03-12T21:24:20Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- knowledge_loader.py builds Sarah's complete system instruction with all CONTEXT.md locked requirements: AI disclosure, qualification flow (4 must-have fields), programme recommendation (Cloud Security GBP 1,200 + SRE GBP 1,800), reactive objection handling (two attempts), commitment thresholds (COMMITTED/FOLLOW_UP/DECLINED), watchdog wrap-up behavior, follow-up timing, and full KB injection
- tools.py provides two ADK-compatible function tools (update_lead_profile, determine_call_outcome) with ToolContext state management and two Supabase async helpers with Content-Profile: sales_agent header pattern
- Full test suite of 23 tests covering all plan requirements with TDD red-green methodology

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Knowledge loader tests** - `48b2899` (test) -- conftest.py, test_knowledge_loader.py, test_system_instruction.py, pyproject.toml
2. **Task 1 (GREEN): Knowledge loader implementation** - `2d79fff` (feat) -- knowledge_loader.py, conftest.py fix, requirements.txt
3. **Task 2 (RED): ADK tools tests** - `8570fdc` (test) -- test_tools.py
4. **Task 2 (GREEN): ADK tools implementation** - `740b792` (feat) -- tools.py rewrite

_Note: TDD tasks have separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `backend/knowledge_loader.py` - Firestore KB pre-loader and system instruction builder with Sarah's persona
- `backend/tools.py` - ADK function tools (update_lead_profile, determine_call_outcome) and Supabase async helpers
- `backend/requirements.txt` - Bumped google-adk to >=1.26.0, google-genai to >=1.66.0, added soxr, pytest, pytest-asyncio, pytest-mock
- `tests/conftest.py` - Shared fixtures: mock_firestore_db, mock_firestore_db_missing_one, mock_supabase_config, sample_kb_content
- `tests/test_knowledge_loader.py` - 4 tests: KB preload (5 docs), missing doc resilience, name personalization, KB content inclusion
- `tests/test_system_instruction.py` - 10 tests: AI disclosure (CALL-02), qualification fields (CALL-03), programme recommendation (CALL-04), objection handling (CALL-05), commitment rules (CALL-06), watchdog (CALL-08), follow-up timing (CALL-10)
- `tests/test_tools.py` - 9 tests: update_lead_profile state/return, determine_call_outcome validation/storage, follow_up_preference capture, Supabase PATCH/POST with Content-Profile
- `pyproject.toml` - pytest-asyncio auto mode configuration

## Decisions Made
- AsyncMock with return_value for Firestore mock chain instead of side_effect with async lambda -- the latter created a double-coroutine issue where the coroutine was never awaited
- Tools store qualification and outcome data in ToolContext.state dict for immediate return to Gemini, with Supabase writes deferred to call cleanup -- keeps tool execution non-blocking during live audio
- SUPABASE_URL and SUPABASE_SERVICE_KEY read from env at module level in tools.py, matching the established pattern from logger.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed conftest.py AsyncMock chain for Firestore document.get()**
- **Found during:** Task 1 (Knowledge loader GREEN phase)
- **Issue:** `AsyncMock(side_effect=lambda: mock_get(doc_id))` where `mock_get` is async created a double-coroutine -- the lambda returns a coroutine, and AsyncMock wraps it in another
- **Fix:** Changed to `AsyncMock(return_value=mock_doc)` where mock_doc is pre-computed in the `mock_document` closure
- **Files modified:** tests/conftest.py
- **Verification:** All 14 Task 1 tests pass
- **Committed in:** 2d79fff (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test infrastructure correctness. No scope creep.

## Issues Encountered
- Task 1 RED phase was already committed (48b2899) from a prior session -- continued from GREEN phase without redoing RED work
- requirements.txt already had most updates staged from a prior session -- included in Task 1 GREEN commit

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- knowledge_loader.py and tools.py are the foundation modules that all other Phase 3 plans depend on
- Plan 03-02 (agent.py + voice_handler.py) can import knowledge_loader and tools directly
- Plan 03-03 (call_manager.py + main.py routes) can use the Supabase helpers and tool state patterns
- 23 tests provide regression safety for ongoing Phase 3 development

## Self-Check: PASSED

- All 8 files exist on disk
- All 4 commits verified in git log
- 23/23 tests pass

---
*Phase: 03-voice-agent-backend*
*Completed: 2026-03-12*

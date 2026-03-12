---
phase: 03-voice-agent-backend
plan: 03
subsystem: voice-agent
tags: [websocket, fastapi, adk, gemini, streaming, asyncio, firestore, supabase, pytest]

# Dependency graph
requires:
  - phase: 03-voice-agent-backend
    plan: 01
    provides: "knowledge_loader.py (load_knowledge_base, build_system_instruction), tools.py (update_lead_profile, determine_call_outcome, Supabase async helpers)"
  - phase: 03-voice-agent-backend
    plan: 02
    provides: "agent.py (create_sarah_agent), call_manager.py (CallSession, duration_watchdog, process_call_end)"
provides:
  - "voice_handler.py: WebSocket handler with full ADK Runner streaming pipeline (fetch lead, load KB, create agent, bidirectional audio, transcript capture, cleanup)"
  - "voice_handler.py: fetch_lead() for Supabase REST lead retrieval with Accept-Profile: sales_agent"
  - "voice_handler.py: get_firestore_client() module-level Firestore AsyncClient singleton"
  - "main.py: /ws/voice/{lead_id} WebSocket endpoint for browser voice sessions"
  - "test_voice_session.py: 9 integration tests covering full handler lifecycle"
affects: [04-browser-voice-ui, 05-cloud-run-deployment, 06-twilio-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [websocket-to-adk-runner-pipeline, asyncio-gather-3-tasks, module-level-firestore-client, supabase-rest-lead-fetch]

key-files:
  created:
    - tests/test_voice_session.py
  modified:
    - backend/voice_handler.py
    - backend/main.py
    - tests/conftest.py

key-decisions:
  - "Module-level Firestore AsyncClient singleton in voice_handler.py -- reused across calls to avoid repeated client creation"
  - "WebSocket close code 4004 for lead-not-found -- custom application code distinct from standard WebSocket close codes"
  - "Tool state extraction via session_service.get_session after streaming ends -- reads ToolContext.state values set by Gemini during the call"
  - "google.cloud.firestore mock added to conftest.py for voice_handler import support without installing google-cloud-firestore"

patterns-established:
  - "WebSocket handler pattern: accept -> fetch lead -> load KB -> build instruction -> create agent -> Runner -> stream (gather upstream + downstream + watchdog) -> finally: cancel watchdog, close queue, extract state, process_call_end, log"
  - "Three concurrent asyncio tasks via gather(upstream_audio, downstream_audio, watchdog, return_exceptions=True)"
  - "ADK event processing: check event.content.parts for audio data, event.input_transcription for user speech, event.output_transcription for agent speech"
  - "FastAPI TestClient WebSocket testing pattern with comprehensive mocking of voice_handler internal dependencies"

requirements-completed: [CALL-01, CALL-02, CALL-03, CALL-04, CALL-05, CALL-06, CALL-08, CALL-10]

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 3 Plan 03: WebSocket Voice Handler & Integration Tests Summary

**FastAPI WebSocket voice handler wiring Supabase lead fetch -> Firestore KB -> ADK Runner bidirectional audio streaming with transcript capture, duration watchdog, and guaranteed cleanup, plus 9 integration tests verifying full session lifecycle**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-12T21:39:55Z
- **Completed:** 2026-03-12T21:47:34Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- voice_handler.py rewritten from stub to full WebSocket-to-ADK pipeline: fetch lead from Supabase, load KB from Firestore, build system instruction, create agent, stream bidirectional audio via asyncio.gather (upstream + downstream + watchdog), capture transcriptions, extract tool state (qualification + outcome) from session, call process_call_end, log events
- main.py updated with /ws/voice/{lead_id} WebSocket endpoint connecting browser clients to Sarah
- 9 integration tests verify the complete handler lifecycle: session setup, lead-not-found error, cleanup on disconnect, watchdog integration, transcription accumulation, health endpoint regression, and fetch_lead unit tests
- All 52 tests pass across the full Phase 3 suite (Plans 01-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: WebSocket voice handler with ADK Runner streaming** - `9ac7462` (feat) -- voice_handler.py, main.py, conftest.py
2. **Task 2: Integration test for voice session lifecycle** - `4f1c041` (test) -- test_voice_session.py

## Files Created/Modified
- `backend/voice_handler.py` - Complete WebSocket handler: fetch_lead, get_firestore_client, handle_voice_session with ADK Runner streaming pipeline
- `backend/main.py` - Added /ws/voice/{lead_id} WebSocket route, imported handle_voice_session, removed Phase 3 TODO
- `tests/test_voice_session.py` - 9 integration tests for voice session lifecycle (setup, error, cleanup, transcription, health)
- `tests/conftest.py` - Added google.cloud and google.cloud.firestore mock modules for voice_handler import support

## Decisions Made
- Module-level Firestore AsyncClient singleton (get_firestore_client) reuses the client across calls, avoiding repeated initialization overhead per WebSocket connection
- WebSocket close code 4004 used for lead-not-found (custom application error code, avoids ambiguity with standard 1000-series codes)
- Tool state extraction reads session.state after streaming ends via session_service.get_session -- the ToolContext.state dict populated by Gemini's tool calls during the conversation is persisted in the ADK session
- google.cloud.firestore mock module added to conftest.py since voice_handler.py imports firestore at module level (same pattern as existing google.adk mocks)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added google.cloud.firestore mock module to conftest.py**
- **Found during:** Task 1 (voice_handler implementation)
- **Issue:** voice_handler.py imports `from google.cloud import firestore` at module level, but google-cloud-firestore is not installed in the test environment
- **Fix:** Added `google.cloud` and `google.cloud.firestore` mock modules to `_setup_mock_google_modules()` in conftest.py, following the same pattern used for google.adk and google.genai
- **Files modified:** tests/conftest.py
- **Verification:** All 52 tests pass, voice_handler imports correctly
- **Committed in:** 9ac7462 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary test infrastructure for new module import. No scope creep.

## Issues Encountered
None -- implementation followed the plan specification exactly. FastAPI required installation (`pip install fastapi httpx`) for import verification outside the test environment, but this is expected in a fresh environment without `pip install -r requirements.txt`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 (Voice Agent Backend) is now COMPLETE -- all 3 plans executed successfully
- Complete module chain: knowledge_loader.py -> tools.py -> agent.py -> call_manager.py -> voice_handler.py -> main.py
- Phase 4 (Browser Voice UI) can connect to /ws/voice/{lead_id} WebSocket endpoint with 16kHz PCM audio
- Phase 5 (Cloud Run Deployment) can deploy main.py with all dependencies in requirements.txt
- Phase 6 (Twilio Integration) will add mulaw transcoding in voice_handler.py and a new /twilio/voice route in main.py
- 52 tests across 6 test files provide full regression safety

## Self-Check: PASSED

- All 4 files exist on disk
- Both commits verified in git log (9ac7462, 4f1c041)
- 52/52 tests pass

---
*Phase: 03-voice-agent-backend*
*Completed: 2026-03-12*

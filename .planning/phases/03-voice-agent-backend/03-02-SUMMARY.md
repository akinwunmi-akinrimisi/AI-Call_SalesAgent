---
phase: 03-voice-agent-backend
plan: 02
subsystem: voice-agent
tags: [adk, agent, gemini, call-manager, watchdog, supabase, asyncio, pytest]

# Dependency graph
requires:
  - phase: 03-voice-agent-backend
    plan: 01
    provides: "knowledge_loader.py (build_system_instruction), tools.py (update_lead_profile, determine_call_outcome, Supabase async helpers)"
provides:
  - "agent.py: create_sarah_agent() factory with dynamic system instruction and 2 ADK tool bindings"
  - "call_manager.py: CallSession class for call state, transcript, and outcome tracking"
  - "call_manager.py: duration_watchdog() that injects wrap-up signal at configurable timeout"
  - "call_manager.py: process_call_end() for Supabase writes and CALL_DROPPED fallback"
  - "conftest.py: mock google.adk and google.genai module hierarchy for test isolation"
  - "Full pytest suite: 20 new tests (43 total) covering CALL-01 backend and CALL-08"
affects: [03-03-PLAN, 05-cloud-run-deployment, 06-twilio-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [mock-adk-module-hierarchy, callsession-state-tracking, asyncio-watchdog-with-cancellation, call-outcome-post-processing]

key-files:
  created:
    - backend/call_manager.py
    - tests/test_agent.py
    - tests/test_call_manager.py
  modified:
    - backend/agent.py
    - tests/conftest.py

key-decisions:
  - "Mock google.adk and google.genai via sys.modules in conftest.py -- avoids installing heavy ADK package for unit tests while testing agent construction logic"
  - "CallSession stores qualification and outcome as separate dicts -- qualification from update_lead_profile tool, outcome from determine_call_outcome tool, written to Supabase independently in process_call_end"
  - "duration_watchdog uses asyncio.sleep with CancelledError handling -- clean cancellation when call ends before 8.5 minutes, no orphaned tasks"
  - "_update_lead_status is a separate internal helper for Supabase PATCH -- keeps process_call_end focused on orchestration logic"

patterns-established:
  - "Mock ADK module hierarchy: conftest registers _MockAgent, _MockContent, _MockPart in sys.modules for google.adk.* and google.genai.types"
  - "CallSession as state container: lead_id, lead_name, transcripts, outcome, qualification, watchdog_task -- passed through entire call lifecycle"
  - "Watchdog pattern: asyncio.create_task(duration_watchdog(...)), cancel on disconnect, CancelledError = silent return"
  - "Call cleanup pattern: process_call_end checks outcome presence, falls back to CALL_DROPPED, writes call_log, lead profile, lead status, pipeline events"

requirements-completed: [CALL-01, CALL-08]

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 3 Plan 02: ADK Agent Definition & Call Session Manager Summary

**ADK Agent factory (create_sarah_agent) with dynamic system instruction and tool bindings, plus CallSession state tracker with 8.5-minute duration watchdog and Supabase call outcome post-processing for normal completion and CALL_DROPPED fallback**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-12T21:28:27Z
- **Completed:** 2026-03-12T21:33:32Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- agent.py rewritten from stub to export create_sarah_agent() that produces an ADK Agent with name="Sarah", model="gemini-live-2.5-flash-native-audio", 2 tool bindings (update_lead_profile, determine_call_outcome), and dynamic system instruction
- call_manager.py created with CallSession class for call state tracking (lead_id, lead_name, transcripts, outcome, qualification, elapsed_seconds, full_transcript formatting)
- duration_watchdog fires at configurable timeout (default 510s / 8.5 min), injects [INTERNAL SYSTEM SIGNAL] content into LiveRequestQueue, cleanly cancellable via asyncio
- process_call_end handles both normal completion (writes call_log, lead profile, lead status, pipeline events) and abnormal disconnect (CALL_DROPPED fallback with partial transcript)
- 20 new tests (43 total with Plan 01) covering agent creation, call state, watchdog timing/content/cancellation, and all process_call_end scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Agent and call manager tests** - `79a97ae` (test) -- test_agent.py (7 tests), test_call_manager.py (13 tests)
2. **Task 1 (GREEN): Agent and call manager implementation** - `ceb94d5` (feat) -- agent.py, call_manager.py, conftest.py ADK mocks

_Note: TDD task has separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `backend/agent.py` - ADK Agent factory with create_sarah_agent(system_instruction) -> Agent
- `backend/call_manager.py` - CallSession state tracker, duration_watchdog, process_call_end
- `tests/test_agent.py` - 7 tests for agent creation (name, model, tools, instruction, description)
- `tests/test_call_manager.py` - 13 tests for CallSession, watchdog, process_call_end scenarios
- `tests/conftest.py` - Added mock google.adk and google.genai module hierarchy for test isolation

## Decisions Made
- Mock google.adk and google.genai module hierarchy via sys.modules in conftest.py rather than installing heavy ADK package -- enables fast unit tests while verifying agent construction logic, tool binding, and mock Content/Part types
- CallSession stores qualification and outcome as separate dicts (populated by ToolContext.state during the call), written to Supabase independently in process_call_end
- duration_watchdog uses asyncio.sleep with CancelledError handling for clean cancellation when call ends before timeout
- _update_lead_status is a separate internal async helper for Supabase PATCH, keeping process_call_end focused on orchestration

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added mock google.adk and google.genai modules to conftest.py**
- **Found during:** Task 1 (GREEN phase -- running tests after implementation)
- **Issue:** agent.py imports `from google.adk.agents import Agent` at module level. google-adk package is not installed in the test environment, causing `ModuleNotFoundError`
- **Fix:** Added `_setup_mock_google_modules()` to conftest.py that registers mock Agent, Content, Part, and other ADK classes in sys.modules before any backend module is imported
- **Files modified:** tests/conftest.py
- **Verification:** All 43 tests pass (20 new + 23 from Plan 01)
- **Committed in:** ceb94d5 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary test infrastructure for ADK module mocking. No scope creep.

## Issues Encountered
None -- implementation followed the plan specification exactly. The only issue was the missing google-adk package in the test environment, resolved via module mocking (documented as deviation above).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- agent.py and call_manager.py are ready for Plan 03-03 (voice_handler.py WebSocket integration)
- Plan 03-03 will wire: create_sarah_agent() -> Runner -> LiveRequestQueue -> WebSocket, with CallSession tracking and watchdog
- conftest.py ADK mocks support all future Phase 3 tests without package installation
- 43 tests provide regression safety for ongoing Phase 3 development

## Self-Check: PASSED

- All 5 files exist on disk
- Both commits verified in git log (79a97ae, ceb94d5)
- 43/43 tests pass

---
*Phase: 03-voice-agent-backend*
*Completed: 2026-03-12*

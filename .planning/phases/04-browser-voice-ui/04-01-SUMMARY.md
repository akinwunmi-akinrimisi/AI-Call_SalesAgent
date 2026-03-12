---
phase: 04-browser-voice-ui
plan: 01
subsystem: ui, api, audio
tags: [react, vite, audioworklet, websocket, pcm, barge-in, fastapi]

# Dependency graph
requires:
  - phase: 03-voice-agent-backend
    provides: voice_handler.py WebSocket handler, main.py FastAPI server, config.py env loader
provides:
  - Transcript forwarding via WebSocket JSON messages
  - GET /api/leads REST endpoint for lead listing
  - GET /api/call/{lead_id}/latest REST endpoint for call summary
  - Vite dev server with proxy to FastAPI backend
  - AudioWorklet processors for 16kHz capture and 24kHz ring buffer playback
  - PCM conversion and RMS amplitude utilities
  - useVoiceSession React hook for full audio pipeline orchestration
  - Barge-in detection with automated test coverage (COMP-01)
affects: [04-02-PLAN, 05-cloud-run-deployment]

# Tech tracking
tech-stack:
  added: [vitest, @testing-library/react, @testing-library/jest-dom, jsdom]
  patterns: [AudioWorklet for Web Audio processing, ring buffer for audio playback, VAD-based barge-in, extracted testable pure functions from hooks]

key-files:
  created:
    - frontend/index.html
    - frontend/vite.config.js
    - frontend/src/audio/pcm-recorder-processor.js
    - frontend/src/audio/pcm-player-processor.js
    - frontend/src/utils/pcm.js
    - frontend/src/hooks/useVoiceSession.js
    - frontend/src/hooks/useVoiceSession.test.js
    - tests/test_api_endpoints.py
  modified:
    - backend/voice_handler.py
    - backend/main.py
    - frontend/package.json

key-decisions:
  - "Extracted checkBargeIn as testable pure function from useVoiceSession hook for direct unit testing (COMP-01)"
  - "VAD_THRESHOLD set to 0.015 RMS for barge-in detection, exported as named constant for tuning"
  - "Ring buffer size 24000*180 (~3 min) in player processor to avoid overflow during long responses"
  - "Vitest with jsdom environment for frontend testing (lighter than full browser)"

patterns-established:
  - "AudioWorklet pattern: processor files loaded via new URL() for Vite asset handling"
  - "PCM utility functions: shared Float32/Int16 conversion used by both hook and tests"
  - "WebSocket protocol: binary for audio, JSON text for transcripts on same connection"
  - "React hook exports testable pure functions for complex logic"

requirements-completed: [DEPL-03, COMP-01]

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 4 Plan 01: Audio Plumbing Summary

**Backend transcript forwarding + REST endpoints, Vite dev proxy, AudioWorklet 16kHz/24kHz processors, useVoiceSession hook with VAD-based barge-in detection, and 7 automated barge-in tests (COMP-01)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-12T23:18:37Z
- **Completed:** 2026-03-12T23:26:45Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Backend voice_handler.py now forwards user and agent transcripts as JSON messages on the same WebSocket alongside binary audio
- Two new REST endpoints (GET /api/leads, GET /api/call/{lead_id}/latest) query Supabase with Accept-Profile: sales_agent header
- Complete client-side audio engine: 16kHz mic capture, 24kHz ring buffer playback, barge-in buffer flush via clearBuffer command
- useVoiceSession React hook manages full WebSocket + audio pipeline lifecycle with amplitude tracking for visualization
- 7 automated barge-in tests (COMP-01) validate clearBuffer logic with boundary conditions
- All 58 backend tests pass, 7 frontend tests pass, production build completes without errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend modifications -- transcript forwarding + REST endpoints (TDD)**
   - `6c3a6c6` (test: add failing tests for REST endpoints and transcript forwarding)
   - `4f54968` (feat: add transcript forwarding and REST endpoints)
2. **Task 2: Frontend infrastructure -- Vite config, AudioWorklet, PCM utils, useVoiceSession hook, barge-in test** - `9dbdd81` (feat)

## Files Created/Modified

- `backend/voice_handler.py` - Added transcript forwarding via websocket.send_json after each transcription capture
- `backend/main.py` - Added GET /api/leads and GET /api/call/{lead_id}/latest REST endpoints with httpx + Supabase
- `tests/test_api_endpoints.py` - 4 tests for REST endpoints (list leads, error handling, latest call, not found)
- `tests/test_voice_session.py` - 2 tests added for transcript forwarding (user + agent)
- `frontend/index.html` - Vite entry point with #root div and module script
- `frontend/vite.config.js` - Dev server proxy for /ws (WebSocket) and /api to localhost:8000
- `frontend/src/audio/pcm-recorder-processor.js` - AudioWorklet capturing mono Float32 mic audio at 16kHz
- `frontend/src/audio/pcm-player-processor.js` - AudioWorklet ring buffer player with clearBuffer command for barge-in
- `frontend/src/utils/pcm.js` - convertFloat32ToPCM16, computeRMS, computePCMAmplitude utilities
- `frontend/src/hooks/useVoiceSession.js` - WebSocket + audio pipeline orchestration hook with barge-in detection
- `frontend/src/hooks/useVoiceSession.test.js` - 7 tests for barge-in clearBuffer logic (COMP-01 coverage)
- `frontend/package.json` - Added vitest, @testing-library/react, @testing-library/jest-dom, jsdom dev dependencies

## Decisions Made

- Extracted checkBargeIn as a testable pure function from useVoiceSession hook for direct unit testing (simpler than mocking entire browser audio API chain via renderHook)
- VAD_THRESHOLD set to 0.015 RMS (exported constant, easily tunable)
- Ring buffer sized at 24000 * 180 samples (~3 min at 24kHz) to handle long agent responses without overflow
- Used Vitest with jsdom environment for frontend tests (lighter weight than full browser, compatible with Vite config)
- Added test script to package.json for convenient `npm test` execution

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All backend-to-frontend plumbing is complete (transcript forwarding, REST endpoints, audio pipeline)
- Plan 02 can now build the React visual components (VoiceAgent.jsx, LeadList.jsx) on top of the useVoiceSession hook
- The useVoiceSession hook exports status, transcripts, amplitudes, startCall, and endCall for the UI layer

## Self-Check: PASSED

- All 10 created/modified files verified on disk
- All 3 task commits (6c3a6c6, 4f54968, 9dbdd81) verified in git log
- 58 backend tests pass, 7 frontend tests pass
- Vite production build completes without errors

---
*Phase: 04-browser-voice-ui*
*Completed: 2026-03-12*

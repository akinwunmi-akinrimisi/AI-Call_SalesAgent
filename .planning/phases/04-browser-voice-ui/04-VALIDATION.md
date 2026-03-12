---
phase: 4
slug: browser-voice-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (frontend, not yet installed) + pytest 9.0.2 (backend, existing) |
| **Config file** | frontend/vitest.config.js (Wave 0 creates) + tests/conftest.py (existing) |
| **Quick run command** | `cd frontend && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd frontend && npx vitest run && cd ../tests && python -m pytest -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run --reporter=verbose`
- **After every plan wave:** Run `cd frontend && npx vitest run && cd ../tests && python -m pytest -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DEPL-03 | integration | `cd tests && python -m pytest test_api_endpoints.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | DEPL-03 | integration | `cd tests && python -m pytest test_voice_session.py::test_transcript_forwarding -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | DEPL-03 | smoke | `cd frontend && npx vitest run src/App.test.jsx` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | COMP-02 | unit | `cd frontend && npx vitest run src/utils/pcm.test.js` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | COMP-01 | unit | `cd frontend && npx vitest run src/hooks/useVoiceSession.test.js` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | COMP-01 | manual | Browser test: speak while Sarah talks | N/A | ⬜ pending |
| 04-02-04 | 02 | 2 | DEPL-03 | e2e | Browser test: full call flow pre-call -> active -> post-call | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.js` — Vitest config (environment: jsdom)
- [ ] `frontend/src/App.test.jsx` — Basic render test for App component
- [ ] `frontend/src/utils/pcm.test.js` — Unit tests for Float32<->Int16 PCM conversion and RMS amplitude
- [ ] `frontend/src/hooks/useVoiceSession.test.js` — WebSocket hook tests (mock WebSocket, barge-in logic)
- [ ] `tests/test_api_endpoints.py` — Integration tests for GET /api/leads and GET /api/call/{id}/latest
- [ ] `tests/test_voice_session.py` — Add test_transcript_forwarding to existing file
- [ ] Install: `cd frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Barge-in stops Sarah mid-sentence | COMP-01 | Requires real microphone + speaker interaction | 1. Start call 2. Let Sarah speak 3. Interrupt by speaking 4. Verify Sarah stops and buffered audio clears |
| Audio visualization pulses with speech | COMP-02 | Requires visual inspection of CSS animation | 1. During call 2. Verify blue circle pulses when user speaks 3. Verify green circle pulses when Sarah speaks |
| Full qualification flow in browser | DEPL-03 | End-to-end requires real Gemini API | 1. Start call with test lead 2. Complete greeting -> qualification -> recommendation -> close 3. Verify post-call summary shows outcome |
| Responsive layout stacking | DEPL-03 | Visual layout check | 1. Resize browser below 768px 2. Verify panels stack vertically |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

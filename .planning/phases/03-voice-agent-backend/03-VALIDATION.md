---
phase: 3
slug: voice-agent-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | None -- Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | CALL-01 | integration | `pytest tests/test_voice_session.py::test_session_creation -x` | No -- W0 | pending |
| 03-01-02 | 01 | 1 | CALL-02 | unit | `pytest tests/test_system_instruction.py::test_ai_disclosure -x` | No -- W0 | pending |
| 03-01-03 | 01 | 1 | CALL-03 | unit | `pytest tests/test_system_instruction.py::test_qualification_fields -x` | No -- W0 | pending |
| 03-01-04 | 01 | 1 | CALL-04 | unit | `pytest tests/test_system_instruction.py::test_programme_recommendation -x` | No -- W0 | pending |
| 03-01-05 | 01 | 1 | CALL-05 | unit | `pytest tests/test_knowledge_loader.py::test_kb_preload -x` | No -- W0 | pending |
| 03-02-01 | 02 | 1 | CALL-06 | unit | `pytest tests/test_tools.py::test_outcome_determination -x` | No -- W0 | pending |
| 03-02-02 | 02 | 1 | CALL-10 | unit | `pytest tests/test_tools.py::test_follow_up_preference -x` | No -- W0 | pending |
| 03-03-01 | 03 | 1 | CALL-08 | unit | `pytest tests/test_call_manager.py::test_watchdog_timing -x` | No -- W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` -- shared fixtures (mock Firestore, mock Supabase, mock ADK session)
- [ ] `tests/test_system_instruction.py` -- covers CALL-02, CALL-03, CALL-04
- [ ] `tests/test_knowledge_loader.py` -- covers CALL-05
- [ ] `tests/test_tools.py` -- covers CALL-06, CALL-10
- [ ] `tests/test_call_manager.py` -- covers CALL-08
- [ ] `tests/test_voice_session.py` -- covers CALL-01 (integration, may need mock ADK runner)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` -- pytest config with asyncio_mode=auto
- [ ] Framework install: `pip install pytest pytest-asyncio pytest-mock`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sarah's conversational tone feels natural and coach-like | CALL-02 | Subjective persona quality | Listen to test call recording, verify tone matches persona spec |
| Qualification flow adapts to lead's answers | CALL-03 | Requires real conversation dynamics | Run simulated call, verify Sarah skips already-answered questions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

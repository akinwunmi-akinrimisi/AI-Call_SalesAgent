---
phase: 1
slug: prerequisites
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python scripts with pass/fail output (no formal test framework for Phase 1) |
| **Config file** | None -- Phase 1 validation scripts are standalone |
| **Quick run command** | `python scripts/validate_gemini.py && python scripts/validate_pdfs.py` |
| **Full suite command** | `python scripts/validate_gemini.py && python scripts/validate_twilio.py && python scripts/validate_pdfs.py && python scripts/validate_services.py` |
| **Estimated runtime** | ~30 seconds (includes network calls to external APIs) |

---

## Sampling Rate

- **After every task commit:** Run the relevant validation script for the task
- **After every plan wave:** Run `python scripts/validate_gemini.py && python scripts/validate_twilio.py && python scripts/validate_pdfs.py && python scripts/validate_services.py`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | SC-1 (Gemini audio) | integration | `python scripts/validate_gemini.py` | No -- Wave 0 | pending |
| 01-01-02 | 01 | 1 | SC-2 (Twilio numbers) | integration | `python scripts/validate_twilio.py` | No -- Wave 0 | pending |
| 01-02-01 | 02 | 1 | SC-3 (PDFs exist) | unit | `python scripts/validate_pdfs.py` | No -- Wave 0 | pending |
| 01-02-02 | 02 | 1 | SC-4 (.env complete) | unit | `python scripts/validate_services.py` | No -- Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `scripts/validate_gemini.py` -- Gemini Live API audio round-trip test (includes mulaw transcoding test)
- [ ] `scripts/validate_twilio.py` -- Twilio credentials check + verified number count
- [ ] `scripts/validate_pdfs.py` -- PDF extraction + section keyword validation
- [ ] `scripts/validate_services.py` -- Supabase, n8n, OpenClaw, Resend reachability
- [ ] Install: `pip install google-genai google-auth pymupdf pymupdf4llm audioop-lts resend supabase`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Twilio phone number SMS OTP verification | SC-2 | Requires human to receive and enter OTP code | Add each number via Twilio console, enter OTP received on phone |
| Audio quality listening test | SC-1 | Subjective quality judgment | Run validate_gemini.py, listen to saved audio sample |
| Nigeria (+234) geographic permissions | SC-2 | Twilio console UI check | Twilio Console > Voice > Geo permissions > verify Nigeria enabled |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

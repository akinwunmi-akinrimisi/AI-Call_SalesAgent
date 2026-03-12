---
phase: 2
slug: data-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (to be installed) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_data_layer.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_data_layer.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DATA-01 | integration | `pytest tests/test_import_leads.py::test_csv_import_creates_leads -x` | No — W0 | pending |
| 02-01-02 | 01 | 1 | DATA-01 | unit | `pytest tests/test_import_leads.py::test_phone_validation -x` | No — W0 | pending |
| 02-01-03 | 01 | 1 | DATA-02 | smoke | `pytest tests/test_schema.py::test_sales_agent_schema_exists -x` | No — W0 | pending |
| 02-01-04 | 01 | 1 | DATA-02 | smoke | `pytest tests/test_schema.py::test_schema_isolation -x` | No — W0 | pending |
| 02-02-01 | 02 | 1 | DATA-03 | integration | `pytest tests/test_firestore.py::test_knowledge_base_seeded -x` | No — W0 | pending |
| 02-02-02 | 02 | 1 | DATA-03 | integration | `pytest tests/test_firestore.py::test_query_programme_details -x` | No — W0 | pending |
| 02-03-01 | 03 | 2 | DATA-04 | integration | `pytest tests/test_pipeline_logs.py::test_log_event_writes -x` | No — W0 | pending |
| 02-03-02 | 03 | 2 | DATA-04 | integration | `pytest tests/test_pipeline_logs.py::test_query_by_lead_id -x` | No — W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_import_leads.py` — stubs for DATA-01 (phone validation + import)
- [ ] `tests/test_schema.py` — stubs for DATA-02 (schema existence, isolation)
- [ ] `tests/test_firestore.py` — stubs for DATA-03 (document existence, content query)
- [ ] `tests/test_pipeline_logs.py` — stubs for DATA-04 (write + read pipeline logs)
- [ ] `tests/conftest.py` — shared fixtures (Supabase client, test CSV data)
- [ ] `pip install pytest pytest-asyncio` — no test framework currently installed
- [ ] `pyproject.toml` or `pytest.ini` — pytest configuration with asyncio mode

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Supabase Docker schema exposure | DATA-02 | Requires SSH to VPS #1 and Docker restart | SSH into VPS #1, update PGRST_DB_SCHEMAS, restart containers, verify via Studio |
| Firestore DB creation via gcloud | DATA-03 | One-time gcloud CLI command on VPS #1 | SSH into VPS #1, run `gcloud firestore databases create`, verify in GCP Console |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

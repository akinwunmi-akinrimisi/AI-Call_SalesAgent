# CLAUDE.md — Cloudboosta AI Sales Agent
## Project Instructions for Claude Code

> This file is loaded automatically by Claude Code at session start.
> It defines how to build this project using GSD for project management
> and Agency Agents for specialist execution.

---

## Project Context

You are building an AI sales call agent for Cloudboosta, a cloud/DevOps training company.
The system automates lead outreach (WhatsApp + email), books calls, conducts AI voice sales
conversations via Gemini, and follows up with payment instructions.

**Read AGENT.md first.** It contains the full DOE (Directive → Observation → Experiment)
rules, the 10-stage pipeline, data schemas, environment variables, and delegation rules.
AGENT.md is the source of truth. This file tells you how to work. AGENT.md tells you what to build.

---

## How This Project Is Built

### GSD is the Project Manager
Use GSD commands for all project flow:
- `/gsd:new-project` — initial setup (already done if SPEC.md exists)
- `/gsd:discuss-phase N` — clarify requirements for phase N
- `/gsd:plan-phase N` — create execution plan for phase N
- `/gsd:execute-phase N` — implement phase N
- `/gsd:verify-work N` — validate phase N deliverables
- `/gsd:complete-milestone` — archive and tag
- `/gsd:quick "task"` — ad-hoc tasks outside the phase flow

### Agency Agents Are the Specialists
**GSD MUST delegate to Agency Agents for all specialist work.**
This is not optional. This is enforced.

When `/gsd:execute-phase` reaches a task that involves:
- Python backend code → `@backend-architect`
- React/frontend code → `@frontend-developer`
- Docker/deployment/Cloud Run → `@devops-engineer`
- Twilio/API integration → `@api-developer`
- SQL/Supabase/database → `@database-architect`
- Security/credentials → `@security-engineer`
- Testing → `@qa-engineer`
- Documentation → `@technical-writer`
- UI/UX design → `@ux-designer`
- Prompt engineering (Sarah's persona) → `@prompt-engineer`

**GSD writes the requirement. The Agency Agent writes the code.**

Example flow during `/gsd:execute-phase 3` (Voice Agent Backend):
```
GSD: "Phase 3 Task 1: Create the ADK agent definition with Sarah's persona"
→ GSD delegates: "Use @backend-architect to implement agent.py with the ADK framework.
   Use @prompt-engineer to craft the system instruction for Sarah.
   Refer to AGENT.md Section 3 for Sarah's profile."
→ @backend-architect writes agent.py
→ @prompt-engineer writes the system_instruction string
→ GSD verifies: "Does agent.py match the spec in directives/05_voice_call.md?"
```

---

## Critical Rules

### Never Hardcode Secrets
```python
# ❌ WRONG
TWILIO_SID = "ACxxxxxxxx"

# ✅ CORRECT
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
```

### Always Log to pipeline_logs
Every significant action in the backend must write to Supabase `pipeline_logs`:
```python
from logger import log_event
log_event("call_started", f"Call initiated for lead {lead_id}", lead_id=lead_id)
```

### Knowledge Base is PDF-Driven
Sarah's knowledge comes from PDF files in `knowledge-base/`. Never hardcode programme details,
pricing, or FAQ answers in the code. Always read from Firestore at runtime.

### Two Separate Systems
- OpenClaw (Hostinger VPS #2) = WhatsApp text messages. Brain: Gemini API.
- Cloud Run (GCP) = Voice calls via Twilio. Brain: Gemini Live API.
- n8n (Hostinger VPS #1) = Coordinates both. No AI brain — deterministic workflows.
- They NEVER talk to each other directly. n8n is the only bridge.

---

## Phase Reference (Maps to AGENT.md Section 9)

| Phase | What Gets Built | Primary Agent |
|-------|----------------|---------------|
| 1 | Prerequisites (PDFs, accounts, webhooks) | `@technical-writer` |
| 2 | Supabase schema + Firestore seed | `@database-architect` |
| 3 | Voice agent backend (Python/ADK/Gemini) | `@backend-architect` |
| 4 | Browser voice UI (React) | `@frontend-developer` |
| 5 | Cloud Run deployment | `@devops-engineer` |
| 6 | Twilio integration | `@api-developer` + `@backend-architect` |
| 7 | OpenClaw WhatsApp config | `@api-developer` |
| 8 | n8n orchestration workflows | `@api-developer` |
| 9 | n8n monitoring workflows | `@api-developer` + `@devops-engineer` |
| 10 | E2E testing (Wave 0) | `@qa-engineer` |
| 11 | Wave 1 launch (200 leads) | All on standby |

---

## Reference Documents

| Document | Location | Use |
|----------|----------|-----|
| AGENT.md | Project root | DOE rules, pipeline, delegation matrix |
| skills.md | Project root | Technical skills and patterns |
| skills.sh | Project root | Environment validation |
| Definitive v2.0 | `docs/` | Full customer journey specification |
| GCP Build Guide | `docs/` | Every GCP command and code file |
| Monitoring Guide | `docs/` | Supabase SQL, n8n workflows, dashboard spec |
| Directives | `directives/` | Per-stage build specs |

---

## Quick Start

```bash
# 1. Validate environment
bash skills.sh

# 2. Start GSD
/gsd:new-project
# OR if resuming:
/gsd:resume

# 3. Follow the phase flow
/gsd:discuss-phase 1
/gsd:plan-phase 1
/gsd:execute-phase 1
/gsd:verify-work 1
# ... repeat for each phase
```

---

> ⚠️ If you are Claude Code reading this: ALWAYS check AGENT.md Section 6 before executing any task.
> If the task belongs to a specialist domain, you MUST delegate to the correct Agency Agent.
> You are the coordinator, not the builder. GSD plans. Agency Agents build. You verify.

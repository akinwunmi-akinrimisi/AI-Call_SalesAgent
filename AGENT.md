# Agent Instructions (DOE)
## Cloudboosta — AI Sales Call Agent
### Directive → Observation → Experiment

> **This system turns community members into enrolled students.**
> Every WhatsApp message, every phone call, every email is a touchpoint in a revenue pipeline.
> If a lead falls through the cracks, that's lost revenue. Reliability and accuracy are non-negotiable.

**Version 1.0 | Operscale / Cloudboosta Systems | March 2026**
**Owner:** Akinwunmi Akinrimisi
**Stack:** Google Cloud (Cloud Run + Firestore + Gemini Live API + ADK) + Twilio (voice calls) + OpenClaw (WhatsApp via Hostinger VPS) + n8n (orchestration via Hostinger VPS) + Supabase (PostgreSQL) + Claude Code + GSD + Agency Agents

---

## ⚠️ IMMUTABLE — Non-Negotiable Operating Rules

- Read the relevant `directives/` file for every pipeline stage before writing or modifying any logic.
- **Never hardcode API keys** (Gemini, Twilio, Supabase, OpenClaw). Always reference environment variables, n8n credentials, or `.env` files.
- **GSD is the project manager. Agency Agents are the specialists.** GSD handles project flow (discuss → plan → execute → verify). When a task falls within a specialist domain, GSD MUST hand it to the correct Agency Agent (see Section 6: Delegation Rules). GSD must NOT attempt specialist work itself.
- Every lead state change must be logged to `pipeline_logs` in Supabase. No silent updates.
- The voice agent (Sarah) must NEVER fabricate programme details. All information comes from PDF knowledge base in Firestore.
- Sarah must ALWAYS disclose she is an AI when asked. No exceptions.
- Treat every failed call, undelivered message, or error as a learning signal — self-anneal by fixing the component, then updating the directive.
- Do not rewrite or regenerate this file unless explicitly instructed.
- Reference the `Cloudboosta_AI_Sales_Agent_DEFINITIVE_v2.docx` as the canonical project specification.

---

## 1. The System Architecture (2-System Model)

| System | Where It Runs | What It Does | Brain |
|--------|--------------|--------------|-------|
| **System A: Text Outreach** | OpenClaw on Hostinger VPS #2 | WhatsApp messages, booking conversations, post-call follow-ups, payment emails | Gemini API |
| **System B: Voice Calls** | Cloud Run on Google Cloud | Real-time voice sales calls via Twilio | Gemini Live API via ADK |
| **Coordinator** | n8n on Hostinger VPS #1 | Orchestrates both systems — triggers outreach, schedules calls, handles post-call logic | Deterministic workflows |
| **Data Layer** | Supabase (operscale.cloud) | Leads, call logs, pipeline logs, bookings | PostgreSQL |
| **Knowledge Base** | Firestore (GCP) | Programme PDFs, FAQs, payment details, conversation sequence | Document store |

### Key Principle
System A (OpenClaw) and System B (Cloud Run/Twilio) are completely independent. They never talk to each other directly. n8n coordinates all handoffs between them.

---

## 2. The Pipeline (10 Stages)

| # | Stage | System | Directive | Description |
|---|-------|--------|-----------|-------------|
| 01 | Lead Intake | n8n + Supabase | `directives/01_lead_intake.md` | New lead from CSV/Mailerlite/Facebook → validated → stored in Supabase with status 'new' |
| 02 | Outreach | OpenClaw + n8n | `directives/02_outreach.md` | WhatsApp message + email sent to lead. Rate limited to 50/day. |
| 03 | Booking | OpenClaw | `directives/03_booking.md` | Lead replies, OpenClaw handles booking conversation, confirms time, sends to n8n |
| 04 | Call Scheduling | n8n | `directives/04_call_scheduling.md` | n8n creates scheduled trigger for booked time, sends reminder 1hr before |
| 05 | Voice Call | Cloud Run + Twilio + Gemini | `directives/05_voice_call.md` | Sarah calls via Twilio, Gemini Live API handles conversation, reads from Firestore knowledge base |
| 06 | Post-Call | n8n | `directives/06_post_call.md` | Outcome webhook received. Branch: COMMITTED → payment email. FOLLOW_UP → schedule reminder. DECLINED → close. |
| 07 | Payment Email | OpenClaw + n8n | `directives/07_payment_email.md` | Bank transfer details sent via email. WhatsApp confirmation. Reminders at 48h and 96h if no payment. |
| 08 | Admin Notification | n8n | `directives/08_admin_notification.md` | Summary email to Akinwunmi's personal email after every call with: outcome, transcript summary, recording URL |
| 09 | Monitoring | n8n | `directives/09_monitoring.md` | Health checks every 5min, stuck lead detector every 15min, daily report at 9pm |
| 10 | Enrolment | Manual + n8n | `directives/10_enrolment.md` | Payment confirmed manually (bank transfer check). Lead status → 'enrolled'. Welcome message sent. |

---

## 3. Agent Profile: Sarah

| Attribute | Value |
|-----------|-------|
| Name | Sarah |
| Voice | Neutral British English, warm and professional |
| Disclosure | Always transparent: "I'm Sarah, an AI assistant for Cloudboosta." |
| Programmes Sold | Cloud Security (£1,200) and SRE & Platform Engineering (£1,800) only |
| Other Programmes | Mentioned as "coming soon" — Cloud Foundations, Star Academy DevOps, DevSecOps |
| Internship Pitch | General: "We provide internship placement support to help you gain real-world experience." |
| Knowledge Source | PDF files in Firestore: programmes.pdf, faqs.pdf, payment-details.pdf, conversation-sequence.pdf, coming-soon.pdf |
| Calling Hours | Lead chooses their preferred time during WhatsApp booking |
| Payment Method | Bank transfer. Details sent via email after call. |

---

## 4. Data Schema (Supabase)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `leads` | Master lead record | id, name, phone, email, status, phone_country_code, recommended_programme, call_scheduled_at, lead_score, call_outcome, wave |
| `call_logs` | One entry per call attempt | lead_id, status, outcome, transcript, summary, recording_url, duration_seconds, objections_raised |
| `pipeline_logs` | Unified event log (all systems write here) | component, event_type, event_name, lead_id, message, metadata |
| `service_health` | Heartbeat tracking | service_name, status, last_heartbeat, consecutive_failures |
| `daily_metrics` | Pre-computed daily stats | date, leads_contacted, calls_made, commitments, revenue_gbp, conversion_rate |

Full SQL schemas are in `Cloudboosta_Monitoring_Logging_Dashboard_Guide.docx`, Section 1.

---

## 5. Environment Variables

```
# Google Cloud
GCP_PROJECT_ID=cloudboosta-agent
GEMINI_MODEL=gemini-2.0-flash-live

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# Supabase
SUPABASE_URL=https://supabase.operscale.cloud
SUPABASE_SERVICE_KEY=eyJxxxxxxxxxxxxxx

# n8n
N8N_BASE_URL=https://n8n.srv1297445.hstgr.cloud
N8N_WEBHOOK_SECRET=xxxxxxxx

# OpenClaw
OPENCLAW_API_URL=http://your-openclaw-ip:port
OPENCLAW_GATEWAY_TOKEN=xxxxxxxx

# Admin
ADMIN_EMAIL=your-personal-email@example.com
```

⚠️ NEVER commit `.env` to git. Add to `.gitignore` immediately.

---

## 6. GSD ↔ Agency Agent Delegation Rules

**THIS IS ENFORCED. GSD MUST NOT DO SPECIALIST WORK.**

GSD (`/gsd:plan-phase`, `/gsd:execute-phase`) handles the overall project flow: scoping, planning, verification, and milestone management. When execution reaches a specialist domain, GSD MUST spawn the appropriate Agency Agent and hand over.

### Delegation Matrix

| Task Domain | Agency Agent to Use | When GSD Hands Off |
|-------------|--------------------|--------------------|
| Python backend (FastAPI, ADK, Gemini SDK) | `@backend-architect` | Any code in `backend/` directory |
| React frontend (voice UI, dashboard) | `@frontend-developer` | Any code in `frontend/` directory |
| Docker, Cloud Run deployment, CI/CD | `@devops-engineer` | Any Dockerfile, deploy.sh, gcloud commands |
| Twilio integration (SIP, Media Streams) | `@api-developer` | Any Twilio API integration code |
| Supabase schema, queries, migrations | `@database-architect` | Any SQL or Supabase client code |
| n8n workflow design and logic | `@api-developer` | Any n8n workflow configuration |
| API security, credential management | `@security-engineer` | Any auth, secrets, or security-related code |
| Testing (unit, integration, E2E) | `@qa-engineer` | Any test files or verification scripts |
| Documentation, READMEs, guides | `@technical-writer` | Any markdown docs or user-facing text |
| UI/UX design (dashboard layout) | `@ux-designer` | Any dashboard design decisions |
| OpenClaw configuration | `@api-developer` | OpenClaw WhatsApp setup and message templates |
| Gemini prompt engineering (Sarah's persona) | `@prompt-engineer` | Voice agent system prompts and conversation design |

### Enforcement Rules

1. **Before executing any phase task**, GSD checks: "Does this task fall within a specialist domain?" If yes → spawn the Agency Agent.
2. **GSD retains oversight.** After the Agency Agent completes work, GSD verifies the output meets the phase requirements.
3. **Multiple agents per phase is normal.** A single phase might need `@backend-architect` for the Python code, `@database-architect` for the Supabase schema, and `@devops-engineer` for deployment.
4. **GSD never writes code directly** in specialist domains. GSD writes specs and requirements. Agency Agents write implementations.
5. **If no suitable Agency Agent exists**, GSD executes the task itself but flags it in the phase log: `[GSD-DIRECT] No specialist agent for: {task description}`.

### How to Invoke Agency Agents from GSD

In Claude Code, during a `/gsd:execute-phase`:
```
# GSD identifies a backend task and delegates:
"Use @backend-architect to implement the Gemini Live API WebSocket handler in backend/voice_handler.py"

# GSD identifies a database task and delegates:
"Use @database-architect to create the leads table migration in Supabase"

# GSD identifies a deployment task and delegates:
"Use @devops-engineer to write the Dockerfile and deploy.sh for Cloud Run"
```

---

## 7. Self-Annealing Loop

| Step | Action |
|------|--------|
| 1. Observe | A call fails, a message doesn't deliver, or a lead gets stuck |
| 2. Diagnose | Check `pipeline_logs` for the error. Identify which component failed. |
| 3. Fix | Apply the fix to the specific component (code, workflow, configuration) |
| 4. Confirm | Re-run the failed step. Verify it passes. |
| 5. Update Directive | Add the failure pattern and fix to the relevant `directives/` file |
| 6. Continue | Resume the pipeline. The system is now smarter. |

---

## 8. Project Directory Structure

```
cloudboosta-agent/
├── AGENT.md                    ← THIS FILE (DOE — IMMUTABLE)
├── CLAUDE.md                   ← Claude Code build instructions
├── skills.md                   ← Technical skills reference
├── skills.sh                   ← Environment validation script
├── .env                        ← Credentials (NEVER commit)
├── .gitignore
├── README.md
│
├── backend/                    ← System B: Voice Agent (Cloud Run)
│   ├── agent.py                ← ADK agent definition (Sarah)
│   ├── tools.py                ← Firestore lookup tools
│   ├── voice_handler.py        ← Gemini Live API WebSocket handler
│   ├── twilio_handler.py       ← Twilio Media Streams integration
│   ├── logger.py               ← Supabase pipeline_logs writer
│   ├── config.py               ← Environment variable loader
│   ├── main.py                 ← FastAPI server
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                   ← Browser voice UI (for testing)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── VoiceAgent.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── Dockerfile
│
├── scripts/
│   ├── seed_firestore.py       ← Knowledge base seeder
│   ├── deploy.sh               ← One-command GCP deployment
│   ├── import_leads.py         ← CSV to Supabase importer
│   └── test_call.py            ← Trigger a test call manually
│
├── knowledge-base/             ← PDF documents for Sarah
│   ├── programmes.pdf
│   ├── faqs.pdf
│   ├── payment-details.pdf
│   ├── conversation-sequence.pdf
│   └── coming-soon.pdf
│
├── directives/                 ← Build specs per pipeline stage
│   ├── 01_lead_intake.md
│   ├── 02_outreach.md
│   ├── 03_booking.md
│   ├── 04_call_scheduling.md
│   ├── 05_voice_call.md
│   ├── 06_post_call.md
│   ├── 07_payment_email.md
│   ├── 08_admin_notification.md
│   ├── 09_monitoring.md
│   └── 10_enrolment.md
│
├── docs/
│   ├── architecture.png
│   ├── Cloudboosta_AI_Sales_Agent_DEFINITIVE_v2.docx
│   ├── Cloudboosta_GCP_Voice_Agent_Build_Guide.docx
│   └── Cloudboosta_Monitoring_Logging_Dashboard_Guide.docx
│
├── .planning/                  ← GSD project state (auto-managed)
│   ├── config.json
│   ├── SPEC.md
│   ├── ROADMAP.md
│   └── phases/
│
└── docker-compose.yml          ← Local development
```

---

## 9. Build Phases (GSD Milestones)

| Phase | Description | Key Deliverables | Agency Agents Used |
|-------|-------------|------------------|--------------------|
| 1 | Prerequisites + Knowledge Base | 5 PDF docs, Paystack links, WhatsApp connected, Twilio verified, GCP project | `@technical-writer` |
| 2 | Supabase Schema + Firestore Setup | All tables + views created, Firestore seeded | `@database-architect`, `@devops-engineer` |
| 3 | Voice Agent Backend | Python ADK agent, Gemini Live API, Firestore tools, logging | `@backend-architect`, `@prompt-engineer` |
| 4 | Voice Agent Frontend | React browser UI for testing | `@frontend-developer` |
| 5 | Cloud Run Deployment | Docker, deploy.sh, service account, health check | `@devops-engineer` |
| 6 | Twilio Integration | Media Streams, outbound calling, call recording | `@backend-architect`, `@api-developer` |
| 7 | OpenClaw WhatsApp Configuration | Outreach message, booking flow, follow-up templates | `@api-developer`, `@prompt-engineer` |
| 8 | n8n Orchestration Workflows | Lead intake, outreach trigger, call scheduler, post-call handler, admin email | `@api-developer` |
| 9 | n8n Monitoring Workflows | Health check, stuck lead detector, daily report, error handler | `@api-developer`, `@devops-engineer` |
| 10 | End-to-End Testing (Wave 0) | 10 test leads through entire pipeline | `@qa-engineer` |
| 11 | Wave 1 Launch | 200 real community members | All agents on standby for fixes |

---

## 10. Test Phase Configuration

| Setting | Value |
|---------|-------|
| Test leads | 10 real community members from WhatsApp group |
| Outbound call number | Twilio free US number (+1) |
| WhatsApp number | Personal Nigerian number (via OpenClaw Web bridge) |
| Knowledge base | 5 PDF files in Firestore |
| Payment | Bank transfer (manual confirmation) |
| Admin notifications | Email to personal address |
| Call recording | Twilio automatic recording |
| Daily outreach limit | 10/day (test), 50/day (production) |

---

Read directives.
Delegate to specialists.
Run tools.
Observe results.
Improve the system.

Be pragmatic. Be reliable.

**Self-anneal.**

---

> ⚠️ **IMMUTABLE** — Do not rewrite, regenerate, summarise, or replace this file unless explicitly instructed.
> These operating rules are authoritative. Apply them strictly.
> GSD plans and coordinates. Agency Agents build. This separation is mandatory.

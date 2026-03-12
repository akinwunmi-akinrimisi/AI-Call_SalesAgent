# Roadmap: Cloudboosta AI Sales Agent

## Overview

This roadmap delivers an AI voice sales agent (Sarah) for the **Gemini Live Agent Challenge** (Devpost, deadline 2026-03-16). Category: **Live Agents** -- real-time audio interaction with natural interruption handling. The critical path for competition: Voice Agent Backend -> Browser Voice UI (with interruption handling) -> Cloud Run Deployment (Terraform IaC) -> Submission Prep (README, architecture diagram, demo video). Post-competition phases (Twilio, WhatsApp, n8n, E2E) remain for the full product launch.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

**COMPETITION CRITICAL PATH (deadline: 2026-03-16 5:00 PM PDT):**
- [x] **Phase 1: Prerequisites** - Validate all external dependencies (APIs, accounts, PDFs) before building anything
- [x] **Phase 2: Data Layer** - Deploy Supabase schema and Firestore knowledge base so every component has data to work with
- [x] **Phase 3: Voice Agent Backend** - Build Sarah (ADK agent with Gemini Live API) who can converse, qualify, recommend, and close
- [ ] **Phase 4: Browser Voice UI** - React voice interface with real-time audio, interruption handling, and audio visualization for demo
- [ ] **Phase 5: Cloud Run Deployment** - Terraform IaC deploying backend + frontend to Cloud Run with Artifact Registry, IAM, and Secret Manager
- [ ] **Phase 6: Submission Prep** - README with spin-up instructions, architecture diagram, demo video recording, Devpost submission

**POST-COMPETITION (full product launch):**
- [ ] **Phase 7: Twilio Integration** - Connect real phone calls with audio bridging, recording, and trial-aware conversation
- [ ] **Phase 8: OpenClaw WhatsApp** - Set up WhatsApp outreach and free-text booking conversation via OpenClaw
- [ ] **Phase 9: n8n Orchestration** - Wire all systems together with n8n workflows for the complete lead-to-outcome pipeline
- [ ] **Phase 10: E2E Testing** - Validate the full pipeline with 10 real leads (Wave 0)

## Phase Details

### Phase 1: Prerequisites
**Goal**: All external dependencies validated and content prepared so no downstream phase is blocked by an account issue, missing API key, or untested service
**Depends on**: Nothing (first phase)
**Requirements**: None (risk reduction phase -- enables all downstream requirements)
**Success Criteria** (what must be TRUE):
  1. Gemini API key successfully completes a live audio streaming test (not just text), confirming the model identifier works and audio flows bidirectionally
  2. All 10 Twilio test phone numbers are verified in the Twilio console and a test call connects to at least one
  3. All 5 PDF files (programmes, conversation-sequence, FAQs, payment details, objection handling) exist in knowledge-base/ and contain the expected content
  4. Environment variables for all services (Gemini, Twilio, Supabase, Firestore, Resend, OpenClaw) are documented in .env.example and populated in .env
**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md -- Fix config files, secure secrets, copy PDFs, create PDF + service validation scripts
- [x] 01-02-PLAN.md -- Validate Gemini Live API audio round-trip and Twilio credentials + phone verification

### Phase 2: Data Layer
**Goal**: Supabase schema and Firestore knowledge base are deployed and seeded so every downstream component can read/write data
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. Running the CSV import script with a test CSV creates lead records in the sales_agent.leads table with name, phone (including country code), and email fields populated
  2. Supabase sales_agent schema contains leads, call_logs, and pipeline_logs tables with correct columns and constraints, isolated from existing public schema tables
  3. Firestore collections contain parsed content from all 5 PDFs, and a test query returns relevant programme details (name, price, description)
  4. Writing a test event to pipeline_logs succeeds and the record is queryable with timestamp, event type, and lead_id
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md -- Deploy Supabase sales_agent schema, update logger.py, implement CSV lead import
- [x] 02-02-PLAN.md -- Implement and execute Firestore knowledge base seeder from 5 PDFs

### Phase 3: Voice Agent Backend
**Goal**: Sarah can hold a complete qualification conversation -- greeting with AI disclosure, qualifying the lead, recommending a programme, handling objections, asking for commitment, and producing a clear outcome
**Depends on**: Phase 2
**Requirements**: CALL-01, CALL-02, CALL-03, CALL-04, CALL-05, CALL-06, CALL-08, CALL-10
**Success Criteria** (what must be TRUE):
  1. Sarah opens every conversation by disclosing she is an AI and mentioning call recording
  2. Sarah asks qualification questions (role, experience, cloud background, motivation) and recommends either Cloud Security or SRE & Platform Engineering based on the lead's answers
  3. When a lead raises a price, time, or job outcome objection, Sarah responds with relevant information from the knowledge base PDFs rather than generic or hallucinated answers
  4. Sarah explicitly asks for commitment near the end of the call, and the system produces one of three outcomes (COMMITTED, FOLLOW_UP, DECLINED) validated against the full conversation context
  5. A duration watchdog triggers wrap-up behavior when the call approaches 8.5 minutes, and Sarah asks the lead when to follow up if the outcome is FOLLOW_UP
**Plans:** 3/3 plans executed

Plans:
- [x] 03-01-PLAN.md -- Knowledge loader, system instruction builder, ADK tools, and pytest test scaffold
- [x] 03-02-PLAN.md -- ADK Agent definition (Sarah) and call session manager with duration watchdog
- [x] 03-03-PLAN.md -- WebSocket voice handler with ADK Runner streaming and FastAPI route integration

### Phase 4: Browser Voice UI
**Goal**: A polished React voice interface that demonstrates Sarah's real-time conversational ability with natural interruption handling, audio visualization, and connection status -- ready for the competition demo video
**Depends on**: Phase 3
**Requirements**: DEPL-03, COMP-01, COMP-02
**Success Criteria** (what must be TRUE):
  1. Opening the React app in a browser and clicking "Start Call" connects to Sarah via WebSocket and a two-way voice conversation begins using the browser microphone and speakers
  2. When the user speaks while Sarah is talking, Sarah stops immediately (barge-in) and the browser stops playing buffered audio -- no overlapping speech
  3. The UI shows real-time connection status (connecting/connected/ended), call duration timer, and audio activity indicators for both user and agent
  4. The full qualification flow (greeting, questions, recommendation, objection handling, close) works end-to-end through the browser
**Plans:** 2 plans

Plans:
- [ ] 04-01-PLAN.md -- Backend modifications (transcript forwarding + REST endpoints) and frontend audio infrastructure (AudioWorklet, PCM utils, useVoiceSession hook)
- [ ] 04-02-PLAN.md -- React UI components (PreCallScreen, ActiveCallScreen, PostCallScreen), audio visualization, transcript panel, and visual verification checkpoint

### Phase 5: Cloud Run Deployment
**Goal**: Backend and frontend deployed to Cloud Run via Terraform infrastructure-as-code, providing the mandatory GCP deployment proof and IaC bonus for the competition
**Depends on**: Phase 4
**Requirements**: DEPL-01, DEPL-02, CALL-09, COMP-03, COMP-04
**Success Criteria** (what must be TRUE):
  1. `terraform apply` provisions all resources: Artifact Registry, Cloud Run services (backend + frontend), IAM service accounts, and Secret Manager secrets
  2. The Cloud Run backend responds to health check requests at /health with a 200 status code
  3. The frontend is accessible via a public Cloud Run URL and connects to the backend WebSocket endpoint
  4. Cold start time is measured and documented; if it exceeds 5 seconds, min-instances is set to 1
  5. Two simultaneous WebSocket connections both maintain independent conversations (concurrent call support)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Submission Prep
**Goal**: All competition submission artifacts are ready -- README with spin-up instructions, architecture diagram, demo video, and Devpost submission text
**Depends on**: Phase 5
**Requirements**: COMP-05, COMP-06, COMP-07, COMP-08
**Success Criteria** (what must be TRUE):
  1. README.md contains project description, tech stack, architecture diagram, local dev setup, Terraform deployment instructions, and competition context
  2. Architecture diagram (PNG/SVG in docs/) clearly shows: Browser -> WebSocket -> FastAPI -> ADK/Runner -> Gemini Live API, plus Firestore and Supabase connections
  3. Demo video (max 4 minutes) shows problem statement, live conversation with interruption, qualification flow, Cloud Run deployment proof, and architecture overview
  4. Devpost submission text is drafted with features, technologies, and learnings
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

---

**POST-COMPETITION PHASES (full product launch)**

### Phase 7: Twilio Integration
**Goal**: Sarah can make and receive real phone calls with clear audio, call recording, and proper handling of the Twilio trial message
**Depends on**: Phase 5
**Requirements**: INTG-01, CALL-07
**Success Criteria** (what must be TRUE):
  1. An outbound call initiated via Twilio connects to a verified test number, and bidirectional audio is clear with mulaw 8kHz to PCM 16kHz transcoding working correctly in both directions
  2. After the call ends, the Twilio recording URL is stored in the Supabase call_logs table and the recording is playable
  3. Sarah's opening accounts for the Twilio trial prefix so the conversation flows naturally
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

### Phase 8: OpenClaw WhatsApp
**Goal**: Leads can receive WhatsApp outreach messages and book calls through natural free-text conversation, with rate limiting to avoid account bans
**Depends on**: Phase 1 (parallelizable)
**Requirements**: INTG-02, BOOK-01, OUTR-03, OUTR-04
**Plans**: TBD

### Phase 9: n8n Orchestration
**Goal**: The complete pipeline runs automatically -- new leads trigger outreach, bookings trigger calls, outcomes trigger follow-up
**Depends on**: Phase 7, Phase 8
**Requirements**: INTG-03, OUTR-01, OUTR-02, BOOK-02, BOOK-03, POST-01, POST-02, POST-03, POST-04, POST-05
**Plans**: TBD

### Phase 10: E2E Testing
**Goal**: Full pipeline validated with 10 real community members
**Depends on**: Phase 9
**Requirements**: None (validation phase)
**Plans**: TBD

## Progress

**Competition Critical Path:** 1 -> 2 -> 3 -> 4 -> 5 -> 6 (submit by 2026-03-16)
**Post-Competition:** 7 -> 8 -> 9 -> 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Prerequisites | 2/2 | Complete | 2026-03-12 |
| 2. Data Layer | 2/2 | Complete | 2026-03-12 |
| 3. Voice Agent Backend | 3/3 | Complete | 2026-03-12 |
| 4. Browser Voice UI | 0/2 | Not started | - |
| 5. Cloud Run + Terraform | 0/2 | Not started | - |
| 6. Submission Prep | 0/2 | Not started | - |
| 7. Twilio Integration | 0/2 | Deferred | - |
| 8. OpenClaw WhatsApp | 0/0 | Deferred | - |
| 9. n8n Orchestration | 0/0 | Deferred | - |
| 10. E2E Testing | 0/0 | Deferred | - |

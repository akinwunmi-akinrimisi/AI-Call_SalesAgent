# Roadmap: Cloudboosta AI Sales Agent

## Overview

This roadmap delivers an automated AI sales pipeline for Cloudboosta in 9 phases. The critical path runs: Prerequisites (validate APIs) -> Data Layer (Supabase + Firestore) -> Voice Agent Backend (Sarah) -> Browser Voice UI (test without Twilio) -> Cloud Run Deployment (make accessible) -> Twilio Integration (real calls) -> n8n Orchestration (tie it all together) -> E2E Testing (10 real leads). OpenClaw WhatsApp (Phase 7) is independent and can be built in parallel with Phases 3-6. Every phase delivers a coherent, verifiable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Prerequisites** - Validate all external dependencies (APIs, accounts, PDFs) before building anything
- [ ] **Phase 2: Data Layer** - Deploy Supabase schema and Firestore knowledge base so every component has data to work with
- [ ] **Phase 3: Voice Agent Backend** - Build Sarah (ADK agent with Gemini Live API) who can converse, qualify, recommend, and close
- [ ] **Phase 4: Browser Voice UI** - Create a browser-based testing interface for Sarah without burning Twilio credits
- [ ] **Phase 5: Cloud Run Deployment** - Deploy the voice agent to the internet so Twilio can reach it
- [ ] **Phase 6: Twilio Integration** - Connect real phone calls with audio bridging, recording, and trial-aware conversation
- [ ] **Phase 7: OpenClaw WhatsApp** - Set up WhatsApp outreach and free-text booking conversation via OpenClaw
- [ ] **Phase 8: n8n Orchestration** - Wire all systems together with n8n workflows for the complete lead-to-outcome pipeline
- [ ] **Phase 9: E2E Testing** - Validate the full pipeline with 10 real leads (Wave 0)

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
- [ ] 01-02-PLAN.md -- Validate Gemini Live API audio round-trip and Twilio credentials + phone verification

### Phase 2: Data Layer
**Goal**: Supabase schema and Firestore knowledge base are deployed and seeded so every downstream component can read/write data
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. Running the CSV import script with a test CSV creates lead records in the sales_agent.leads table with name, phone (including country code), and email fields populated
  2. Supabase sales_agent schema contains leads, call_logs, and pipeline_logs tables with correct columns and constraints, isolated from existing public schema tables
  3. Firestore collections contain parsed content from all 5 PDFs, and a test query returns relevant programme details (name, price, description)
  4. Writing a test event to pipeline_logs succeeds and the record is queryable with timestamp, event type, and lead_id
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

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
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Browser Voice UI
**Goal**: Sarah can be tested through a web browser using microphone audio, validating conversation quality without any Twilio cost
**Depends on**: Phase 3
**Requirements**: DEPL-03
**Success Criteria** (what must be TRUE):
  1. Opening the React app in a browser and clicking "Start Call" connects to Sarah via WebSocket and a two-way voice conversation begins using the browser microphone and speakers
  2. The full qualification flow (greeting, questions, recommendation, objection handling, close) works identically in the browser as it does in backend unit tests
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Cloud Run Deployment
**Goal**: The voice agent is deployed on Cloud Run and accessible from the internet, ready for Twilio to connect to it
**Depends on**: Phase 4
**Requirements**: DEPL-01, DEPL-02, CALL-09
**Success Criteria** (what must be TRUE):
  1. The Cloud Run service responds to health check requests at /health with a 200 status code
  2. Cold start time is measured and documented; if it exceeds 5 seconds, min-instances is set to 1
  3. Two simultaneous WebSocket connections to the Cloud Run service both maintain independent conversations without interference (concurrent call support)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Twilio Integration
**Goal**: Sarah can make and receive real phone calls with clear audio, call recording, and proper handling of the Twilio trial message
**Depends on**: Phase 5
**Requirements**: INTG-01, CALL-07
**Success Criteria** (what must be TRUE):
  1. An outbound call initiated via Twilio connects to a verified test number, and bidirectional audio is clear (no static, silence, or garbled sound) with mulaw 8kHz to PCM 16kHz transcoding working correctly in both directions
  2. After the call ends, the Twilio recording URL is stored in the Supabase call_logs table and the recording is playable
  3. Sarah's opening accounts for the Twilio trial "this call is from a trial account" prefix so the conversation flows naturally despite it
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: OpenClaw WhatsApp
**Goal**: Leads can receive WhatsApp outreach messages and book calls through natural free-text conversation, with rate limiting to avoid account bans
**Depends on**: Phase 1 (parallelizable with Phases 3-6)
**Requirements**: INTG-02, BOOK-01, OUTR-03, OUTR-04
**Success Criteria** (what must be TRUE):
  1. OpenClaw is connected to the personal Nigerian WhatsApp number and can send and receive messages
  2. A test outreach message is delivered that includes a heads-up about the incoming call from a US number
  3. A lead can reply with a preferred time in free text (e.g., "Tuesday at 3pm"), OpenClaw confirms the booking naturally, and the booking data is accessible to n8n
  4. If a lead responds on both WhatsApp and email, the first response wins and the other channel receives an "already scheduled" message
  5. Message sending is rate-limited to 10 messages per day with at least 30 seconds between messages
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

### Phase 8: n8n Orchestration
**Goal**: The complete pipeline runs automatically -- new leads trigger outreach, bookings trigger reminders and calls, call outcomes trigger the correct follow-up, and admin stays informed
**Depends on**: Phase 6, Phase 7
**Requirements**: INTG-03, OUTR-01, OUTR-02, BOOK-02, BOOK-03, POST-01, POST-02, POST-03, POST-04, POST-05
**Success Criteria** (what must be TRUE):
  1. Adding a new lead to Supabase triggers both a WhatsApp outreach message (via OpenClaw) and a parallel email (via Resend API) without manual intervention
  2. One hour before a scheduled call, the lead receives a WhatsApp reminder
  3. If a lead does not answer, the system retries twice at different intervals and then sends a WhatsApp follow-up message
  4. After a call with COMMITTED outcome, the lead receives a payment details email with bank transfer instructions; after FOLLOW_UP, a follow-up call is scheduled at the lead-specified time; after DECLINED, no further contact is made but the lead is preserved in the database
  5. After every call, the admin receives a summary email with lead details, call outcome, duration, and recording URL; and committed leads who have not paid after 48 hours receive a payment reminder
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD

### Phase 9: E2E Testing
**Goal**: The complete pipeline is validated with 10 real community members, proving that leads flow from import through outreach, booking, voice call, and post-call follow-up without manual intervention
**Depends on**: Phase 8
**Requirements**: None (validation phase -- verifies all requirements end-to-end)
**Success Criteria** (what must be TRUE):
  1. A self-test call to Akinwunmi's own phone completes the full pipeline: outreach received, call booked, Sarah calls and holds a natural conversation, outcome determined, correct post-call action triggered
  2. At least 5 of the 10 test leads are processed through the pipeline with each stage logged in pipeline_logs and no leads stuck in limbo
  3. All three outcome paths (COMMITTED, FOLLOW_UP, DECLINED) have been exercised at least once with correct downstream behavior (payment email, follow-up scheduling, or graceful close)
  4. Total Twilio cost stays within the $0-15 budget constraint
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
Note: Phase 7 (OpenClaw WhatsApp) can run in parallel with Phases 3-6.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Prerequisites | 1/2 | Executing | - |
| 2. Data Layer | 0/2 | Not started | - |
| 3. Voice Agent Backend | 0/3 | Not started | - |
| 4. Browser Voice UI | 0/1 | Not started | - |
| 5. Cloud Run Deployment | 0/2 | Not started | - |
| 6. Twilio Integration | 0/2 | Not started | - |
| 7. OpenClaw WhatsApp | 0/2 | Not started | - |
| 8. n8n Orchestration | 0/3 | Not started | - |
| 9. E2E Testing | 0/2 | Not started | - |

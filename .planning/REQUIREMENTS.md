# Requirements: Cloudboosta AI Sales Agent

**Defined:** 2026-03-12
**Core Value:** Sarah (the AI voice agent) must conduct a natural qualification call, recommend the right programme, handle objections, and produce a clear outcome (COMMITTED / FOLLOW_UP / DECLINED) -- the revenue moment.

## v1 Requirements

Requirements for Wave 0 launch (10 test leads). Each maps to roadmap phases.

### Data Foundation

- [ ] **DATA-01**: Leads can be imported into Supabase via CSV with name, phone (with country code), and email
- [ ] **DATA-02**: Supabase schema deployed in isolated `sales_agent` schema with leads, call_logs, and pipeline_logs tables
- [x] **DATA-03**: Firestore knowledge base seeded from 5 PDFs (programmes, conversation-sequence, FAQs, payment details, objection handling)
- [ ] **DATA-04**: All significant pipeline actions logged to `pipeline_logs` table in Supabase

### Voice Call

- [ ] **CALL-01**: Voice agent (Sarah) calls leads via Twilio from US number, powered by Gemini Live API with real-time audio streaming
- [ ] **CALL-02**: Sarah discloses she is AI in the opening and mentions call recording
- [ ] **CALL-03**: Sarah qualifies leads using conversation-sequence PDF decision tree (role, experience, cloud background, motivation)
- [ ] **CALL-04**: Sarah recommends Cloud Security (£1,200) or SRE & Platform Engineering (£1,800) based on qualification
- [ ] **CALL-05**: Sarah handles objections using knowledge base PDFs (price, time commitment, job outcomes, beginner concerns)
- [ ] **CALL-06**: Call outcome determined by explicit commitment ask + Gemini validation against full conversation context (COMMITTED / FOLLOW_UP / DECLINED)
- [ ] **CALL-07**: Call recorded via Twilio, recording URL stored in Supabase `call_logs`
- [ ] **CALL-08**: Target call duration 5-10 minutes with duration watchdog triggering wrap-up at 8.5 minutes
- [ ] **CALL-09**: Concurrent calls supported via multiple Cloud Run instances
- [ ] **CALL-10**: Sarah asks the lead when to follow up (lead-determined follow-up timing)

### Deployment

- [ ] **DEPL-01**: Voice agent deployed as Docker container on Cloud Run with health check endpoint
- [ ] **DEPL-02**: Cold start time measured; min-instances=1 if >5 seconds
- [ ] **DEPL-03**: Browser voice UI (React) for testing Sarah without Twilio credits

### Outreach

- [ ] **OUTR-01**: n8n detects new leads and triggers WhatsApp outreach via OpenClaw
- [ ] **OUTR-02**: n8n triggers parallel email outreach via Resend API
- [ ] **OUTR-03**: WhatsApp outreach message includes heads-up about incoming US number call
- [ ] **OUTR-04**: Duplicate channel handling -- first response (WhatsApp or email) wins, other channel gets "already scheduled"

### Booking

- [ ] **BOOK-01**: OpenClaw handles free-text booking conversation (lead says a time, OpenClaw confirms naturally)
- [ ] **BOOK-02**: n8n sends 1-hour WhatsApp reminder before scheduled call
- [ ] **BOOK-03**: Retry logic -- 2 retries at different intervals if lead doesn't answer, then WhatsApp follow-up

### Post-Call

- [ ] **POST-01**: Post-call webhook to n8n triggers branching: payment email (committed), follow-up scheduling (follow_up), or close (declined)
- [ ] **POST-02**: Payment details email sent via Resend API with bank transfer instructions from PDF
- [ ] **POST-03**: Admin summary email sent after every call with lead details, outcome, duration, and recording URL
- [ ] **POST-04**: 48-hour payment reminder if committed lead hasn't paid
- [ ] **POST-05**: Declined leads preserved in database for future campaigns, no further contact in current wave

### Integration

- [ ] **INTG-01**: Twilio Media Streams WebSocket handler with bidirectional audio format transcoding (mulaw 8kHz <-> PCM 16kHz)
- [ ] **INTG-02**: OpenClaw WhatsApp connected to personal Nigerian number with rate limiting (10 messages/day for test)
- [ ] **INTG-03**: n8n orchestration workflows in separate project folder (isolated from existing workflows)

## v2 Requirements

Deferred to Wave 1 (200 leads) after core pipeline validates.

### Monitoring

- **MONR-01**: Stuck lead detection -- 15-minute cron checks for leads in limbo (no response after 48hrs, past-due calls, unpaid after 96hrs)
- **MONR-02**: Service health checks -- 5-minute cron pings Cloud Run, Supabase, OpenClaw
- **MONR-03**: Daily metrics email digest at 9pm GMT (leads contacted, calls made, commitments, conversion rate)
- **MONR-04**: 96-hour second payment reminder for committed but unpaid leads
- **MONR-05**: Rate limiting enforcement (50/day outreach cap for WhatsApp)

### Analytics

- **ANLT-01**: Objection tracking -- which objections come up most, inform PDF updates
- **ANLT-02**: Call duration tracking with alerts for too short (<2min) or too long (>15min)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Paystack payment integration | Manual bank transfer for 10 test leads. Paystack adds PCI compliance complexity. Defer to production. |
| Custom web dashboard | Supabase Studio provides table views for free. Dashboard is weeks of frontend work that doesn't validate core hypothesis. |
| WhatsApp Business API | Personal number via OpenClaw sufficient for test phase. Business API requires 2-4 week Meta approval. |
| Multi-language support | Programmes taught in English. Gemini Pidgin/Yoruba quality untested. English only. |
| Automated lead import (Mailerlite/Facebook) | CSV import takes 30 seconds for 10 leads. Automate after 200+ leads. |
| UK Twilio number | US number for test phase. UK numbers for production. |
| Voice cloning | Gemini Live API native voice is warm and professional. Cloning adds 200-500ms latency. |
| Voicemail drop | WhatsApp follow-up is more reliable and personal for 10 leads. |
| Sentiment analysis scoring | Gemini adapts tone naturally. Explicit scoring adds latency for unclear ROI. |
| Parallel/power dialing | Absurd for 10-200 leads. Sequential with smart scheduling is sufficient. |
| Call transfer to human | No human agents available. FOLLOW_UP outcome handles edge cases. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 2: Data Layer | Pending |
| DATA-02 | Phase 2: Data Layer | Pending |
| DATA-03 | Phase 2: Data Layer | Complete |
| DATA-04 | Phase 2: Data Layer | Pending |
| CALL-01 | Phase 3: Voice Agent Backend | Pending |
| CALL-02 | Phase 3: Voice Agent Backend | Pending |
| CALL-03 | Phase 3: Voice Agent Backend | Pending |
| CALL-04 | Phase 3: Voice Agent Backend | Pending |
| CALL-05 | Phase 3: Voice Agent Backend | Pending |
| CALL-06 | Phase 3: Voice Agent Backend | Pending |
| CALL-07 | Phase 6: Twilio Integration | Pending |
| CALL-08 | Phase 3: Voice Agent Backend | Pending |
| CALL-09 | Phase 5: Cloud Run Deployment | Pending |
| CALL-10 | Phase 3: Voice Agent Backend | Pending |
| DEPL-01 | Phase 5: Cloud Run Deployment | Pending |
| DEPL-02 | Phase 5: Cloud Run Deployment | Pending |
| DEPL-03 | Phase 4: Browser Voice UI | Pending |
| OUTR-01 | Phase 8: n8n Orchestration | Pending |
| OUTR-02 | Phase 8: n8n Orchestration | Pending |
| OUTR-03 | Phase 7: OpenClaw WhatsApp | Pending |
| OUTR-04 | Phase 7: OpenClaw WhatsApp | Pending |
| BOOK-01 | Phase 7: OpenClaw WhatsApp | Pending |
| BOOK-02 | Phase 8: n8n Orchestration | Pending |
| BOOK-03 | Phase 8: n8n Orchestration | Pending |
| POST-01 | Phase 8: n8n Orchestration | Pending |
| POST-02 | Phase 8: n8n Orchestration | Pending |
| POST-03 | Phase 8: n8n Orchestration | Pending |
| POST-04 | Phase 8: n8n Orchestration | Pending |
| POST-05 | Phase 8: n8n Orchestration | Pending |
| INTG-01 | Phase 6: Twilio Integration | Pending |
| INTG-02 | Phase 7: OpenClaw WhatsApp | Pending |
| INTG-03 | Phase 8: n8n Orchestration | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 after roadmap creation*

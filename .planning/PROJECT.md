# Cloudboosta AI Sales Agent

## What This Is

An automated sales pipeline for Cloudboosta that takes members from a cloud/DevOps WhatsApp community, reaches out via WhatsApp text and email, qualifies them through conversation, schedules and conducts AI voice sales calls (via Gemini Live API), and follows up with payment instructions. The system runs across two independent platforms (OpenClaw for text, Cloud Run for voice) coordinated by n8n. Everything is automated except the final bank transfer confirmation.

## Core Value

Sarah (the AI voice agent) must be able to call a lead, have a natural qualification conversation, recommend the right programme, handle objections, and produce a clear outcome (COMMITTED / FOLLOW_UP / DECLINED) — because that's the revenue moment. If nothing else works, the voice call must.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Leads can be imported into Supabase with name, phone (with country code), and email
- [ ] n8n detects new leads and triggers WhatsApp outreach via OpenClaw + email via Resend API
- [ ] WhatsApp outreach message includes heads-up about US number call
- [ ] OpenClaw handles free-text booking conversation (lead says a time, OpenClaw confirms)
- [ ] n8n sends 1-hour reminder via WhatsApp before scheduled call
- [ ] Voice agent (Sarah) calls leads via Twilio from US number, powered by Gemini Live API
- [ ] Sarah discloses she is AI in the opening and mentions call recording
- [ ] Sarah qualifies leads using conversation-sequence PDF decision tree
- [ ] Sarah recommends Cloud Security (£1,200) or SRE & Platform Engineering (£1,800) based on qualification
- [ ] Sarah handles objections using knowledge base PDFs
- [ ] Call outcome determined by explicit ask + Gemini validation of full conversation
- [ ] Call recorded via Twilio, recording URL stored in Supabase call_logs
- [ ] Post-call webhook to n8n triggers branching: payment email (committed), follow-up scheduling, or close (declined)
- [ ] Payment details email sent via Resend API with bank transfer instructions from PDF
- [ ] Admin summary email sent after every call with lead details, outcome, and recording URL
- [ ] 48-hour payment reminder if committed lead hasn't paid
- [ ] Follow-up timing determined by Sarah asking the lead during the call
- [ ] Retry logic: 2 retries at different intervals if lead doesn't answer, then WhatsApp follow-up
- [ ] Duplicate channel handling: first response (WhatsApp or email) wins, other channel gets "already scheduled"
- [ ] Declined leads preserved in database for future campaigns but no further contact now
- [ ] All significant actions logged to pipeline_logs in Supabase
- [ ] Target call duration: 5-10 minutes
- [ ] Concurrent calls supported (multiple Cloud Run instances)

### Out of Scope

- Paystack payment integration — manual bank transfer for test phase, Paystack for production
- Custom web dashboard — use Supabase Studio for monitoring during test phase
- WhatsApp Business API — personal number via OpenClaw for test phase
- Multi-language support — English only
- Automated lead import from Mailerlite/Facebook — manual CSV for test phase
- UK Twilio numbers — US number for test phase, UK numbers for production
- n8n monitoring workflows — build after core pipeline is validated
- Daily WhatsApp report to admin — email notifications sufficient for test phase

## Context

**Owner:** Akinwunmi Akinrimisi (Operscale / Cloudboosta)
**Admin email:** akinolaakinrimisi@gmail.com

**Infrastructure (all running):**
- VPS #1 (srv1297445.hstgr.cloud): n8n + Supabase self-hosted, Docker, gcloud CLI, Python 3.12, Node 18. All 5 GCP APIs enabled.
- VPS #2 (187.77.154.70): OpenClaw installed. WhatsApp NOT yet connected to personal Nigerian number.
- GCP project: vision-gridai, region us-east5. Service account active.
- Twilio: Trial account active, US number +17404943597. 10 test numbers need verification.
- Supabase: Running on VPS #1 at supabase.operscale.cloud.

**Test leads:** 10 real community members already identified. Have name, phone, and email for each.

**Key behaviors:**
- Sarah's tone and objection handling defined entirely by conversation-sequence.pdf
- Internship details come from programmes.pdf — Sarah relays what the PDF says
- Programme prices are PDF-driven — update the PDF, Sarah learns the new info
- Qualification decision tree is in conversation-sequence.pdf
- Booking is free-text (lead says a time, OpenClaw confirms naturally)
- Call outcome: Sarah explicitly asks for commitment, then Gemini validates against conversation context
- Self-test: Call Akinwunmi's own phone first before contacting real leads
- Recording consent: Sarah mentions "this call may be recorded" in opening

**Existing n8n:** Has production workflows — create a SEPARATE n8n project/folder for sales agent workflows.
**Existing Supabase:** Has other tables — create a SEPARATE 'sales_agent' schema for isolation.

**Gemini Live API key:** Exists in .env but NOT yet tested for real-time audio streaming. Needs validation early.

## Constraints

- **Twilio trial:** Can only call verified numbers. All 10 test numbers must be verified in Twilio console before launch.
- **Budget:** $0-15 total for test phase. Everything on free tiers.
- **OpenClaw WhatsApp:** Not yet connected. Must be set up before any WhatsApp outreach.
- **Gemini Live API:** Key not tested for live audio. Must validate before building voice agent.
- **Timezone:** GMT (UK) for all scheduling and reminders.
- **Email service:** Resend API for transactional emails (outreach + payment details).
- **Single Gemini key:** Shared across OpenClaw (text) and Cloud Run (voice).
- **n8n isolation:** New workflows must be in a separate project folder to avoid breaking existing workflows.
- **Supabase isolation:** New tables in a 'sales_agent' schema, not public schema.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Two-system architecture (OpenClaw + Cloud Run) | Text and voice are fundamentally different channels with different requirements. n8n bridges them. | — Pending |
| PDF-driven knowledge base | Programme details, pricing, FAQs change. PDF update = instant agent update. No code changes. | — Pending |
| Gemini Live API for voice | Real-time audio streaming needed for natural conversation. Google ADK framework. | — Pending |
| Manual bank transfer (test) | Paystack adds complexity. 10 leads can be confirmed manually. | — Pending |
| Separate Supabase schema | Isolate sales agent data from existing tables. Clean separation. | — Pending |
| Separate n8n project | Don't risk breaking existing production workflows. | — Pending |
| Resend API for email | Reliable transactional email with free tier. Better than Gmail SMTP for deliverability. | — Pending |
| GMT timezone | Programmes priced in GBP, many leads UK-based. Consistent scheduling. | — Pending |
| Recording disclosure | Sarah tells leads the call is recorded. Legal compliance. | — Pending |
| Free-text booking | Natural conversation > rigid time slots for test phase. | — Pending |

---
*Last updated: 2026-03-12 after initialization*

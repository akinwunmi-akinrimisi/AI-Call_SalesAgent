# Directive 05: Voice Call

## Stage
05 — Voice Call (THE CORE)

## System
Cloud Run + Twilio + Gemini Live API (ADK)

## What Happens
Sarah calls the lead via Twilio. Gemini Live API powers the real-time voice conversation.

### Call Flow
1. Cloud Run receives HTTP POST from n8n with lead details
2. Backend fetches lead info from Supabase
3. Backend loads knowledge base from Firestore
4. Backend tells Twilio to place outbound call from US number
5. Lead picks up → Twilio streams audio via Media Streams WebSocket
6. Cloud Run pipes audio to Gemini Live API
7. Sarah speaks

### Conversation Sequence (from conversation-sequence.pdf)
1. **Opening**: Greeting, AI disclosure, confirm availability
2. **Qualification**: Role, location, experience, cloud background, motivation
3. **Programme Recommendation**: Cloud Security (£1,200) or SRE (£1,800) based on answers
4. **Objection Handling**: Price, time, job outcomes, beginner concerns
5. **Close**: Committed → payment email. Follow-up → schedule. Declined → thank and close.

### Call Recording
Twilio records automatically. Recording URL stored in `call_logs`.

## Data Flow
1. n8n triggers call → Cloud Run
2. Cloud Run → Supabase (fetch lead) → Firestore (fetch knowledge)
3. Cloud Run → Twilio (outbound call)
4. Twilio ↔ Cloud Run (Media Streams WebSocket) ↔ Gemini Live API
5. Call ends → outcome determined (COMMITTED / FOLLOW_UP / DECLINED)
6. Cloud Run → n8n webhook with result
7. Cloud Run → Supabase (update `call_logs`)
8. Log to `pipeline_logs`: `call_started`, `call_ended`, outcome

## Critical Rules
- Sarah NEVER fabricates programme details — all info from Firestore PDFs
- Sarah ALWAYS discloses she is AI when asked
- All calls are recorded
- Call outcome must be one of: COMMITTED, FOLLOW_UP, DECLINED

## Done When
- Outbound call connects to a phone number
- Sarah speaks using Gemini Live API
- Conversation follows the sequence document
- Outcome is correctly determined and sent to n8n
- Call recording URL is stored

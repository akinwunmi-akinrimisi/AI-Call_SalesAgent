# Skills Reference
## Cloudboosta AI Sales Agent

> Technical patterns, integration specifics, and operational knowledge for every component.
> Read this before implementing. It prevents known mistakes.

**Version 1.0 | March 2026**

---

## 1. Gemini Live API — Voice Conversation Skill

### How It Works
The Gemini Live API handles bidirectional audio streaming in a single WebSocket connection.
Audio goes in (user's voice), text and audio come out (Sarah's response).
No separate STT or TTS required — Gemini does it all.

### Connection Pattern
```python
async with client.aio.live.connect(
    model='gemini-2.0-flash-live',
    config={
        'system_instruction': SARAH_SYSTEM_PROMPT,
        'tools': [lookup_programme, get_objection_response, log_call_outcome],
        'response_modalities': ['AUDIO'],
        'speech_config': {
            'voice_config': {
                'prebuilt_voice_config': {
                    'voice_name': 'Aoede'  # British English female
                }
            }
        }
    }
) as session:
    # Stream audio in both directions
```

### Known Constraints
- The exact SDK interface may change. Always check: ai.google.dev/gemini-api/docs/live
- Voice name options may be limited. Test available voices before committing.
- Session timeout: plan for calls up to 10 minutes (Cloud Run timeout = 600s).
- Audio format from browser: typically PCM 16kHz mono via MediaRecorder API.
- Audio format from Twilio: mulaw 8kHz mono — MUST be converted to PCM 16kHz before sending to Gemini.

---

## 2. Twilio Media Streams — Telephony Skill

### How It Works
Twilio places the phone call. When the lead picks up, Twilio opens a WebSocket to your
Cloud Run backend and streams the call audio in real-time.

### Outbound Call Flow
```
Your backend calls Twilio REST API: "Call +234xxxxxxxxxx"
→ Twilio rings the phone
→ Lead picks up
→ Twilio opens WebSocket to wss://your-cloud-run-url/ws/twilio/{lead_id}
→ Audio streams both directions
→ Your backend bridges Twilio audio ↔ Gemini Live API
```

### Audio Format Conversion (CRITICAL)
Twilio sends **mulaw 8kHz mono**. Gemini expects **PCM 16kHz mono**.
You MUST convert in both directions:
```
Twilio → [mulaw 8kHz → PCM 16kHz] → Gemini
Gemini → [PCM 16kHz → mulaw 8kHz] → Twilio
```
Use the `audioop` Python module or `pydub` for conversion.

### Call Recording
Enable in the Twilio API call:
```python
client.calls.create(
    to=lead_phone,
    from_=TWILIO_NUMBER,
    twiml=f'<Response><Connect><Stream url="wss://..."/></Connect></Response>',
    record=True,
    recording_status_callback='https://your-n8n/webhook/twilio-recording'
)
```
Recording URL arrives via status callback webhook.

### Known Constraints
- Trial account: can only call verified numbers. Upgrade ($20) to call any number.
- US number calling Nigerian numbers: ~$0.18/min. Budget for 10 test calls = ~$9.
- Call recording adds ~$0.0025/min to cost.
- Media Streams WebSocket sends JSON frames, not raw audio. Parse the `media.payload` field.

---

## 3. Google ADK (Agent Development Kit) — Agent Skill

### How It Works
ADK provides the framework for defining an AI agent with tools, instructions, and state.
The agent is a Python object that Gemini uses to determine behaviour.

### Agent Definition Pattern
```python
from google.adk import Agent

sales_agent = Agent(
    model='gemini-2.0-flash-live',
    name='Sarah',
    instruction=SYSTEM_INSTRUCTION,  # The full conversation sequence
    tools=[
        lookup_programme,       # Reads from Firestore
        get_objection_response, # Reads from Firestore
        get_company_info,       # Reads from Firestore
        log_call_outcome,       # Writes to Supabase
    ],
)
```

### Tool Design Rules
- Tools must have clear docstrings — Gemini uses the docstring to decide when to call the tool.
- Tools should be focused: one tool per action, not mega-tools.
- Tools that read from Firestore should cache results per-session (programme list won't change mid-call).
- The `log_call_outcome` tool should be called by Sarah at the END of the conversation, not during.

### Known Constraints
- ADK is relatively new. API may change. Pin your version in requirements.txt.
- If ADK doesn't support Gemini Live API directly, you may need to use the GenAI SDK's
  live connect method instead and wire tools manually.

---

## 4. OpenClaw — WhatsApp Integration Skill

### How It Works
OpenClaw runs on Hostinger VPS #2 in a Docker container.
It connects to your personal Nigerian WhatsApp number via the WhatsApp Web bridge.
n8n triggers OpenClaw via its API to send messages and receive responses.

### Trigger Pattern (n8n → OpenClaw)
```
n8n HTTP Request node → POST http://openclaw-ip:port/api/send
{
    "to": "+234xxxxxxxxxx",
    "message": "Hi [Name], this is Sarah from Cloudboosta..."
}
```

### Receiving Replies (OpenClaw → n8n)
Configure OpenClaw to POST incoming messages to an n8n webhook:
```
POST https://your-n8n-url/webhook/openclaw-reply
{
    "from": "+234xxxxxxxxxx",
    "message": "3pm tomorrow works",
    "timestamp": "2026-03-15T10:30:00Z"
}
```

### Known Constraints
- WhatsApp Web bridge is NOT official API. Risk of ban if you message too many people too fast.
- Rate limit: max 50 messages/day for test phase. Spread across the day.
- If your phone disconnects from the internet, OpenClaw loses WhatsApp connection.
- For production (200+ leads), migrate to WhatsApp Business API via 360dialog or Telnyx.

---

## 5. n8n Orchestration — Workflow Skill

### Workflow Naming Convention
```
CB-01-Lead-Intake
CB-02-Outreach-Trigger
CB-03-Booking-Handler
CB-04-Call-Scheduler
CB-05-Call-Trigger
CB-06-Post-Call-Handler
CB-07-Payment-Email
CB-08-Admin-Notification
CB-09-Health-Check
CB-10-Stuck-Lead-Detector
CB-11-Daily-Report
CB-12-Error-Handler
CB-13-CSV-Importer
```

### Error Handling Pattern
Every workflow must have:
1. An Error Trigger node that catches any node failure
2. A Supabase insert to `pipeline_logs` with event_type='error'
3. A notification (email or WhatsApp) for critical errors

### Webhook Security
All n8n webhooks should use a secret header:
```
Header: x-webhook-secret: {N8N_WEBHOOK_SECRET}
```
Validate this in the first node of every webhook workflow.

---

## 6. Supabase — Database Skill

### Connection Pattern (Python)
```python
from supabase import create_client
import os

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)
```

### Lead Status Transitions (Valid Paths)
```
new → outreach_pending → outreach_sent → replied → call_scheduled
    → call_in_progress → call_completed → committed → payment_pending → enrolled
                                        → follow_up → (back to call_scheduled)
                                        → declined
    → outreach_failed → unreachable
    → call_failed → (retry → call_scheduled)
    → call_no_answer → (retry → call_scheduled, max 3)
    → do_not_contact
```

### Known Constraints
- Always use service key (not anon key) for backend operations.
- Row Level Security (RLS): disabled for backend writes, but enable for any future dashboard.
- Supabase realtime: enable on `pipeline_logs` table for future dashboard live updates.

---

## 7. Firestore — Knowledge Base Skill

### Document Structure
```
Firestore Database
├── programmes/
│   ├── cloud-security         {name, duration, price_gbp, price_ngn, ...}
│   └── sre-platform           {name, duration, price_gbp, price_ngn, ...}
├── objections/
│   ├── too-expensive           {trigger_phrases, response}
│   ├── no-time                 {trigger_phrases, response}
│   ├── job-guarantee           {trigger_phrases, response}
│   ├── think-about-it          {trigger_phrases, response}
│   └── beginner-worry          {trigger_phrases, response}
├── company/
│   └── about                   {name, tagline, key_differentiator, ...}
└── pdf_content/
    ├── programmes              {extracted text from programmes.pdf}
    ├── faqs                    {extracted text from faqs.pdf}
    ├── payment-details         {extracted text from payment-details.pdf}
    ├── conversation-sequence   {extracted text from conversation-sequence.pdf}
    └── coming-soon             {extracted text from coming-soon.pdf}
```

### PDF Upload Pattern
Extract text from PDFs and store in Firestore. Sarah reads the text, not the raw PDF:
```python
import fitz  # PyMuPDF
doc = fitz.open("programmes.pdf")
text = ""
for page in doc:
    text += page.get_text()
db.collection('pdf_content').document('programmes').set({'text': text})
```

---

## 8. Cloud Run Deployment — Deployment Skill

### Deploy Command (One-Liner)
```bash
cd backend && \
gcloud builds submit --tag europe-west1-docker.pkg.dev/cloudboosta-agent/cloudboosta-repo/agent-backend && \
gcloud run deploy cloudboosta-agent-backend \
  --image europe-west1-docker.pkg.dev/cloudboosta-agent/cloudboosta-repo/agent-backend \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account cloudboosta-agent-sa@cloudboosta-agent.iam.gserviceaccount.com \
  --memory 512Mi --cpu 1 --timeout 600 \
  --min-instances 0 --max-instances 5 \
  --set-env-vars GCP_PROJECT_ID=cloudboosta-agent
```

### Known Constraints
- Cloud Run cold start: first request after scale-to-zero takes 2-5 seconds.
  For scheduled calls, consider --min-instances 1 during active calling hours.
- WebSocket connections on Cloud Run require --timeout to be set high enough for the call duration.
- Max request timeout is 3600s (1 hour). Calls should never exceed 10 minutes.

---

## Known Gotchas + Lessons Learned

| Gotcha | Fix |
|--------|-----|
| Twilio sends mulaw, Gemini expects PCM | Convert audio format in both directions |
| Cloud Run cold start delays first call | Set --min-instances 1 during calling hours |
| OpenClaw WhatsApp disconnects when phone sleeps | Keep phone plugged in and connected to WiFi 24/7 |
| Firestore reads add latency to voice calls | Cache programme data at session start, not per-query |
| n8n webhook fails silently if no error handler | ALWAYS add Error Trigger node to every workflow |
| Lead booked on both WhatsApp and email | Check Supabase status before creating any booking |
| Sarah fabricates pricing | NEVER put pricing in the system prompt. Always use tool to read from Firestore |
| Twilio trial only calls verified numbers | Verify all 10 test numbers before Wave 0 |
| GSD tries to write code instead of delegating | Check AGENT.md Section 6. Delegation is mandatory, not optional. |

---

## Project Directory Quick Reference
```
backend/           → System B: Voice agent code (Cloud Run)
frontend/          → Browser voice UI for testing
scripts/           → Deployment and utility scripts
knowledge-base/    → 5 PDF documents for Sarah
directives/        → Per-stage build specifications
docs/              → Reference documents (.docx files)
.planning/         → GSD project state (auto-managed)
.env               → Credentials (NEVER commit)
AGENT.md           → DOE operating rules (IMMUTABLE)
CLAUDE.md          → Claude Code instructions (THIS PROJECT)
skills.md          → THIS FILE — technical patterns
skills.sh          → Environment validation
```

# Architecture Patterns

**Domain:** AI Voice Sales Agent Pipeline (WhatsApp + Voice + Orchestration)
**Researched:** 2026-03-12
**Confidence:** HIGH (architecture defined in AGENT.md, patterns verified against current Gemini Live API and Twilio docs)

---

## Recommended Architecture

### The 2-System + Coordinator Model

This project uses a **hub-and-spoke architecture** where n8n is the deterministic hub and two independent AI systems (text + voice) are spokes. This is the correct pattern for this domain because text-based outreach and real-time voice conversations have fundamentally different runtime requirements, latency profiles, and failure modes.

```
                         +------------------+
                         |    DATA LAYER    |
                         |  Supabase (PG)   |
                         |  sales_agent.*   |
                         +--------+---------+
                                  |
              reads/writes        |        reads/writes
         +------------------------+------------------------+
         |                        |                        |
+--------v---------+    +---------v--------+    +----------v---------+
|  SYSTEM A: TEXT   |    |   COORDINATOR    |    |  SYSTEM B: VOICE   |
|  OpenClaw (VPS2)  |    |   n8n (VPS1)     |    |  Cloud Run (GCP)   |
|                   |    |                  |    |                    |
| - WhatsApp msgs   |<-->| - Lead intake    |<-->| - Twilio calls     |
| - Booking convos  |    | - Outreach trig  |    | - Gemini Live API  |
| - Follow-ups      |    | - Call scheduler |    | - ADK agent(Sarah) |
| - Brain: Gemini   |    | - Post-call flow |    | - Firestore KB     |
|                   |    | - Admin emails   |    | - Call recording    |
+-------------------+    | - Monitoring     |    +--------------------+
                         +------------------+

                         +------------------+
                         |  KNOWLEDGE BASE  |
                         |  Firestore (GCP) |
                         | - programmes.pdf |
                         | - faqs.pdf       |
                         | - payment.pdf    |
                         | - convo-seq.pdf  |
                         +------------------+
```

### Why This Structure (Not a Monolith)

1. **Different runtimes:** WhatsApp text = async HTTP. Voice = persistent WebSocket with real-time audio streaming at 8kHz. Mixing these in one service creates scaling and failure coupling.
2. **Different scaling:** Voice calls need dedicated CPU per active call (audio encoding/decoding). Text can handle thousands of concurrent conversations per instance.
3. **Independent failure:** If OpenClaw goes down, voice calls still work. If Cloud Run has issues, WhatsApp outreach continues. n8n retries failed handoffs.
4. **Different deployment:** OpenClaw is a pre-built platform (configure, don't code). Cloud Run is custom Python. Shipping cycles are independent.

---

## Component Boundaries

| Component | Responsibility | Talks To | Protocol | Deployment |
|-----------|---------------|----------|----------|------------|
| **n8n** (Coordinator) | Orchestrates entire pipeline. Triggers outreach, schedules calls, handles post-call branching, sends admin emails, runs monitoring. NO AI logic. | Supabase, OpenClaw, Cloud Run, Resend API | HTTP webhooks, REST APIs | Docker on VPS #1 |
| **OpenClaw** (System A) | WhatsApp messaging. Handles outreach messages, free-text booking conversations, post-call follow-ups. | Gemini API (brain), n8n (webhooks) | WhatsApp Web bridge, HTTP | Pre-built on VPS #2 |
| **Cloud Run** (System B) | Voice agent runtime. FastAPI server handles Twilio webhooks, opens Gemini Live API sessions, bridges audio between Twilio and Gemini. | Twilio (audio), Gemini Live API (brain), Firestore (knowledge), Supabase (logging) | WebSocket (Twilio Media Streams + Gemini Live), HTTP | Docker on GCP Cloud Run |
| **Supabase** | Persistent state. Leads, call logs, pipeline logs, service health, daily metrics. Single source of truth for lead status. | All components read/write | PostgreSQL REST API | Docker on VPS #1 |
| **Firestore** | Knowledge base. PDF content indexed for Sarah's runtime retrieval. Immutable during calls. | Cloud Run reads at call time | Firestore SDK | GCP managed |
| **Twilio** | Telephony. Makes outbound calls, streams audio via Media Streams WebSocket, records calls. | Cloud Run (webhooks + WebSocket) | SIP/PSTN, WebSocket, REST | Twilio cloud (managed) |
| **Resend API** | Transactional email. Outreach emails, payment detail emails, admin summaries. | n8n triggers sends | REST API | Resend cloud (managed) |

### Strict Boundary Rules

- **n8n never processes AI logic.** It is purely deterministic: if/else, webhook triggers, HTTP requests, timers.
- **OpenClaw and Cloud Run never communicate directly.** All coordination goes through n8n.
- **Supabase is the single source of truth for lead state.** Every component reads lead status from Supabase before acting.
- **Firestore is read-only at runtime.** Knowledge base is seeded once during setup, updated only by admin.

---

## Data Flow

### Primary Pipeline Flow (Happy Path)

```
1. LEAD INTAKE
   CSV/manual --> n8n webhook --> validate --> Supabase leads (status: 'new')
                                              pipeline_logs: "lead_created"

2. OUTREACH
   n8n detects new lead --> triggers OpenClaw WhatsApp message
                        --> triggers Resend email
                        --> Supabase leads (status: 'contacted')
                           pipeline_logs: "outreach_sent"

3. BOOKING
   Lead replies on WhatsApp --> OpenClaw handles conversation (Gemini brain)
                            --> Lead says a time --> OpenClaw confirms
                            --> Webhook to n8n with booking time
                            --> Supabase leads (status: 'booked', call_scheduled_at: <time>)
                               pipeline_logs: "call_booked"

4. CALL SCHEDULING
   n8n scheduled trigger at booked time minus 1hr --> WhatsApp reminder via OpenClaw
   n8n scheduled trigger at booked time --> HTTP POST to Cloud Run /initiate-call
                                           pipeline_logs: "call_triggered"

5. VOICE CALL (the revenue moment)
   Cloud Run receives call trigger
   --> Twilio REST API: create outbound call to lead's phone
   --> Twilio connects, opens Media Stream WebSocket to Cloud Run
   --> Cloud Run opens Gemini Live API WebSocket session
   --> AUDIO BRIDGE: Twilio <--mulaw 8kHz--> Cloud Run <--PCM--> Gemini Live API
   --> Sarah converses using knowledge from Firestore
   --> Call ends --> outcome determined (COMMITTED/FOLLOW_UP/DECLINED)
   --> Supabase call_logs: full record
   --> Supabase leads: (status: 'called', call_outcome: <outcome>)
   --> Webhook POST to n8n with outcome
      pipeline_logs: "call_completed"

6. POST-CALL BRANCHING (n8n)
   COMMITTED --> Resend: payment email with bank details
             --> Supabase leads (status: 'committed')
             --> n8n schedules 48hr payment reminder
   FOLLOW_UP --> n8n schedules follow-up at time Sarah asked for
             --> Supabase leads (status: 'follow_up')
   DECLINED  --> Supabase leads (status: 'declined')
             --> No further contact
   ALL OUTCOMES --> Resend: admin summary email
                   pipeline_logs: "post_call_<outcome>"

7. ENROLMENT (manual)
   Admin confirms bank transfer --> manual status update
   --> Supabase leads (status: 'enrolled')
   --> n8n triggers welcome message via OpenClaw
```

### The Voice Call Audio Bridge (Critical Path Detail)

This is the most technically complex component. The Cloud Run server must bridge two concurrent WebSocket connections in real time:

```
Lead's Phone
    |
    | (PSTN call)
    v
Twilio
    |
    | WebSocket: Media Streams
    | Format: G.711 mulaw, 8kHz, base64 encoded
    v
Cloud Run (FastAPI + WebSocket handler)
    |
    | 1. Receive mulaw audio from Twilio
    | 2. Decode base64 --> raw mulaw bytes
    | 3. Convert mulaw 8kHz --> PCM 16kHz (if needed by Gemini)
    | 4. Forward to Gemini Live API
    | 5. Receive audio response from Gemini
    | 6. Convert PCM --> mulaw 8kHz
    | 7. Base64 encode --> send to Twilio
    |
    | WebSocket: Gemini Live API session
    | Format: PCM audio
    v
Gemini Live API
    |
    | Session includes:
    | - System instruction (Sarah's persona)
    | - Tools (Firestore lookup functions)
    | - Conversation context
    v
Firestore Knowledge Base
```

**Latency budget:** Total round-trip must stay under ~500ms for natural conversation. Gemini Live API is optimized for this. The main risk is audio format conversion overhead on Cloud Run.

### ADK's Role in the Voice Stack

Google's Agent Development Kit (ADK) provides the high-level framework that eliminates manual WebSocket session management, tool orchestration, and state persistence. Using ADK with the Gemini Live API Toolkit:

- **Agent definition** (`agent.py`): Declares Sarah's persona via `system_instruction`, registers Firestore lookup tools, sets model to `gemini-2.0-flash-live`.
- **Tool execution**: ADK automatically handles function calling -- when Sarah needs programme details, Gemini issues a tool call, ADK executes the Firestore lookup, returns results to the conversation.
- **Session management**: ADK handles WebSocket reconnection, barge-in (user interrupts Sarah), and conversation state.
- **Audio streaming**: ADK's streaming module handles the bidirectional audio pipe, though Twilio Media Streams integration requires custom bridging code in `voice_handler.py`.

**Key insight:** ADK handles the Gemini side cleanly. The custom code is primarily the Twilio-to-Gemini bridge (`voice_handler.py` + `twilio_handler.py`).

---

## Patterns to Follow

### Pattern 1: Event-Sourced Pipeline Logging

**What:** Every state change writes to `pipeline_logs` before updating the lead record. This creates an audit trail and enables debugging.

**When:** Every component, every action.

**Example:**
```python
# In Cloud Run backend
async def complete_call(lead_id: str, outcome: str):
    # 1. Log the event FIRST
    await log_event(
        component="voice_agent",
        event_type="call_completed",
        lead_id=lead_id,
        message=f"Call completed with outcome: {outcome}",
        metadata={"duration": duration, "objections": objections}
    )
    # 2. THEN update lead status
    await supabase.table("leads").update({"call_outcome": outcome, "status": "called"}).eq("id", lead_id).execute()
```

### Pattern 2: Webhook-Driven Handoffs

**What:** All cross-system communication uses HTTP webhooks with JSON payloads. No polling. No shared queues.

**When:** Every handoff between n8n, OpenClaw, and Cloud Run.

**Why:** n8n is built around webhooks. This keeps the architecture simple and debuggable (every handoff is a logged HTTP request).

```
OpenClaw booking complete --> POST n8n/webhook/booking-confirmed { lead_id, scheduled_time }
Cloud Run call complete   --> POST n8n/webhook/call-completed { lead_id, outcome, summary }
n8n trigger call          --> POST cloud-run/initiate-call { lead_id, phone }
```

### Pattern 3: Idempotent Operations with Lead Status Guards

**What:** Before performing any action, check the lead's current status. Prevent duplicate outreach, duplicate calls, or post-call actions on the wrong lead state.

**When:** Every n8n workflow node that modifies lead state.

**Example:**
```
n8n node: "Check lead status"
  --> GET Supabase leads WHERE id = lead_id
  --> IF status != 'booked' THEN skip (already processed or wrong state)
  --> IF status == 'booked' THEN proceed with call
```

### Pattern 4: Retry with Escalation

**What:** Failed operations retry with increasing intervals, then escalate to a different channel.

**When:** Unanswered calls, undelivered messages.

**Example for calls:**
```
Attempt 1: Call at scheduled time
  --> No answer --> wait 30 min
Attempt 2: Call again
  --> No answer --> wait 2 hours
Attempt 3: Call again
  --> No answer --> Send WhatsApp: "We tried to reach you..."
  --> Update lead status to 'no_answer'
  --> pipeline_logs: "call_retries_exhausted"
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct System-to-System Communication

**What:** OpenClaw calling Cloud Run directly, or Cloud Run sending WhatsApp messages directly.

**Why bad:** Creates hidden coupling. When one system changes, the other breaks. n8n loses visibility into the pipeline. Debugging becomes impossible because you can't see the handoff in n8n's execution log.

**Instead:** All cross-system communication goes through n8n webhooks. Even if it adds a hop, the observability is worth it.

### Anti-Pattern 2: Hardcoding Knowledge in Agent Code

**What:** Putting programme prices, FAQ answers, or conversation scripts directly in `agent.py` or system prompts.

**Why bad:** Every content change requires a code deploy. The whole point of the PDF-driven knowledge base is that admins can update a PDF and Sarah immediately knows the new info.

**Instead:** Sarah's system instruction says "look up programme details using your tools." Firestore tools return current PDF content at runtime.

### Anti-Pattern 3: Synchronous Call Initiation

**What:** n8n waits for the entire voice call to complete before proceeding.

**Why bad:** Calls last 5-10 minutes. n8n workflow would timeout. Blocks the workflow executor.

**Instead:** n8n sends an async POST to Cloud Run to initiate the call, then exits. Cloud Run sends a webhook back to n8n when the call completes. This is the standard pattern for long-running telephony operations.

### Anti-Pattern 4: Shared Gemini Session Across Calls

**What:** Reusing a single Gemini Live API session for multiple concurrent calls.

**Why bad:** Conversation context bleeds between calls. Sarah would reference details from a previous lead's call.

**Instead:** Each call gets its own Gemini Live API session. Session is created when the call connects and destroyed when the call ends. Cloud Run handles concurrency by running multiple instances.

---

## Scalability Considerations

| Concern | 10 leads (test) | 200 leads (Wave 1) | 1,000+ leads (production) |
|---------|-----------------|---------------------|---------------------------|
| **Concurrent calls** | 1 at a time | 2-3 concurrent max | Cloud Run auto-scaling, 10+ concurrent |
| **Outreach rate** | 10/day | 50/day (rate limited) | Need WhatsApp Business API |
| **Supabase load** | Negligible | Low (200 rows) | Consider connection pooling |
| **Gemini API quota** | Well within free tier | Monitor usage, single key shared | Separate keys per system, quota alerts |
| **n8n execution** | Low | Medium (200 workflow runs) | May need workflow optimization |
| **Twilio costs** | Free trial | ~$20-50/month | Volume discounts needed |
| **OpenClaw** | Personal number OK | Personal number risky at scale | WhatsApp Business API required |

---

## Suggested Build Order (Dependency Chain)

Build order is driven by dependencies. You cannot test downstream components without upstream ones being ready.

```
LAYER 1: Foundation (no dependencies)
  [Phase 1] Prerequisites: PDFs, accounts, API keys
  [Phase 2] Supabase schema + Firestore seed

  These are independent and could be done in parallel.
  Everything else depends on these.

LAYER 2: The Revenue Core (depends on Layer 1)
  [Phase 3] Voice agent backend (Python/ADK/Gemini)

  This is the highest-risk, most complex component.
  Build it early so problems surface early.
  Depends on: Firestore (knowledge base), Supabase (logging)

LAYER 3: Voice Testing & Deployment (depends on Layer 2)
  [Phase 4] Browser voice UI (for testing without Twilio)
  [Phase 5] Cloud Run deployment
  [Phase 6] Twilio integration

  Phase 4 lets you test the voice agent without Twilio costs.
  Phase 5 deploys it. Phase 6 connects real phone calls.
  These are sequential: 4 --> 5 --> 6.

LAYER 4: Text Channel (depends on Layer 1 only)
  [Phase 7] OpenClaw WhatsApp configuration

  Independent of voice. Can be built in parallel with Layer 2/3.
  But testing the full pipeline requires both text and voice.

LAYER 5: Orchestration (depends on Layers 2-4)
  [Phase 8] n8n orchestration workflows

  n8n ties everything together. It needs all components
  to be at least partially functional to test handoffs.

LAYER 6: Observability (depends on Layer 5)
  [Phase 9] n8n monitoring workflows

  Monitoring is only useful once the pipeline runs.

LAYER 7: Validation (depends on everything)
  [Phase 10] E2E testing with 10 real leads
  [Phase 11] Wave 1 launch with 200 leads
```

### Critical Path

The critical path is: **Foundation --> Voice Backend --> Cloud Run Deploy --> Twilio Integration --> n8n Orchestration --> E2E Testing**

OpenClaw (Phase 7) is on the non-critical path and can be developed in parallel with the voice stack, but must be ready before E2E testing.

### Highest Risk Component

**The Twilio-to-Gemini audio bridge** (`voice_handler.py` + `twilio_handler.py`) is the highest risk component because:
- Real-time audio format conversion (mulaw 8kHz <-> PCM)
- Dual concurrent WebSocket management
- Latency sensitivity (~500ms budget)
- Gemini Live API is relatively new (launched late 2024/early 2025)
- ADK streaming toolkit simplifies the Gemini side but Twilio bridging is custom code

**Mitigation:** Build Phase 3 early. Test with the browser UI (Phase 4) before adding Twilio complexity. Validate Gemini Live API key works for audio streaming as the very first technical task.

---

## Sources

- [ADK Gemini Live API Toolkit - Official Docs](https://google.github.io/adk-docs/streaming/) - HIGH confidence
- [Build a real-time voice agent with Gemini & ADK - Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/build-a-real-time-voice-agent-with-gemini-adk) - HIGH confidence
- [Part 1: Intro to ADK Streaming](https://google.github.io/adk-docs/streaming/dev-guide/part1/) - HIGH confidence
- [Building an AI IVA with Gemini Multimodal Live & Twilio](https://thoughts.ckbrox.com/building-an-ai-interactive-voice-agent-iva-with-gemini-multimodal-live-and-twilio/) - MEDIUM confidence
- [Twilio Media Streams Overview](https://www.twilio.com/docs/voice/media-streams) - HIGH confidence
- [Twilio Media Streams WebSocket Messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) - HIGH confidence
- [Gemini Live API Overview - Google AI](https://ai.google.dev/gemini-api/docs/live-api) - HIGH confidence
- [Building a Telephone Voice Agent with FreeSWITCH and ADK](https://medium.com/google-cloud/gemini-live-part-1-building-a-low-latency-telephone-voice-agent-with-freeswitch-and-adk-agents-ceafd209f017) - MEDIUM confidence
- [AI Voice Agents in 2025: A Comprehensive Guide](https://dev.to/kaymen99/ai-voice-agents-in-2025-a-comprehensive-guide-3kl) - MEDIUM confidence
- [Outbound calls with Python, OpenAI Realtime API, and Twilio Voice](https://www.twilio.com/en-us/blog/outbound-calls-python-openai-realtime-api-voice) - MEDIUM confidence (different LLM but same Twilio pattern)

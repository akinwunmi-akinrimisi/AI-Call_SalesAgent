# Project Research Summary

**Project:** Cloudboosta AI Sales Agent
**Domain:** AI Voice Sales Agent with Multi-Channel Outreach Pipeline
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

The Cloudboosta AI Sales Agent is an automated sales pipeline that converts WhatsApp community members into enrolled cloud/DevOps training students. It operates as a two-system architecture -- text outreach via OpenClaw (WhatsApp + Gemini) on a Hostinger VPS and voice sales calls via Gemini Live API on Google Cloud Run -- coordinated by a deterministic n8n orchestrator. Experts build systems like this using a hub-and-spoke pattern where each channel (text, voice) is an independent spoke and the orchestrator is the only bridge. This isolation ensures that a failure in one system does not cascade to the other, which is critical when real leads and revenue are at stake.

The recommended approach is to build the voice agent first (highest risk, highest value), validate it in a browser before connecting Twilio, then layer on WhatsApp outreach and n8n orchestration. The core stack -- Python 3.12, FastAPI, google-genai SDK, Google ADK, Twilio Media Streams -- is mature and well-documented. The critical custom code is the audio bridge that converts Twilio's mulaw 8kHz audio to Gemini's PCM 16kHz format in real time on every audio chunk, bidirectionally. This is the single most technically challenging piece and where most integration failures will occur.

Five critical risks threaten the pipeline: (1) audio format mismatch between Twilio and Gemini causing garbled or silent calls, (2) Gemini Live API model deprecation on a one-week timeline requiring immediate model identifier verification, (3) n8n self-hosted webhooks silently failing while returning 200 OK -- causing leads to fall through the cracks invisibly, (4) WhatsApp account bans when using OpenClaw's unofficial API at scale, and (5) Twilio trial account imposing a hard 10-minute call limit that exactly matches the target call duration. The $0-15 budget is the binding constraint: it forces acceptance of the Twilio trial (with its "trial account" message prefix and 10-minute cutoff), Cloud Run scale-to-zero (with cold start risk), and OpenClaw personal number (with ban risk). Upgrading Twilio alone to a paid account ($20-30) would eliminate the most user-facing quality issues and is the strongest single-investment recommendation from this research.

## Key Findings

### Recommended Stack

The stack is GCP-native by design. All core technologies have been verified against current official sources and are production-ready. The key insight is to use the `google-genai` unified SDK (not the deprecated `google-generativeai` package) and Twilio Media Streams (not ConversationRelay, which would add an unnecessary text intermediary and defeat Gemini Live API's native audio-to-audio streaming).

**Core technologies:**
- **Python 3.12 + FastAPI 0.135.x**: Runtime and HTTP/WebSocket server. Async-first, native WebSocket support required for concurrent Twilio + Gemini streams. No alternatives come close.
- **google-genai SDK + Google ADK 1.26.x**: Gemini Live API client and agent framework. ADK handles tool registration, session management, and conversation state. The only supported SDK for Gemini Live API.
- **Twilio Media Streams**: Bidirectional raw audio streaming via WebSocket. Chosen over ConversationRelay because Gemini Live API operates audio-to-audio natively -- inserting a text step would add latency and complexity for no benefit.
- **Supabase (self-hosted PostgreSQL)**: Transactional data store for leads, call logs, pipeline logs. Already deployed. Schema isolation via `sales_agent` schema.
- **Firestore (GCP managed)**: Knowledge base document store. PDFs parsed and seeded into collections. Read-only at call runtime. Separate concern from transactional data.
- **n8n (self-hosted)**: Deterministic workflow orchestrator. Bridges text and voice systems. No AI logic -- purely if/else, webhooks, timers.
- **OpenClaw (VPS #2)**: WhatsApp messaging via personal number. Handles outreach and booking conversations. Brain is Gemini API (text mode).
- **Resend API**: Transactional email for outreach, payment details, admin notifications. Free tier sufficient.

**Critical version notes:**
- Model `gemini-live-2.5-flash-preview-native-audio-09-2025` is being deprecated March 19, 2026. Migrate to `gemini-live-2.5-flash-native-audio`.
- Gemini Live API sessions max out at 10 minutes. Target call duration is 5-10 minutes, right at the boundary. Implement session watchdog.
- Twilio audio is mulaw 8kHz; Gemini expects PCM 16kHz. Bidirectional real-time transcoding is mandatory.

### Expected Features

**Must have (table stakes for Wave 0 -- 10 test leads):**
- Natural voice conversation with sub-300ms response target (Gemini Live API handles this natively; the WebSocket pipe is the latency risk)
- AI disclosure at call opening (legal compliance)
- Call recording with URL storage (QA and evidence)
- Knowledge-base-driven responses with no hallucination (PDF-to-Firestore pipeline)
- Qualification-driven programme recommendation (Cloud Security vs. SRE based on lead fit)
- Objection handling from conversation-sequence.pdf
- Explicit commitment ask with full-context outcome validation (COMMITTED / FOLLOW_UP / DECLINED)
- Multi-channel outreach (WhatsApp + email) with duplicate channel handling
- WhatsApp heads-up about US phone number (critical for answer rates with +1 number)
- Conversational booking via free-text WhatsApp (no slot picker UI)
- Call scheduling with 1-hour WhatsApp reminder
- Retry logic (2 retries at varied intervals, then WhatsApp fallback)
- Post-call automation (payment email for committed, follow-up scheduling, admin summary)
- Comprehensive event logging to pipeline_logs

**Should have (competitive differentiators):**
- PDF-driven hot-swappable knowledge base (non-technical admin updates a PDF, Sarah learns immediately)
- Lead-determined follow-up timing (Sarah asks the lead when to follow up)
- Full pipeline observability with stuck lead detection (15-minute cron)
- Daily metrics email digest at 9pm GMT
- Wave-based lead management (controlled rollout batches)
- Outcome validation via full conversation context (distinguishes social politeness from genuine commitment)

**Defer to v2+:**
- Paystack payment integration (manual bank transfer is fine for 10 leads)
- Custom web dashboard (use Supabase Studio during test phase)
- WhatsApp Business API (personal number acceptable for test; required for 200+ leads)
- Automated lead import from Mailerlite/Facebook (CSV import takes 30 seconds)
- Multi-language support, voice cloning, parallel dialing, sentiment analysis

### Architecture Approach

The system uses a hub-and-spoke architecture with n8n as the deterministic hub and two independent AI systems as spokes. Text (OpenClaw on VPS #2) and voice (Cloud Run on GCP) never communicate directly -- all coordination flows through n8n webhooks. Supabase is the single source of truth for lead state. Firestore is read-only at runtime for knowledge base content.

**Major components:**
1. **n8n (Coordinator)** -- Orchestrates pipeline: triggers outreach, schedules calls, handles post-call branching, sends admin emails, runs monitoring. Zero AI logic.
2. **Cloud Run (Voice System)** -- FastAPI server bridging Twilio Media Streams WebSocket and Gemini Live API WebSocket. ADK agent (Sarah) with Firestore tools. The revenue-critical component.
3. **OpenClaw (Text System)** -- WhatsApp outreach, booking conversations, follow-ups. Gemini API as brain (text mode). Pre-built platform, configure not code.
4. **Supabase (Data Layer)** -- PostgreSQL for leads, call_logs, pipeline_logs, service_health. All components read/write. Atomic status checks prevent race conditions.
5. **Firestore (Knowledge Base)** -- Parsed PDF content: programmes, FAQs, payment details, conversation sequence. Immutable during calls.
6. **Twilio (Telephony)** -- Outbound calling, Media Streams for raw audio, call recording. Managed service.
7. **Resend (Email)** -- Transactional email triggered by n8n. Managed service.

**Key patterns:**
- Event-sourced pipeline logging (log before state change)
- Webhook-driven handoffs (all cross-system communication via HTTP webhooks through n8n)
- Idempotent operations with lead status guards (check state before acting)
- Retry with escalation (call retries then channel-switch to WhatsApp)
- Dead-letter pattern for n8n webhook resilience (Cloud Run writes to Supabase directly as fallback)

### Critical Pitfalls

1. **Audio format mismatch (Twilio mulaw 8kHz vs Gemini PCM 16kHz)** -- Build the transcoding layer as an isolated, unit-tested module before integrating Twilio with Gemini. Browser tests will pass while Twilio calls produce silence or static if this is wrong.
2. **Gemini Live API model deprecation** -- Pin model version in config (not hardcoded in agent logic). Verify the current model identifier at Phase 3 start, not at research time. Audio quality regressions have been reported post-March 9, 2026.
3. **n8n webhook silent failures** -- Webhooks randomly stop executing while returning 200 OK. Implement dead-letter pattern: Cloud Run writes critical data to Supabase directly, n8n cron scans for unprocessed events. Self-ping health check every 5 minutes.
4. **WhatsApp account ban via OpenClaw** -- Rate-limit to 10 messages/day for test phase, vary message content, space messages 30+ seconds apart. Have a backup phone number ready. Plan WhatsApp Business API migration for Wave 1.
5. **Twilio trial 10-minute hard cutoff** -- Calls are cut mid-sentence at 10:00 with no warning. Design Sarah's conversation for 7-8 minutes max. Build a duration watchdog that triggers wrap-up at 8.5 minutes. Strongly consider upgrading to paid Twilio ($20-30).

## Implications for Roadmap

Based on research, the 11-phase structure from AGENT.md is sound and correctly ordered by dependencies. The critical path is: Foundation --> Voice Backend --> Cloud Run Deploy --> Twilio Integration --> n8n Orchestration --> E2E Testing.

### Phase 1: Prerequisites
**Rationale:** Everything downstream depends on accounts, API keys, and content being ready. Two critical validations must happen here that cannot wait: (1) Gemini API key tested for live audio streaming (not just text), and (2) all 10 Twilio test numbers pre-verified.
**Delivers:** Validated API keys, prepared PDF knowledge base content, verified Twilio numbers, account configurations.
**Addresses:** Foundation dependencies for all features.
**Avoids:** Pitfall 2 (discovering deprecated model at Phase 3), Pitfall 5 (unverified numbers causing silent call failures).

### Phase 2: Data Layer (Supabase + Firestore)
**Rationale:** Every component reads from or writes to Supabase. Firestore knowledge base is required before the voice agent can be tested. Build the data foundation before any feature work.
**Delivers:** Complete Supabase schema with `sales_agent` tables, Firestore collections seeded from 5 PDFs, CSV import script.
**Addresses:** Data foundation for all P1 features, atomic booking constraints, event logging infrastructure.
**Avoids:** Pitfall 7 (validate extracted PDF text against originals), Pitfall 8 (add database-level constraint preventing duplicate active bookings).

### Phase 3: Voice Agent Backend
**Rationale:** Highest risk, highest value. The ADK agent (Sarah), Gemini Live API session management, audio transcoding module, and Firestore tool integration are the most technically complex pieces. Build early so problems surface early.
**Delivers:** Working voice agent that can converse using knowledge base content, qualify leads, handle objections, determine outcomes.
**Uses:** Python 3.12, FastAPI, google-genai, Google ADK, google-cloud-firestore.
**Implements:** Cloud Run voice system component, audio bridge pattern.
**Avoids:** Pitfall 1 (build transcoder as isolated module with unit tests), Pitfall 2 (configurable model identifier).

### Phase 4: Browser Voice UI
**Rationale:** Test the voice agent without burning Twilio credits. Validates Sarah's conversation quality, knowledge base accuracy, and latency before adding telephony complexity.
**Delivers:** React SPA that connects to the voice agent via WebSocket for browser-based testing.
**Addresses:** Early validation of conversation quality and knowledge base accuracy.

### Phase 5: Cloud Run Deployment
**Rationale:** The voice agent must be accessible from the internet before Twilio can connect to it. Measure cold start time here to make the min-instances decision.
**Delivers:** Dockerized voice agent deployed on Cloud Run, health check endpoint, cold start measurement.
**Avoids:** Pitfall 9 (measure cold start; implement min-instances=1 if >5 seconds, or pre-warm request from n8n).

### Phase 6: Twilio Integration
**Rationale:** Connect real phone calls. This is where the audio format mismatch (Pitfall 1) will be validated end-to-end for the first time. Must be thoroughly tested with actual calls before touching real leads.
**Delivers:** Outbound calling via Twilio, Media Streams WebSocket handler, call recording, trial message handling.
**Avoids:** Pitfall 1 (end-to-end audio validation), Pitfall 5 (trial message acknowledged in Sarah's opening, duration watchdog at 8.5 min), Pitfall 11 (strip audio headers from Twilio payloads).

### Phase 7: OpenClaw WhatsApp
**Rationale:** Independent of voice stack. Can be built in parallel with Phases 3-6 but must be complete before E2E testing. The booking flow is the pipeline's entry point for leads.
**Delivers:** WhatsApp connection, outreach message templates (with US number warning), free-text booking conversation, rate limiting.
**Avoids:** Pitfall 4 (rate limiting, message variation, 30-second spacing), Pitfall 12 (pin OpenClaw to known-good version).

### Phase 8: n8n Orchestration
**Rationale:** Ties all systems together. Requires all components to be at least partially functional. This is where the dead-letter pattern for webhook resilience must be implemented.
**Delivers:** All pipeline workflows: lead intake, outreach triggering, call scheduling with reminders, post-call branching, payment emails, admin notifications.
**Avoids:** Pitfall 3 (dead-letter pattern with Supabase fallback, explicit WEBHOOK_URL configuration), Pitfall 8 (atomic status checks in booking workflow), Pitfall 13 (UTC-based scheduling with timezone conversion for display).

### Phase 9: n8n Monitoring
**Rationale:** Observability is only useful once the pipeline runs. Build after orchestration is functional.
**Delivers:** Webhook health self-ping, stuck lead detection cron, service health checks, daily metrics computation, webhook receipt counting (to detect Pitfall 3).
**Avoids:** Pitfall 3 detection (compare Cloud Run "webhook sent" logs against n8n "webhook received" logs).

### Phase 10: E2E Testing (Wave 0 -- 10 leads)
**Rationale:** Full pipeline validation with real leads. All pitfalls converge here. Every detection mechanism from the pitfalls research should be explicitly tested.
**Delivers:** 10 leads processed through the complete pipeline. Conversion data. Identified issues for remediation before Wave 1.
**Addresses:** All P1 features validated end-to-end.

### Phase 11: Wave 1 Launch (200 leads)
**Rationale:** Scale validation after E2E proves the pipeline works. P2 features (stuck lead detection, payment reminders, rate limiting enforcement) become necessary at this scale.
**Delivers:** 200 leads processed. Revenue data. Validated conversion rates.

### Phase Ordering Rationale

- **Phases 1-2 are foundation.** Every other phase reads from Supabase and Firestore. Skipping or rushing these creates cascading failures.
- **Phase 3 is deliberately early.** The voice agent is the highest-risk component (dual WebSocket bridging, real-time audio transcoding, new API surface). Surfacing problems at Phase 3 leaves time to solve them before the pipeline needs to work end-to-end.
- **Phases 4-5-6 are sequential by necessity.** Browser test (no Twilio cost) --> deploy to cloud (make accessible) --> connect Twilio (real calls). Each validates the previous before adding complexity.
- **Phase 7 is independent and parallelizable.** OpenClaw configuration has no dependency on the voice stack. It could run alongside Phases 3-6 if resources allow.
- **Phase 8 is the integration point.** n8n orchestration cannot be tested until both text (Phase 7) and voice (Phase 6) are functional.
- **Phases 9-10-11 are sequential.** Monitor --> test --> launch. Each informs the next.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Voice Agent Backend):** The ADK streaming toolkit integration with Twilio Media Streams has no official reference implementation. The Gemini side is well-documented; the Twilio bridge is custom code. Needs `/gsd:research-phase` to investigate current ADK streaming examples and Gemini Live API audio format requirements at build time.
- **Phase 6 (Twilio Integration):** Gemini Live API may have added native mulaw support since research date. Verify at build time whether the transcoding layer is still needed or if Gemini accepts mulaw directly. Needs research.
- **Phase 8 (n8n Orchestration):** The dead-letter pattern for webhook resilience is non-standard for n8n. Needs research on the best implementation approach (cron-based Supabase scan vs. n8n error handling nodes).

Phases with standard patterns (skip research):
- **Phase 1 (Prerequisites):** Account setup and API validation. Well-documented.
- **Phase 2 (Data Layer):** Standard Supabase schema creation and Firestore seeding. Well-documented.
- **Phase 4 (Browser Voice UI):** Standard React + WebSocket. Well-documented.
- **Phase 5 (Cloud Run Deployment):** Standard Docker + gcloud deploy. Well-documented.
- **Phase 7 (OpenClaw WhatsApp):** Configuration, not code. OpenClaw docs are sufficient.
- **Phase 9 (n8n Monitoring):** Standard n8n cron workflows. Well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified via official PyPI/npm/docs. Versions confirmed current. google-genai is the correct unified SDK replacing the deprecated package. |
| Features | HIGH | Requirements thoroughly defined in AGENT.md and PROJECT.md. Feature landscape cross-referenced against competitor platforms (Synthflow, Bland, Vapi). Clear P1/P2/P3 prioritization. |
| Architecture | HIGH | Two-system hub-and-spoke model verified against industry patterns. Dual WebSocket bridge pattern confirmed via Twilio+OpenAI reference implementations (same pattern, different LLM). |
| Pitfalls | HIGH | All 5 critical pitfalls verified with official docs or GitHub issues. Audio format mismatch, model deprecation, webhook failures, WhatsApp bans, and trial limits are all documented with primary sources. |
| Gemini Live API specifics | MEDIUM | API is in active development with frequent model updates. Audio format requirements, model identifiers, and session limits may change between research and implementation. Must verify at Phase 3 start. |

**Overall confidence:** HIGH

### Gaps to Address

- **Gemini Live API current audio format**: Does the latest model accept mulaw directly, or is PCM conversion still required? This determines whether the transcoding module is needed. Check at Phase 3 start.
- **ADK streaming + Twilio bridge**: No official reference implementation exists for this exact combination. The Twilio+OpenAI Realtime API pattern is analogous but uses a different protocol. Phase 3 will require exploratory development.
- **OpenClaw webhook payload format**: The exact JSON structure of booking confirmation webhooks from OpenClaw needs documentation during Phase 7. Not available in advance.
- **Twilio trial vs paid account decision**: The $0-15 budget versus trial limitations tradeoff needs a firm decision before Phase 10. Research strongly recommends upgrading ($20-30) but this is a business decision.
- **Gemini API rate limits for live audio**: Actual rate limits for the specific model and API key tier need empirical testing during Phase 3. Documentation does not specify clear limits for Live API sessions.
- **Gemini Live API 10-minute session limit handling**: The project targets 5-10 minute calls. A session handoff mechanism (save context, reconnect) may be needed but adds significant complexity. Validate whether calls consistently stay under 10 minutes during Phase 10.

## Sources

### Primary (HIGH confidence)
- [Gemini Live API overview -- Google AI](https://ai.google.dev/gemini-api/docs/live-api)
- [Gemini Live API on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api)
- [Google ADK Python -- GitHub](https://github.com/google/adk-python)
- [Google ADK on PyPI](https://pypi.org/project/google-adk/)
- [google-genai SDK -- GitHub](https://github.com/googleapis/python-genai)
- [ADK Streaming Toolkit -- Official Docs](https://google.github.io/adk-docs/streaming/)
- [ADK Streaming Dev Guide Part 1](https://google.github.io/adk-docs/streaming/dev-guide/part1/)
- [Build real-time voice agent with Gemini and ADK -- Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/build-a-real-time-voice-agent-with-gemini-adk)
- [Twilio Media Streams overview](https://www.twilio.com/docs/voice/media-streams)
- [Twilio Media Streams WebSocket messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages)
- [Twilio Free Trial Limitations](https://help.twilio.com/articles/360036052753-Twilio-Free-Trial-Limitations)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [supabase-py on PyPI](https://pypi.org/project/supabase/)
- [n8n Production Webhook Issue #16339](https://github.com/n8n-io/n8n/issues/16339)
- [n8n Webhooks Randomly Stop -- Community](https://community.n8n.io/t/help-needed-webhooks-randomly-stop-require-workflow-toggle-to-resume-not-sustainable/119667)
- [OpenClaw WhatsApp documentation](https://docs.openclaw.ai/channels/whatsapp)
- [Gemini Live Audio Regression (March 9, 2026) -- Forum](https://discuss.ai.google.dev/t/gemini-live-audio-regression-post-march-9-2026-update/130605)
- [Gemini Live API mulaw support discussion -- Forum](https://discuss.ai.google.dev/t/live-api-support-for-mulaw-g711-ulaw-input-output/86053)

### Secondary (MEDIUM confidence)
- [Building AI IVA with Gemini + Twilio -- ckBrox](https://thoughts.ckbrox.com/building-an-ai-interactive-voice-agent-iva-with-gemini-multimodal-live-and-twilio/)
- [Building Telephone Voice Agent with FreeSWITCH and ADK -- Medium](https://medium.com/google-cloud/gemini-live-part-1-building-a-low-latency-telephone-voice-agent-with-freeswitch-and-adk-agents-ceafd209f017)
- [Twilio + OpenAI Realtime API Python tutorial -- Twilio Blog](https://www.twilio.com/en-us/blog/voice-ai-assistant-openai-realtime-api-python)
- [Outbound calls Python OpenAI Realtime API -- Twilio Blog](https://www.twilio.com/en-us/blog/outbound-calls-python-openai-realtime-api-voice)
- [OpenClaw WhatsApp Risks for Engineers](https://zenvanriel.com/ai-engineer-blog/openclaw-whatsapp-risks-engineers-guide/)
- [n8n Self-Hosted Webhook Fix Guide](https://optimizesmart.com/blog/self-hosted-n8n-webhooks-not-working-here-is-the-fix/)
- [AI Voice Agents in 2025 -- Dev.to Guide](https://dev.to/kaymen99/ai-voice-agents-in-2025-a-comprehensive-guide-3kl)
- [Bland AI vs Vapi AI vs Synthflow AI comparison](https://synthflow.ai/blog/bland-ai-vs-vapi-ai)
- [AI Voice Agents in 2025 -- Retell AI](https://www.retellai.com/blog/ai-voice-agents-in-2025)
- [Voice agents and Conversational AI 2026 -- ElevenLabs](https://elevenlabs.io/blog/voice-agents-and-conversational-ai-new-developer-trends-2025)
- [How Voice AI Is Redefining Sales 2026](https://salesandmarketing.com/how-voice-ai-is-redefining-sales-in-2026/)
- [State of Voice 2025 -- Deepgram](https://deepgram.com/learn/state-of-voice-ai-2025)
- [AI Agent Pilot Failures Report -- Composio](https://composio.dev/blog/why-ai-agent-pilots-fail-2026-integration-roadmap)
- [AssemblyAI 2026 Voice Agent Insights](https://www.assemblyai.com/blog/new-2026-insights-report-what-actually-makes-a-good-voice-agent)
- [Voice AI Challenges -- BeConversive](https://www.beconversive.com/blog/voice-ai-challenges)

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*

# Domain Pitfalls

**Domain:** AI Voice Sales Agent Pipeline (Gemini Live API + Twilio + WhatsApp + n8n orchestration)
**Project:** Cloudboosta AI Sales Agent
**Researched:** 2026-03-12

---

## Critical Pitfalls

Mistakes that cause rewrites, lost leads, or system-wide failures.

---

### Pitfall 1: Audio Format Mismatch Between Twilio and Gemini Live API

**What goes wrong:** Twilio Media Streams send audio as 8-bit mulaw at 8kHz sample rate. Gemini Live API requires raw 16-bit PCM at 16kHz, little-endian. If you pass Twilio audio directly to Gemini (or vice versa), you get silence, static, or garbled audio. The call appears to connect but Sarah cannot hear the lead, or the lead hears robotic noise.

**Why it happens:** Developers test with browser-based audio (which is already PCM16/16kHz) and everything works. Then they connect Twilio and the audio format is completely different. The mismatch is bidirectional -- you must convert mulaw-to-PCM on inbound AND PCM-to-mulaw on outbound.

**Consequences:** Voice agent appears broken in production despite working in browser tests. Leads hear nothing or garbled audio and hang up. First impressions are destroyed. Debugging is difficult because WebSocket connections succeed -- it is the payload content that is wrong.

**Prevention:**
- Build the audio transcoding layer (mulaw 8kHz <-> PCM16 16kHz) as an isolated, testable module BEFORE integrating Twilio with Gemini.
- Use Python's `audioop` library or `pydub` for the conversion. The conversion must happen in real-time on every audio chunk, not as batch processing.
- Write unit tests that take known mulaw samples, convert to PCM16, and verify the output matches expected waveforms.
- Test with actual Twilio Media Streams early (Phase 6), not just browser audio (Phase 4).

**Detection:** During testing, if the browser voice UI works but Twilio calls produce silence or distortion, this is the cause. Log audio chunk sizes on both sides of the conversion -- mulaw chunks should be roughly half the size of PCM16 chunks at double the sample rate.

**Confidence:** HIGH -- multiple sources confirm this exact mismatch. The ckBrox Gemini+Twilio integration guide and the Google AI Developer Forum thread both document this as the primary integration challenge.

**Phase impact:** Phase 3 (Voice Agent Backend) must include the transcoding module. Phase 6 (Twilio Integration) must validate it end-to-end.

---

### Pitfall 2: Gemini Live API Model Deprecation and Audio Quality Regression

**What goes wrong:** Google actively deprecates Gemini Live API model versions on short timelines. The model `gemini-live-2.5-flash-preview-native-audio-09-2025` is being removed on March 19, 2026 -- one week from the research date. Additionally, a post-March 9, 2026 update introduced severe audio quality regression: harsh sibilance distortion on "S" and "Sh" sounds across Lyra and Pegasus voices.

**Why it happens:** Gemini Live API is still in active development. Google ships breaking changes, model deprecations, and quality regressions without long notice periods. The API surface and model identifiers change frequently.

**Consequences:** System breaks overnight with no code changes. Sarah suddenly sounds terrible (distortion) or the API returns errors (deprecated model). With 10 test leads, every failed call is 10% of the test cohort lost.

**Prevention:**
- Pin the model version in config.py (not hardcoded in agent logic) so it can be changed in one place.
- The PROJECT.md specifies `gemini-2.0-flash-live` -- verify this model identifier is current before Phase 3 begins. Check the Gemini API docs at build time, not research time.
- Build a "voice quality smoke test" script that calls the API, generates a sample response, and lets the admin listen before deploying to real leads.
- Subscribe to the Google AI Developers Forum and Gemini API changelog for deprecation notices.
- Validate the Gemini API key for live audio streaming in Phase 1 (Prerequisites), not Phase 3. PROJECT.md already flags this: "Gemini Live API key exists but NOT yet tested for real-time audio streaming."

**Detection:** Unexpected API errors (model not found, 404, deprecation warnings in response headers). Sudden change in voice quality that was not caused by a code deployment. Monitor Gemini API response headers for deprecation warnings.

**Confidence:** HIGH -- the deprecation timeline and audio regression are documented in the Google AI Developers Forum as of March 2026.

**Phase impact:** Phase 1 must validate the API key and model. Phase 3 must use a configurable model identifier. Phase 10 (E2E testing) must include a voice quality check.

---

### Pitfall 3: n8n Self-Hosted Webhooks Silently Fail in Production

**What goes wrong:** n8n webhooks randomly stop processing incoming requests. The webhook endpoint returns 200 OK (appearing healthy), but the workflow never executes. The only fix is to manually deactivate and reactivate the workflow. This is a documented, recurring bug in self-hosted n8n.

**Why it happens:** Multiple root causes: (1) The WEBHOOK_URL environment variable is misconfigured or missing, so n8n generates internal URLs that don't match the public-facing reverse proxy URL. (2) Production webhook registration silently fails after workflow activation -- no error logged, endpoint responds 200 OK, but no execution triggers. (3) Reverse proxy (Cloudflare, Nginx, Traefik) may block or modify webhook payloads from external services like Twilio.

**Consequences:** This is catastrophic for an automated sales pipeline. Post-call webhooks from Cloud Run silently disappear. Leads who said "yes" on the call never receive payment emails. Follow-up scheduling never triggers. The system appears healthy (200 OK responses) while leads fall through the cracks. With no error signals, the failure is invisible until someone manually checks the database.

**Prevention:**
- Set `WEBHOOK_URL` explicitly in n8n's environment to match the public-facing URL exactly (including https:// and the correct domain).
- Build a "webhook health check" workflow in n8n that pings itself every 5 minutes and writes the result to Supabase `service_health`. If the self-ping fails, alert the admin.
- Implement a "dead letter" pattern: after Cloud Run sends a post-call webhook, it writes the event to Supabase directly as a fallback. n8n processes from the webhook, but a separate n8n cron workflow scans Supabase every 10 minutes for unprocessed events.
- Never rely on n8n as the sole data pathway. Critical state changes (call outcome, lead status) must be written to Supabase by the originating system (Cloud Run), not only by n8n after receiving a webhook.
- Test webhook reliability under the exact production configuration (reverse proxy, SSL, domain) during Phase 8, not just with n8n's built-in test button.

**Detection:** Compare `pipeline_logs` entries from Cloud Run ("webhook sent") against n8n ("webhook received"). Any mismatch = silent failure. The monitoring workflow in Phase 9 should specifically count these mismatches.

**Confidence:** HIGH -- multiple GitHub issues (#16339, #16858, #25700) and community reports confirm this is a persistent, unresolved issue in self-hosted n8n.

**Phase impact:** Phase 8 (n8n Orchestration) must implement the dead-letter fallback. Phase 9 (Monitoring) must detect webhook failures. Phase 5 (Cloud Run Deployment) must write critical data to Supabase directly, not depend solely on n8n webhooks.

---

### Pitfall 4: WhatsApp Account Ban via OpenClaw

**What goes wrong:** OpenClaw uses Baileys, an open-source library that reverse-engineers the WhatsApp Web protocol. Running automation through it violates Meta's Terms of Service. The personal WhatsApp number used for outreach gets permanently banned. All leads lose their communication channel. Booking conversations in progress are destroyed.

**Why it happens:** Meta actively detects automation patterns: rapid message sending, identical message content sent to multiple numbers, unusual connection patterns (reconnect loops). OpenClaw's connection to WhatsApp Web can enter reconnect loops that trigger Meta's detection systems. There is no warning -- one day the number works, the next it is banned with no appeal path.

**Consequences:** Complete loss of the text outreach and booking channel. With a personal Nigerian number, there is no way to get it back once banned. All 10 test leads who were in mid-conversation lose their thread. The entire WhatsApp side of the 2-system architecture goes down.

**Prevention:**
- Rate-limit outreach aggressively. The project already specifies 10/day for test phase -- enforce this at the n8n level, not just as a guideline.
- Never send identical messages to multiple leads. Template each message with the lead's name and a slight variation.
- Space messages at least 30 seconds apart. Burst-sending 10 messages in a minute is a strong ban signal.
- Have a backup plan: identify a second phone number that can be connected to OpenClaw if the first is banned.
- Consider upgrading to WhatsApp Business API for Wave 1 (200 leads). The project correctly marks this as out-of-scope for test phase, but it should be the first upgrade after validation.
- Monitor connection stability. If OpenClaw's WhatsApp connection enters reconnect loops, stop all automation immediately and reconnect manually.

**Detection:** OpenClaw stops receiving messages or gets "not registered" errors. The WhatsApp Web session shows "logged out" without user action. Messages show single check (sent) but never double check (delivered).

**Confidence:** HIGH -- OpenClaw's own documentation and multiple engineering blogs confirm this risk. The project is deliberately accepting this risk for the test phase (10 leads), which is reasonable, but it must be a known risk, not a surprise.

**Phase impact:** Phase 7 (OpenClaw WhatsApp) must implement rate limiting and message variation. Phase 10 (E2E Testing) must test with slow, spaced-out message delivery. Phase 11 (Wave 1) should plan for WhatsApp Business API migration.

---

### Pitfall 5: Twilio Trial Account Hard Limits Break the Call Experience

**What goes wrong:** Twilio trial accounts have three hard limits that directly conflict with the project requirements: (1) Maximum call duration of 10 minutes -- cannot be extended regardless of configuration. (2) Maximum 4 concurrent calls. (3) Calls can only reach pre-verified numbers. Additionally, trial calls are prefixed with a "This is a trial account" message that undermines Sarah's professional opening.

**Why it happens:** These are Twilio's anti-abuse measures for free accounts. The 10-minute limit is particularly dangerous because the project targets 5-10 minute calls. A qualifying conversation that runs long will be hard-cut at exactly 10 minutes, mid-sentence, with no warning.

**Consequences:** Sarah is mid-close with a lead who is about to commit, and the call drops at 10:00. The lead perceives this as a technical failure, not a trial limit. The trial message at the start of the call ("you are receiving a call from a Twilio trial account") immediately signals "cheap/experimental" to the lead, undermining Sarah's warm professional persona. If any test number was not pre-verified, the call fails silently.

**Prevention:**
- Budget $20-30 to upgrade to a paid Twilio account before Wave 0 testing. The project's $0-15 budget constraint will cause more damage in lost test leads than it saves in Twilio fees.
- If staying on trial: design Sarah's conversation to target 7-8 minutes max, leaving 2-3 minute buffer before the hard cutoff.
- Build a call-duration watchdog: at 8.5 minutes, Sarah should begin wrapping up ("I want to be respectful of your time, let me summarize...").
- Pre-verify ALL 10 test numbers before any testing begins. Build a verification checklist script that checks each number's status via the Twilio API.
- Acknowledge the trial message in Sarah's opening: "You may have heard a brief message before I joined -- that is just our phone system. I am Sarah, an AI assistant from Cloudboosta..."

**Detection:** Calls dropping at exactly 10:00 in call_logs. Outbound calls failing with "unverified number" errors. Leads mentioning the trial message in feedback.

**Confidence:** HIGH -- Twilio's own documentation explicitly states these limits.

**Phase impact:** Phase 1 (Prerequisites) must verify all test numbers. Phase 3 (Voice Agent) must implement the duration watchdog. Phase 6 (Twilio Integration) must handle the trial message gracefully. Budget decision should be revisited before Phase 10.

---

## Moderate Pitfalls

---

### Pitfall 6: Latency Kills Natural Conversation

**What goes wrong:** The voice pipeline has multiple latency sources: Twilio Media Streams to Cloud Run (network), mulaw-to-PCM conversion (CPU), Gemini Live API processing (AI inference), PCM-to-mulaw conversion (CPU), Cloud Run to Twilio (network). If total round-trip exceeds 1 second, the conversation feels robotic. Leads talk over Sarah. Sarah talks over leads. The "warm British professional" persona is destroyed by awkward pauses.

**Why it happens:** Each component adds 100-300ms. Developers test each component in isolation and see acceptable latency. But the full pipeline compounds: 200ms (Twilio) + 100ms (transcode) + 400ms (Gemini) + 100ms (transcode) + 200ms (Twilio) = 1000ms. Add network variance and you hit 1.5s regularly.

**Prevention:**
- Deploy Cloud Run in `us-east5` (already specified) close to Twilio's US infrastructure.
- Use streaming responses from Gemini Live API -- do not wait for the complete response before sending audio back. Send audio chunks to Twilio as they arrive from Gemini.
- Pre-warm Cloud Run instances to avoid cold start latency on the first call of the day. A cold start can add 5-15 seconds.
- Implement Twilio's recommended light buffering (40-80ms) for jitter smoothing, but no more.
- Profile the full pipeline end-to-end during Phase 6 testing. Set a latency budget: target 800ms total round-trip.

**Detection:** Leads consistently talking over Sarah. Sarah interrupting leads. Awkward silences in call recordings. Measure time between end-of-lead-speech and start-of-Sarah-speech in call recordings.

**Confidence:** MEDIUM -- latency budgets are well-documented in voice AI literature, but exact numbers depend on the specific Gemini model and Cloud Run configuration.

**Phase impact:** Phase 3 must implement streaming audio responses. Phase 5 (Cloud Run) must configure minimum instances to avoid cold starts. Phase 6 must profile end-to-end latency.

---

### Pitfall 7: PDF Knowledge Base Creates Stale or Hallucinated Responses

**What goes wrong:** Sarah's knowledge comes from PDFs stored in Firestore. If the PDF parsing extracts garbled text (tables, formatting, headers), Sarah receives corrupted context and fabricates answers. If PDFs are not updated, Sarah gives outdated pricing or programme details. If the conversation-sequence PDF is ambiguous, Sarah's qualification logic becomes unpredictable.

**Why it happens:** PDFs are not designed for machine consumption. Tables lose structure. Headers become inline text. Page numbers and footers contaminate content. The Gemini model tries to be helpful and fills gaps with hallucinated details, which is especially dangerous for pricing (GBP 1,200 vs 1,800).

**Prevention:**
- Convert PDFs to clean plain text or structured JSON before seeding Firestore. Do not feed raw PDF binary to the pipeline.
- Build a "knowledge base validation" script that queries Sarah with known questions (price of Cloud Security? price of SRE?) and validates answers against expected values.
- Include explicit "do not answer if not in knowledge base" instructions in Sarah's system prompt.
- Version the knowledge base entries in Firestore with timestamps so you can track when content was last updated.
- Test every PDF extraction manually before Phase 3 -- read the extracted text and verify it matches the original document.

**Detection:** Sarah giving wrong prices, mentioning programmes that do not exist, or giving vague answers to questions that should have specific answers. Run the validation script before every deployment.

**Confidence:** MEDIUM -- PDF extraction issues are well-known, but the severity depends on the specific PDF formatting.

**Phase impact:** Phase 1 (Prerequisites) must produce clean, well-structured PDFs. Phase 2 (Firestore Setup) must extract and validate content. Phase 3 must include the "do not fabricate" system prompt guardrail.

---

### Pitfall 8: Dual-Channel Race Condition in Booking

**What goes wrong:** A lead receives both WhatsApp and email outreach simultaneously. They reply to both channels. OpenClaw books a call from WhatsApp at 3pm. The email reply triggers a second booking at 4pm. Two calls get scheduled. Sarah calls twice. Lead is confused or annoyed.

**Why it happens:** The project specifies "first response wins, other channel gets 'already scheduled'" but implementing this requires atomic state checks across two independent systems (OpenClaw and email via n8n). If OpenClaw and n8n both check the lead status at the same moment before either has written the update, both see "awaiting_response" and both proceed.

**Prevention:**
- Use Supabase as the single source of truth with a database-level constraint. When updating lead status from "contacted" to "booking," use an atomic UPDATE with a WHERE clause: `UPDATE leads SET status = 'booking' WHERE id = X AND status = 'contacted'`. If 0 rows affected, the other channel already claimed it.
- OpenClaw must check Supabase before confirming a booking, not just its own internal state.
- n8n must check Supabase before processing an email reply.
- Add a 30-second delay between WhatsApp and email outreach to make simultaneous responses less likely.

**Detection:** Two entries in `call_logs` for the same lead on the same day. Leads receiving two different confirmation messages.

**Confidence:** MEDIUM -- race conditions are a well-known distributed systems problem. The specific dual-channel architecture makes this highly likely.

**Phase impact:** Phase 7 (OpenClaw) and Phase 8 (n8n) must both implement the atomic status check pattern. Phase 2 (Supabase Schema) should add a database constraint preventing duplicate active bookings for the same lead.

---

### Pitfall 9: Cloud Run Cold Starts During Scheduled Calls

**What goes wrong:** Cloud Run scales to zero when idle. When n8n triggers a scheduled call, Cloud Run needs to spin up a new instance. Cold start takes 5-15 seconds for a Python container with ML dependencies. Twilio's call setup has a timeout. Either Twilio times out waiting for the WebSocket connection, or the lead answers and hears 10 seconds of silence before Sarah speaks.

**Why it happens:** Cloud Run's default behavior is to scale to zero to save costs (critical for the $0-15 budget). The container image for the voice agent will be large (Python + Gemini SDK + audio libraries). First request after idle triggers a full container boot.

**Prevention:**
- Set `--min-instances=1` on the Cloud Run service to keep one instance warm. This costs roughly $5-10/month but eliminates cold starts entirely.
- If budget prohibits warm instances: build a "pre-warm" step in n8n that hits the Cloud Run health check endpoint 60 seconds before the scheduled call time.
- Optimize the Docker image: use a slim Python base, minimize dependencies, use multi-stage builds.
- Measure cold start time during Phase 5 deployment. If it exceeds 5 seconds, warm instances are mandatory.

**Detection:** First call of the day or after idle period has a long initial silence. `pipeline_logs` show a gap between "call initiated" and "WebSocket connected" timestamps.

**Confidence:** HIGH -- Cloud Run cold start behavior is well-documented. The $0-15 budget constraint makes this a near-certain issue.

**Phase impact:** Phase 5 (Cloud Run Deployment) must measure cold start time and decide on warm instances. Phase 4 (n8n Call Scheduling) should implement the pre-warm request.

---

### Pitfall 10: Single Gemini API Key Shared Across Systems

**What goes wrong:** One Gemini API key is shared between OpenClaw (text, VPS #2) and Cloud Run (voice). If the key hits rate limits from OpenClaw's text conversations, Sarah's voice calls fail mid-conversation. If the key is revoked or rotated, both systems break simultaneously. Rate limit errors from one system are impossible to attribute without careful logging.

**Why it happens:** The project constraint explicitly states "Single Gemini key: Shared across OpenClaw (text) and Cloud Run (voice)." This is a pragmatic decision for the test phase but creates a single point of failure.

**Prevention:**
- Request a second Gemini API key if possible -- one for text (OpenClaw), one for voice (Cloud Run). Even within the same GCP project, multiple keys can be created.
- If truly limited to one key: implement rate limit awareness in both systems. Cloud Run voice calls should have priority -- if rate limits are approached, throttle OpenClaw text responses rather than risking a mid-call failure.
- Log every Gemini API call with the source system (text vs voice) so rate limit attribution is possible.
- Build a rate limit monitor that alerts when usage exceeds 80% of the quota.

**Detection:** Intermittent Gemini API errors (429 Too Many Requests) that correlate with high OpenClaw text activity. Voice calls failing during periods of active WhatsApp conversations.

**Confidence:** MEDIUM -- depends on actual rate limits for the specific Gemini model and tier.

**Phase impact:** Phase 1 (Prerequisites) should investigate creating a second API key. Phase 3 and Phase 7 must implement rate-limit-aware API calls.

---

## Minor Pitfalls

---

### Pitfall 11: Twilio Media Streams Payload Contains Header Bytes

**What goes wrong:** When constructing audio payloads to send back to Twilio via the Media Stream WebSocket, developers accidentally include audio file type header bytes (WAV headers, etc.) in the payload. This causes audio to stream incorrectly -- the first chunk plays as noise, then subsequent chunks may be offset.

**Prevention:** Always send raw audio bytes only. Strip any WAV/PCM headers before base64 encoding. The payload must be pure audio/x-mulaw, base64 encoded, with no file format headers.

**Phase impact:** Phase 6 (Twilio Integration).

---

### Pitfall 12: OpenClaw Baileys Dependency Supply Chain Risk

**What goes wrong:** OpenClaw's WhatsApp integration depends on Baileys, an open-source library. In late 2025, a malicious npm package mimicking Baileys was discovered that stole WhatsApp tokens and messages.

**Prevention:** Pin OpenClaw to a known-good version. Verify the Baileys dependency is the legitimate package. Do not run `npm update` blindly on the OpenClaw instance.

**Phase impact:** Phase 7 (OpenClaw WhatsApp Configuration).

---

### Pitfall 13: Timezone Mismatch in Scheduling

**What goes wrong:** Leads are in Nigeria (WAT, UTC+1). The system uses GMT (UTC+0). Twilio is US-based. Cloud Run is in us-east5. A lead says "call me at 3pm" -- 3pm in which timezone? OpenClaw confirms 3pm but schedules it as 3pm GMT. Lead expects 3pm WAT. Sarah calls one hour early.

**Prevention:** Store all times in UTC internally. OpenClaw must ask or infer the lead's timezone during booking. Display confirmation messages in the lead's local timezone. n8n cron triggers must use UTC with explicit timezone conversion.

**Phase impact:** Phase 3 (Booking), Phase 4 (Call Scheduling).

---

### Pitfall 14: Call Recording Consent and Legal Compliance

**What goes wrong:** Sarah mentions "this call may be recorded" but if the recording starts before Sarah speaks (Twilio starts recording at call connect), the lead's initial words are recorded without disclosure. In some jurisdictions, this is a legal violation.

**Prevention:** Configure Twilio to start recording AFTER the call connects and Sarah's disclosure plays, not at call setup. Use Twilio's `Record` attribute on the `<Connect>` verb, not on the initial `<Dial>`. Alternatively, start recording from code after Sarah's opening statement completes.

**Phase impact:** Phase 6 (Twilio Integration).

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation | Severity |
|-------|---------------|------------|----------|
| 1 - Prerequisites | Gemini API key untested for live audio (Pitfall 2) | Validate key with a live audio test before proceeding | Critical |
| 1 - Prerequisites | Twilio test numbers not verified (Pitfall 5) | Script to verify all 10 numbers via API | Critical |
| 2 - Supabase Schema | No atomic booking constraint (Pitfall 8) | Add WHERE clause pattern to booking updates | Moderate |
| 3 - Voice Agent Backend | Audio format handled at wrong layer (Pitfall 1) | Build transcoding as isolated, tested module | Critical |
| 3 - Voice Agent Backend | Model identifier hardcoded (Pitfall 2) | Configurable model in config.py | Critical |
| 3 - Voice Agent Backend | PDF parsing produces garbage (Pitfall 7) | Validate extracted text against source PDFs | Moderate |
| 5 - Cloud Run Deployment | Cold start kills first call (Pitfall 9) | Measure cold start, implement pre-warm or min-instances | Moderate |
| 6 - Twilio Integration | mulaw/PCM mismatch not caught (Pitfall 1) | End-to-end audio test with real Twilio call | Critical |
| 6 - Twilio Integration | Trial message undermines persona (Pitfall 5) | Acknowledge in Sarah's opening or upgrade account | Moderate |
| 7 - OpenClaw WhatsApp | Account banned from burst messaging (Pitfall 4) | Enforce rate limits, vary messages | Critical |
| 8 - n8n Orchestration | Webhooks silently fail (Pitfall 3) | Dead-letter pattern, direct Supabase writes | Critical |
| 8 - n8n Orchestration | Dual-channel race condition (Pitfall 8) | Atomic database status checks | Moderate |
| 9 - n8n Monitoring | Monitoring doesn't catch webhook failure (Pitfall 3) | Self-ping health check, webhook receipt counting | Critical |
| 10 - E2E Testing | All pitfalls converge on real leads | Test each pitfall's detection mechanism explicitly | Critical |
| 11 - Wave 1 Launch | WhatsApp ban at 200-lead scale (Pitfall 4) | Plan WhatsApp Business API migration | Critical |

---

## Sources

- [Gemini Live API overview - Google AI](https://ai.google.dev/gemini-api/docs/live-api) -- HIGH confidence
- [Gemini Live Audio Regression (March 9, 2026)](https://discuss.ai.google.dev/t/gemini-live-audio-regression-post-march-9-2026-update/130605) -- HIGH confidence
- [Gemini Live API mulaw support discussion](https://discuss.ai.google.dev/t/live-api-support-for-mulaw-g711-ulaw-input-output/86053) -- HIGH confidence
- [Building AI IVA with Gemini + Twilio (ckBrox)](https://thoughts.ckbrox.com/building-an-ai-interactive-voice-agent-iva-with-gemini-multimodal-live-and-twilio/) -- MEDIUM confidence
- [Twilio Media Streams WebSocket Messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) -- HIGH confidence
- [Twilio Free Trial Limitations](https://help.twilio.com/articles/360036052753-Twilio-Free-Trial-Limitations) -- HIGH confidence
- [OpenClaw WhatsApp Risks for Engineers](https://zenvanriel.com/ai-engineer-blog/openclaw-whatsapp-risks-engineers-guide/) -- MEDIUM confidence
- [OpenClaw WhatsApp documentation](https://docs.openclaw.ai/channels/whatsapp) -- HIGH confidence
- [n8n Production Webhook Registration Issue #16339](https://github.com/n8n-io/n8n/issues/16339) -- HIGH confidence
- [n8n Webhooks Randomly Stop](https://community.n8n.io/t/help-needed-webhooks-randomly-stop-require-workflow-toggle-to-resume-not-sustainable/119667) -- HIGH confidence
- [n8n Self-Hosted Webhook Fix Guide](https://optimizesmart.com/blog/self-hosted-n8n-webhooks-not-working-here-is-the-fix/) -- MEDIUM confidence
- [Voice AI Challenges (BeConversive)](https://www.beconversive.com/blog/voice-ai-challenges) -- MEDIUM confidence
- [AI Agent Pilot Failures Report (Composio)](https://composio.dev/blog/why-ai-agent-pilots-fail-2026-integration-roadmap) -- MEDIUM confidence
- [AssemblyAI 2026 Voice Agent Insights](https://www.assemblyai.com/blog/new-2026-insights-report-what-actually-makes-a-good-voice-agent) -- MEDIUM confidence

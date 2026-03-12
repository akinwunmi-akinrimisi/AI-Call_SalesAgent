# Phase 3: Voice Agent Backend - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the ADK voice agent (Sarah) powered by Gemini Live API that conducts a complete qualification sales call: AI disclosure, qualification questioning, programme recommendation, objection handling, commitment ask, and outcome determination (COMMITTED / FOLLOW_UP / DECLINED). Includes duration watchdog, knowledge base integration, and lead profile population. Twilio integration and Cloud Run deployment are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Sarah's Personality & Conversation Style
- Tone: Enthusiastic coach -- high energy, motivational, excited about the lead's potential. Personal and encouraging
- Nigerian-aware: Familiar with Nigerian context (NYSC, Naira references, local tech scene) but speaks standard English. No Pidgin
- Assertiveness: Gently guided -- Sarah has a clear path but follows the lead's pace. Naturally brings tangents back without feeling scripted
- AI disclosure: Natural and brief -- "Hi [name], this is Sarah from Cloudboosta. Just so you know, I'm an AI assistant and this call is being recorded. I'd love to learn about your cloud career goals -- is now a good time?"
- Hesitant leads: Direct but warm -- acknowledges hesitation briefly, then moves forward with clear questions. Doesn't dwell
- Small talk: Brief engagement (1-2 exchanges) then natural redirect to qualification
- Name usage: Natural, 3-4 times throughout the call (greeting, mid-call acknowledgment, closing)

### Qualification Flow & Decision Logic
- Decision tree adherence: Guided but adaptive -- Sarah knows the conversation-sequence PDF stages but adapts order based on what the lead volunteers. Skips questions already answered
- Questioning style: Conversational weaving -- questions flow naturally from previous answers. "That's interesting you're in networking -- have you worked with any cloud platforms before?"
- Recommendation timing: After ALL qualification fields are gathered (role, experience_level, cloud_background, motivation). Don't recommend early
- Recommendation style: Personalized reasoning -- explain WHY this programme fits their specific background and goals
- Vague answers: Offer concrete examples to help them articulate -- "A lot of people come from different angles -- some want to switch careers, others want to level up. What's driving your interest?"
- Profile fields: Must-haves are role, experience_level, cloud_background, motivation. Others (company, preferred_programme) captured naturally if mentioned. Don't force awkward questions
- No-fit leads: Acknowledge and suggest value anyway -- frame as structured refresher, certification prep, and community value

### Objection Handling Approach
- Trigger: Reactive only -- wait for the lead to raise concerns. Don't plant doubts they didn't have
- Knowledge base: Pre-load all 5 PDF contents into Sarah's system instruction at call start. ~43K chars fits Gemini context easily. No mid-call tool calls needed
- Persistence: Two attempts with different angles -- if first response doesn't land, try a different framing (e.g., price -> ROI angle, then payment flexibility). Still respectful
- Salary figures: Yes, use specific numbers from the PDF data ("Cloud engineers in the UK typically earn £30k-£50k starting, and with DevOps that goes to £40k-£95k+")

### Commitment Ask & Outcome Determination
- Transition to close: Natural summary then ask -- Sarah summarizes qualification findings, confirms recommendation, then asks directly: "So [name], based on everything we've discussed, are you ready to get started?"
- COMMITTED threshold: Explicit verbal yes required -- "yes", "let's do it", "I'm in", "sign me up". Anything ambiguous ("I'll think about it", "sounds good") = FOLLOW_UP
- DECLINED: Lead explicitly says no, not interested, or can't afford it
- Follow-up timing: Suggest options -- "Would later this week or early next week work better for a follow-up call?"
- Duration watchdog: Internal signal injected into conversation context at 8.5 minutes. Sarah naturally wraps up without revealing the timer: "I'm conscious of your time, so let me quickly summarize..."

### Claude's Discretion
- Exact system instruction wording and prompt engineering for Sarah's persona
- ADK agent framework structure and tool bindings
- How the duration watchdog is technically implemented (timer thread, async callback, etc.)
- Gemini session configuration (temperature, safety settings, audio format)
- How outcome validation works (Gemini validates against full conversation context)
- FastAPI route structure for the agent endpoint

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/agent.py`: Stub for ADK agent definition -- needs Sarah's persona and tool bindings
- `backend/tools.py`: Stub for Firestore lookup tools -- but decision is to pre-load KB into system prompt instead of runtime tools
- `backend/voice_handler.py`: Stub for Gemini Live API WebSocket handler
- `backend/main.py`: FastAPI server with health check, CORS, ready for agent routes
- `backend/config.py`: Config dataclass with GCP project, region, credentials, Supabase URL/keys
- `backend/logger.py`: Async pipeline_logs writer with Content-Profile: sales_agent header

### Established Patterns
- httpx for async HTTP calls (logger.py)
- Supabase REST API with Content-Profile/Accept-Profile headers for sales_agent schema
- Service account JSON from secrets/ directory for GCP auth
- python-dotenv for env loading
- Gemini model: gemini-live-2.5-flash-native-audio via Vertex AI

### Integration Points
- Firestore knowledge_base collection: 5 docs with markdown content (programmes, conversation-sequence, faqs, payment-details, objection-handling) -- pre-load into system prompt
- Supabase leads table: Sarah populates company, role, experience_level, cloud_background, motivation, preferred_programme during call
- Supabase call_logs table: outcome, objections_raised (JSON array), qualification_summary, transcript, recommended_programme
- pipeline_logs: log call events (call_started, qualification_complete, recommendation_made, objection_handled, outcome_determined)

</code_context>

<specifics>
## Specific Ideas

- conversation-sequence.pdf has a clear decision tree with explicit branching (if background is X -> recommend Y) -- Sarah should internalize this logic
- Sarah should feel like talking to a knowledgeable Nigerian friend who happens to be a cloud career expert
- Two programmes to recommend: Cloud Security (£1,200) and SRE & Platform Engineering (£1,800) based on qualification
- The call is the "revenue moment" -- Sarah's outcome determination feeds directly into n8n post-call workflows

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-voice-agent-backend*
*Context gathered: 2026-03-12*

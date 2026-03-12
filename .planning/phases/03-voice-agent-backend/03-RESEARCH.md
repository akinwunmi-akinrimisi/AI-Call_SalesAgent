# Phase 3: Voice Agent Backend - Research

**Researched:** 2026-03-12
**Domain:** Google ADK + Gemini Live API + FastAPI real-time voice agent
**Confidence:** HIGH

## Summary

Phase 3 builds the core voice agent (Sarah) that conducts qualification sales calls using Google's Agent Development Kit (ADK) with the Gemini Live API for bidirectional audio streaming. The architecture is: FastAPI server exposes a WebSocket endpoint -> ADK Runner manages the agent session -> Gemini `gemini-live-2.5-flash-native-audio` handles speech-to-speech conversation. Sarah's knowledge comes from 5 Firestore PDFs pre-loaded into the system instruction at call start.

The ADK framework (v1.26.0, latest) provides `Runner`, `LiveRequestQueue`, `RunConfig`, and `InMemorySessionService` for managing streaming voice sessions. The agent is defined as a Python `Agent` object with a system instruction (Sarah's persona + KB content), tools (for logging outcomes and updating lead profiles), and voice configuration (Aoede voice, British English). Audio flows bidirectionally: input at 16kHz PCM mono, output at 24kHz PCM mono. For Phase 3, the WebSocket serves a browser client directly (no Twilio yet -- that is Phase 6). Phase 4 builds the browser UI that connects to this WebSocket.

The decision to pre-load all KB content into the system prompt (~43K chars from 5 PDFs) is sound: Gemini's 128K context window easily accommodates this, and it avoids mid-call tool latency for knowledge retrieval. Tools are reserved for side-effect operations: updating lead profiles in Supabase, logging call outcomes, and the duration watchdog signal injection.

**Primary recommendation:** Use ADK's `Runner.run_live()` with `StreamingMode.BIDI` and `response_modalities=["AUDIO"]`, define Sarah as an `Agent` with pre-loaded KB in system instruction, expose a FastAPI WebSocket at `/ws/voice/{lead_id}`, implement tools for Supabase writes only, and use an asyncio timer for the 8.5-minute watchdog.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Sarah's personality:** Enthusiastic coach, high energy, motivational, Nigerian-aware (familiar with NYSC, Naira, local tech scene) but standard English, no Pidgin. Gently guided assertiveness.
- **AI disclosure:** Natural and brief -- "Hi [name], this is Sarah from Cloudboosta. Just so you know, I'm an AI assistant and this call is being recorded. I'd love to learn about your cloud career goals -- is now a good time?"
- **Qualification flow:** Conversational weaving, guided but adaptive. Must-have fields: role, experience_level, cloud_background, motivation. Recommend AFTER all fields gathered.
- **Recommendation style:** Personalized reasoning -- explain WHY this programme fits their background. Two programmes: Cloud Security (GBP1,200) and SRE & Platform Engineering (GBP1,800).
- **Objection handling:** Reactive only (wait for lead to raise concerns). Pre-load all 5 PDF contents into system instruction at call start. Two attempts with different angles. Use specific salary figures from PDFs.
- **Commitment ask:** Natural summary then direct ask. COMMITTED = explicit verbal yes. FOLLOW_UP = anything ambiguous. DECLINED = explicit no.
- **Duration watchdog:** Internal signal at 8.5 minutes. Sarah wraps up naturally without revealing the timer.
- **Knowledge base approach:** Pre-load all 5 PDF contents into Sarah's system instruction at call start. ~43K chars fits Gemini context. No mid-call tool calls for KB retrieval.

### Claude's Discretion
- Exact system instruction wording and prompt engineering for Sarah's persona
- ADK agent framework structure and tool bindings
- How the duration watchdog is technically implemented (timer thread, async callback, etc.)
- Gemini session configuration (temperature, safety settings, audio format)
- How outcome validation works (Gemini validates against full conversation context)
- FastAPI route structure for the agent endpoint

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CALL-01 | Voice agent calls leads via Twilio from US number, powered by Gemini Live API with real-time audio streaming | ADK Runner.run_live() with StreamingMode.BIDI provides bidirectional audio. Note: Twilio integration is Phase 6 -- Phase 3 builds the agent backend that Phase 6 will connect to. |
| CALL-02 | Sarah discloses she is AI in the opening and mentions call recording | System instruction includes mandatory AI disclosure as first conversation action. Locked wording from CONTEXT.md. |
| CALL-03 | Sarah qualifies leads using conversation-sequence PDF decision tree (role, experience, cloud background, motivation) | conversation-sequence.pdf pre-loaded into system instruction. Agent tools update lead profile fields in Supabase as gathered. |
| CALL-04 | Sarah recommends Cloud Security or SRE & Platform Engineering based on qualification | programmes.pdf pre-loaded. Recommendation logic encoded in system instruction after conversation-sequence decision tree. |
| CALL-05 | Sarah handles objections using knowledge base PDFs | All 5 PDFs pre-loaded into system instruction (~43K chars within 128K context). objection-handling.pdf provides specific responses and salary figures. |
| CALL-06 | Call outcome determined by commitment ask + Gemini validation (COMMITTED / FOLLOW_UP / DECLINED) | Outcome determination tool called by agent at conversation end. Gemini validates against full conversation context via system instruction rules. |
| CALL-08 | Target 5-10 min duration with watchdog triggering wrap-up at 8.5 min | asyncio timer injects context signal into LiveRequestQueue at 8.5 minutes. Agent instruction specifies wrap-up behavior on this signal. |
| CALL-10 | Sarah asks lead when to follow up (lead-determined timing) | System instruction includes follow-up timing question for FOLLOW_UP outcomes. Tool captures follow_up_date preference. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | >=1.26.0 | Agent framework -- Agent, Runner, LiveRequestQueue, RunConfig | Official Google agent framework optimized for Gemini. Handles streaming, tools, session state. |
| google-genai | >=1.66.0 | Gemini API types -- Content, Part, Blob, SpeechConfig, types | Underlying SDK for Gemini API types used by ADK. Required dependency. |
| google-cloud-firestore | >=2.19.0 | Firestore client for KB pre-loading | Already in requirements.txt. Reads knowledge_base collection at call start. |
| fastapi | >=0.115.0 | HTTP + WebSocket server | Already in main.py. Add WebSocket routes for voice streaming. |
| uvicorn | >=0.34.0 | ASGI server | Already in Dockerfile CMD. |
| httpx | >=0.28.0 | Async HTTP for Supabase REST calls | Already in logger.py. Used for lead profile updates. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| audioop-lts | >=0.2.1 | mulaw <-> PCM conversion | Phase 6 (Twilio). Already in requirements.txt. Not needed for Phase 3 browser audio. |
| soxr | >=0.5.0 | High-quality audio resampling (8kHz <-> 16kHz <-> 24kHz) | Phase 6 (Twilio audio format conversion). Add to requirements.txt. |
| python-dotenv | >=1.0.1 | Environment variable loading | Already in requirements.txt. |
| google-auth | >=2.0.0 | GCP service account authentication | Already in requirements.txt. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ADK Agent framework | Raw google-genai live.connect() | ADK provides session management, tool integration, state, event loop -- hand-rolling would duplicate all of this |
| Pre-loading KB into system prompt | Runtime Firestore tool calls | Pre-loading eliminates latency during conversation. 43K chars is well within 128K context. Locked decision. |
| InMemorySessionService | Database-backed session service | In-memory is sufficient for single-instance voice calls. No session persistence needed across restarts. |

**Installation:**
```bash
pip install "google-adk>=1.26.0" "google-genai>=1.66.0" soxr
```

Note: Update `requirements.txt` to pin `google-adk>=1.26.0` (currently `>=0.3.0` is stale) and `google-genai>=1.66.0` (currently `>=1.56.0`). Add `soxr>=0.5.0` for Phase 6 preparation.

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── agent.py               # ADK Agent definition (Sarah persona, tools list)
├── tools.py               # Function tools (update_lead_profile, determine_outcome, log_event_tool)
├── voice_handler.py       # FastAPI WebSocket + ADK Runner streaming loop
├── knowledge_loader.py    # NEW: Firestore KB pre-loader, builds system instruction
├── call_manager.py        # NEW: Call state management, duration watchdog, outcome processing
├── main.py                # FastAPI app with WebSocket route registration
├── config.py              # Existing config dataclass
├── logger.py              # Existing pipeline_logs writer
└── requirements.txt       # Updated versions
```

### Pattern 1: ADK Streaming Agent with FastAPI WebSocket
**What:** FastAPI WebSocket endpoint receives browser audio, pipes to ADK Runner, streams responses back.
**When to use:** This is THE pattern for Phase 3.
**Example:**
```python
# voice_handler.py
# Source: ADK streaming docs + ADK+Twilio reference architecture
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def handle_voice_session(
    websocket: WebSocket,
    lead_id: str,
    runner: Runner,
    session_service: InMemorySessionService,
) -> None:
    await websocket.accept()

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"  # British English female
                )
            ),
            language_code="en-GB",
        ),
    )

    session = await session_service.create_session(
        app_name="cloudboosta-voice-agent",
        user_id=lead_id,
        session_id=f"call-{lead_id}",
    )

    live_request_queue = LiveRequestQueue()

    async def upstream_audio():
        """Receive PCM audio from browser WebSocket -> send to agent."""
        try:
            while True:
                data = await websocket.receive_bytes()
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=data,
                )
                live_request_queue.send_realtime(audio_blob)
        except WebSocketDisconnect:
            pass

    async def downstream_audio():
        """Receive agent audio events -> send to browser WebSocket."""
        async for event in runner.run_live(
            user_id=lead_id,
            session_id=f"call-{lead_id}",
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            # Send audio data to browser
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.inline_data and part.inline_data.data:
                        await websocket.send_bytes(part.inline_data.data)

            # Capture transcriptions for call_logs
            if event.input_transcription and event.input_transcription.text:
                pass  # Accumulate user transcript
            if event.output_transcription and event.output_transcription.text:
                pass  # Accumulate agent transcript

    try:
        await asyncio.gather(
            upstream_audio(),
            downstream_audio(),
            return_exceptions=True,
        )
    finally:
        live_request_queue.close()
```

### Pattern 2: Pre-loaded Knowledge Base System Instruction
**What:** Fetch all 5 Firestore KB documents at call start, concatenate into system instruction.
**When to use:** Every call initialization.
**Example:**
```python
# knowledge_loader.py
# Source: CONTEXT.md locked decision + Firestore seeding from Phase 2
from google.cloud import firestore

KB_DOCS = [
    "programmes",
    "conversation-sequence",
    "faqs",
    "payment-details",
    "objection-handling",
]

async def load_knowledge_base(db: firestore.AsyncClient) -> str:
    """Fetch all KB docs from Firestore and return concatenated content."""
    sections = []
    for doc_id in KB_DOCS:
        doc = await db.collection("knowledge_base").document(doc_id).get()
        if doc.exists:
            content = doc.to_dict().get("content", "")
            sections.append(f"## {doc_id.replace('-', ' ').title()}\n\n{content}")
    return "\n\n---\n\n".join(sections)


def build_system_instruction(lead_name: str, kb_content: str) -> str:
    """Build complete system instruction with persona + KB + rules."""
    return f"""You are Sarah, an AI sales assistant for Cloudboosta...

[LEAD NAME: {lead_name}]

[KNOWLEDGE BASE - USE THIS FOR ALL PROGRAMME AND PRICING INFORMATION]
{kb_content}

[CONVERSATION RULES]
...
"""
```

### Pattern 3: ADK Function Tools with ToolContext
**What:** Define plain Python functions as agent tools. ADK auto-generates schema from signatures + docstrings.
**When to use:** For side-effect operations during the call (Supabase writes, outcome logging).
**Example:**
```python
# tools.py
# Source: ADK function-tools docs
from google.adk.tools import ToolContext

def update_lead_profile(
    role: str,
    experience_level: str,
    cloud_background: str,
    motivation: str,
    tool_context: ToolContext,
) -> dict:
    """Update the lead's qualification profile in the database.

    Call this after gathering all four qualification fields from the lead.

    Args:
        role: The lead's current job role or title.
        experience_level: junior, mid, senior, or career-changer.
        cloud_background: Description of their cloud/DevOps experience.
        motivation: Why they want cloud training.
    """
    lead_id = tool_context.state.get("lead_id")
    # Queue async Supabase update (non-blocking)
    tool_context.state["qualification"] = {
        "role": role,
        "experience_level": experience_level,
        "cloud_background": cloud_background,
        "motivation": motivation,
    }
    return {"status": "success", "message": "Lead profile updated"}


def determine_call_outcome(
    outcome: str,
    recommended_programme: str,
    qualification_summary: str,
    objections_raised: list[str],
    follow_up_preference: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Record the final outcome of the sales call.

    Call this at the very end of the conversation, after the commitment ask.

    Args:
        outcome: Must be one of COMMITTED, FOLLOW_UP, or DECLINED.
        recommended_programme: The programme recommended (cloud-security or sre-platform-engineering).
        qualification_summary: Brief summary of the lead's qualification.
        objections_raised: List of objections raised during the call.
        follow_up_preference: When the lead prefers follow-up (only for FOLLOW_UP outcome).
    """
    if outcome not in ("COMMITTED", "FOLLOW_UP", "DECLINED"):
        return {"status": "error", "message": f"Invalid outcome: {outcome}"}

    tool_context.state["call_outcome"] = {
        "outcome": outcome,
        "recommended_programme": recommended_programme,
        "qualification_summary": qualification_summary,
        "objections_raised": objections_raised,
        "follow_up_preference": follow_up_preference,
    }
    return {"status": "success", "outcome": outcome}
```

### Pattern 4: Duration Watchdog via asyncio
**What:** Async timer that injects a wrap-up signal into the LiveRequestQueue at 8.5 minutes.
**When to use:** Every voice session.
**Example:**
```python
# call_manager.py
import asyncio
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

WATCHDOG_SECONDS = 8.5 * 60  # 510 seconds

async def duration_watchdog(
    live_request_queue: LiveRequestQueue,
    timeout_seconds: float = WATCHDOG_SECONDS,
) -> None:
    """Inject wrap-up signal into agent context after timeout."""
    await asyncio.sleep(timeout_seconds)
    # Send a system-level text content that instructs wrap-up
    wrap_up_signal = types.Content(
        role="user",
        parts=[types.Part(text=(
            "[INTERNAL SYSTEM SIGNAL - DO NOT READ ALOUD] "
            "The call has reached 8.5 minutes. Begin wrapping up naturally. "
            "Summarize what was discussed, make your recommendation if not done, "
            "ask for commitment, and close the call gracefully. "
            "Do not mention this timer to the lead."
        ))],
    )
    live_request_queue.send_content(wrap_up_signal)
```

### Anti-Patterns to Avoid
- **Mid-call Firestore reads for KB:** Adds 100-300ms latency per query during live voice conversation. Pre-load everything at call start.
- **Hardcoded programme details in system instruction:** If pricing changes, you must redeploy. Read from Firestore at call start so KB updates take effect immediately.
- **Blocking tool execution during audio:** Use `"behavior": "NON_BLOCKING"` for tools that write to Supabase so the conversation continues while the write completes.
- **Single-threaded audio processing:** The upstream (receive from client) and downstream (send from agent) MUST run as concurrent async tasks via `asyncio.gather()`.
- **Missing transcription capture:** Always enable `input_audio_transcription` and `output_audio_transcription` in RunConfig. The transcript is needed for call_logs and outcome validation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent session management | Custom session state tracker | ADK `InMemorySessionService` + `Runner` | Handles session creation, state persistence, cleanup automatically |
| Voice activity detection | Custom silence detector | Gemini Live API built-in VAD | Automatic turn-taking with configurable sensitivity. Already tuned for voice conversations. |
| Speech-to-text / text-to-speech | Separate STT + TTS pipeline | Gemini native audio model | Single model handles audio-in -> audio-out directly. Adding STT/TTS pipeline adds 200-500ms latency. |
| Tool schema generation | Manual JSON schema for tools | ADK function tool auto-schema from Python signatures | ADK inspects function name, docstring, parameter types, default values automatically |
| Audio transcription | Whisper / separate transcription | ADK `AudioTranscriptionConfig` in RunConfig | Gemini provides input + output transcriptions natively during streaming |
| Context window management | Manual token counting + truncation | Gemini `contextWindowCompression` with SlidingWindow | Built-in sliding window truncates oldest turns when context fills. Keeps system instruction intact. |

**Key insight:** ADK + Gemini Live API handles the entire audio pipeline (VAD, STT, response generation, TTS) in a single model call. Adding any external component to this pipeline increases latency and complexity without benefit.

## Common Pitfalls

### Pitfall 1: Stale ADK Version in requirements.txt
**What goes wrong:** The current `requirements.txt` pins `google-adk>=0.3.0` -- this is extremely old. ADK is now at v1.26.0 with breaking API changes from 0.x.
**Why it happens:** requirements.txt was created during project setup before Phase 3 implementation.
**How to avoid:** Update to `google-adk>=1.26.0` before any implementation. The import paths, class names, and streaming API have changed significantly since 0.3.
**Warning signs:** `ImportError`, `AttributeError`, or missing classes like `LiveRequestQueue` or `StreamingMode`.

### Pitfall 2: System Instruction Too Long
**What goes wrong:** If the system instruction (persona + KB content + rules) exceeds ~60K tokens, it consumes too much of the 128K context window, leaving insufficient room for the conversation itself.
**Why it happens:** 5 PDFs at ~43K chars plus persona instructions plus conversation rules.
**How to avoid:** Measure total system instruction length. The 5 KB documents are ~43K chars (~10-12K tokens). Persona + rules add another ~3-5K chars (~1-2K tokens). Total ~14K tokens -- well within limits. But monitor if PDFs grow.
**Warning signs:** Conversations cut short, context window compression kicking in too early.

### Pitfall 3: Audio Format Mismatch (Phase 6 Preparation)
**What goes wrong:** Gemini expects 16kHz PCM input and outputs 24kHz PCM. Browser MediaRecorder may send different formats. Twilio sends mulaw 8kHz.
**Why it happens:** Each system uses different audio standards.
**How to avoid:** For Phase 3 (browser), ensure the browser client sends 16kHz PCM 16-bit mono. For Phase 6 (Twilio), use audioop for mulaw conversion and soxr for resampling.
**Warning signs:** Garbled audio, silence, or "I can't understand you" responses from Sarah.

### Pitfall 4: WebSocket Cleanup on Disconnect
**What goes wrong:** If the browser disconnects abruptly (tab close, network drop), the ADK session and asyncio tasks leak.
**Why it happens:** `WebSocketDisconnect` exception only fires in the receiving task; the other task keeps running.
**How to avoid:** Use `asyncio.gather()` with `return_exceptions=True` and always call `live_request_queue.close()` in a `finally` block. Also write call outcome to Supabase on abnormal disconnects.
**Warning signs:** Memory leaks, orphaned Gemini sessions consuming API quota.

### Pitfall 5: Tool Call Blocking Audio Stream
**What goes wrong:** When Sarah calls a tool (update_lead_profile, determine_outcome), the audio stream pauses while waiting for the tool response.
**Why it happens:** Default tool execution is synchronous/blocking in the Live API.
**How to avoid:** Keep tool implementations fast (<100ms). For Supabase writes, queue the write and return immediately. Use `NON_BLOCKING` behavior in ADK tool configuration if available, or make the tool return instantly while queueing the actual write.
**Warning signs:** Noticeable pauses in conversation when Sarah says "let me note that down."

### Pitfall 6: Missing Outcome on Abnormal Call End
**What goes wrong:** If the lead hangs up before Sarah calls `determine_call_outcome`, no outcome is recorded.
**Why it happens:** The tool-based outcome determination relies on the conversation reaching its natural end.
**How to avoid:** In the session cleanup handler, check if an outcome was recorded. If not, either infer from transcript or record as "CALL_DROPPED" with the partial transcript.
**Warning signs:** call_logs entries with NULL outcome.

### Pitfall 7: Gemini Session 10-Minute Default Limit
**What goes wrong:** Gemini Live API sessions default to 10 minutes. The call could be cut off.
**Why it happens:** Default session configuration has a 10-minute limit.
**How to avoid:** The watchdog at 8.5 minutes should ensure calls wrap up before the limit. Additionally, enable context window compression and session extension if needed. The 10-minute default aligns well with the 5-10 minute target call duration.
**Warning signs:** Abrupt call termination at exactly 10 minutes.

## Code Examples

### Complete Agent Definition
```python
# agent.py
# Source: ADK docs + project CONTEXT.md decisions
from google.adk.agents import Agent
from google.genai import types

from tools import update_lead_profile, determine_call_outcome

def create_sarah_agent(system_instruction: str) -> Agent:
    """Create Sarah agent with pre-loaded KB in system instruction."""
    return Agent(
        name="Sarah",
        model="gemini-live-2.5-flash-native-audio",
        description="Cloudboosta AI sales agent for qualification calls",
        instruction=system_instruction,
        tools=[
            update_lead_profile,
            determine_call_outcome,
        ],
    )
```

### FastAPI WebSocket Route Registration
```python
# main.py additions
# Source: ADK streaming quickstart + FastAPI WebSocket docs
from fastapi import WebSocket
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()

@app.websocket("/ws/voice/{lead_id}")
async def voice_call(websocket: WebSocket, lead_id: str):
    # 1. Fetch lead from Supabase
    # 2. Load KB from Firestore
    # 3. Build system instruction with lead name + KB
    # 4. Create Agent with dynamic system instruction
    # 5. Create Runner
    # 6. Start streaming session with watchdog
    pass
```

### Supabase Lead Profile Update (async, non-blocking)
```python
# tools.py helper
# Source: Existing logger.py pattern
import httpx
from config import config

async def write_lead_profile_to_supabase(lead_id: str, profile: dict) -> None:
    """Non-blocking Supabase update for lead qualification fields."""
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{config.supabase_url}/rest/v1/leads?id=eq.{lead_id}",
            json=profile,
            headers={
                "apikey": config.supabase_service_key,
                "Authorization": f"Bearer {config.supabase_service_key}",
                "Content-Type": "application/json",
                "Content-Profile": "sales_agent",
                "Prefer": "return=minimal",
            },
            timeout=10,
        )
```

### Call Outcome Post-Processing
```python
# call_manager.py
# Source: CONTEXT.md decisions + directive 05
async def process_call_end(
    lead_id: str,
    outcome: dict,
    transcript: str,
    duration_seconds: int,
) -> None:
    """Write call results to Supabase and trigger post-call webhook."""
    # 1. Write to call_logs table
    call_log = {
        "lead_id": lead_id,
        "status": "completed",
        "outcome": outcome.get("outcome", "UNKNOWN"),
        "transcript": transcript,
        "qualification_summary": outcome.get("qualification_summary", ""),
        "recommended_programme": outcome.get("recommended_programme", ""),
        "objections_raised": outcome.get("objections_raised", []),
        "duration_seconds": duration_seconds,
    }
    # 2. Update lead status in leads table
    # 3. Log to pipeline_logs
    # 4. POST to n8n webhook (Phase 8 integration point)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-adk 0.x with manual live.connect() | google-adk 1.x with Runner.run_live() + LiveRequestQueue | 2025 H2 | Complete rewrite of streaming API. Runner handles session lifecycle. |
| google-generativeai (old SDK) | google-genai (new unified SDK) | 2025 | New package name, new import paths. ADK depends on google-genai. |
| Text-only agents with separate STT/TTS | Native audio models (gemini-live-2.5-flash-native-audio) | 2025 Q4 | Single model does audio-in -> audio-out. 30 HD voices, 24 languages. |
| Manual VAD with silence detection | Built-in automatic voice activity detection | 2025 | Configurable sensitivity, natural turn-taking without custom code. |
| Per-query Firestore tool calls | Pre-loaded KB in system instruction | Project decision | Eliminates per-query latency. KB changes require new call to take effect. |

**Deprecated/outdated:**
- `google-generativeai` package: Replaced by `google-genai`. Do not use.
- `google-adk` 0.x API: `client.aio.live.connect()` pattern from skills.md is for raw SDK, not ADK. Use ADK's Runner instead.
- `gemini-2.0-flash-live` model name in AGENT.md: Updated to `gemini-live-2.5-flash-native-audio` (GA model).
- `gemini-live-2.5-flash-preview-native-audio-09-2025`: Deprecated, removal March 19, 2026.

## Open Questions

1. **Exact Voice Name Availability on Vertex AI**
   - What we know: Aoede is listed as available for both half-cascade and native audio models. 30 HD voices available.
   - What's unclear: Whether all 30 voices are available via Vertex AI in europe-west1, or only a subset.
   - Recommendation: Use Aoede (British English female) as specified in skills.md. Test during implementation. Fall back to Kore or Leda if Aoede unavailable.

2. **ADK Tool Execution Model in Live Sessions**
   - What we know: Tools defined as Python functions are auto-wrapped. Live API tool responses must be sent manually (not auto-handled).
   - What's unclear: Whether ADK's Runner abstracts the manual `send_tool_response()` call, or if we need to handle it ourselves.
   - Recommendation: Test with a simple tool first. ADK Runner likely handles this internally based on the function tool abstraction, but verify.

3. **Watchdog Signal Injection**
   - What we know: `LiveRequestQueue.send_content()` can inject text content into the session.
   - What's unclear: Whether injecting a "user" role message works as a system-level signal, or if we need a different approach (e.g., modifying session state).
   - Recommendation: Test sending a user-role content with `[INTERNAL SYSTEM SIGNAL]` prefix. The system instruction should tell Sarah to watch for this and not read it aloud. Alternative: use `tool_context.state` update if tools are checked periodically.

4. **Concurrent Call Handling**
   - What we know: Each WebSocket connection creates its own Runner instance, session, and LiveRequestQueue.
   - What's unclear: Whether InMemorySessionService handles concurrent sessions across multiple WebSocket connections correctly.
   - Recommendation: Each call should use a unique session_id (e.g., `call-{lead_id}-{timestamp}`). Test with 2 concurrent browser sessions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | None -- Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CALL-01 | Agent backend creates and runs a voice session | integration | `pytest tests/test_voice_session.py::test_session_creation -x` | No -- Wave 0 |
| CALL-02 | System instruction includes AI disclosure text | unit | `pytest tests/test_system_instruction.py::test_ai_disclosure -x` | No -- Wave 0 |
| CALL-03 | System instruction includes qualification decision tree from KB | unit | `pytest tests/test_system_instruction.py::test_qualification_fields -x` | No -- Wave 0 |
| CALL-04 | System instruction includes both programme details from KB | unit | `pytest tests/test_system_instruction.py::test_programme_recommendation -x` | No -- Wave 0 |
| CALL-05 | All 5 KB documents loaded into system instruction | unit | `pytest tests/test_knowledge_loader.py::test_kb_preload -x` | No -- Wave 0 |
| CALL-06 | determine_call_outcome tool validates outcome values | unit | `pytest tests/test_tools.py::test_outcome_determination -x` | No -- Wave 0 |
| CALL-08 | Duration watchdog fires at 8.5 minutes | unit | `pytest tests/test_call_manager.py::test_watchdog_timing -x` | No -- Wave 0 |
| CALL-10 | determine_call_outcome captures follow_up_preference | unit | `pytest tests/test_tools.py::test_follow_up_preference -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` -- shared fixtures (mock Firestore, mock Supabase, mock ADK session)
- [ ] `tests/test_system_instruction.py` -- covers CALL-02, CALL-03, CALL-04
- [ ] `tests/test_knowledge_loader.py` -- covers CALL-05
- [ ] `tests/test_tools.py` -- covers CALL-06, CALL-10
- [ ] `tests/test_call_manager.py` -- covers CALL-08
- [ ] `tests/test_voice_session.py` -- covers CALL-01 (integration, may need mock ADK runner)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` -- pytest config with asyncio_mode=auto
- [ ] Framework install: `pip install pytest pytest-asyncio pytest-mock`

## Sources

### Primary (HIGH confidence)
- [ADK Streaming Quickstart](https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/) -- Agent definition, streaming setup
- [ADK Gemini Live API Toolkit](https://google.github.io/adk-docs/streaming/) -- Overview of streaming capabilities
- [ADK Streaming Dev Guide Part 1](https://google.github.io/adk-docs/streaming/dev-guide/part1/) -- Runner, LiveRequestQueue, RunConfig, FastAPI WebSocket pattern
- [ADK Streaming Dev Guide Part 5](https://google.github.io/adk-docs/streaming/dev-guide/part5/) -- Audio format specs, voice config, VAD, transcription
- [ADK Function Tools](https://google.github.io/adk-docs/tools-custom/function-tools/) -- Tool signature requirements, ToolContext, return format
- [ADK Custom Tools Overview](https://google.github.io/adk-docs/tools-custom/) -- ToolContext state management, flow control
- [Gemini 2.5 Flash Live API on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-live-api) -- Model name, regions, constraints, audio specs
- [ADK with Vertex AI Setup](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/get-started-adk) -- Vertex AI env vars, authentication
- [ADK Gemini Models](https://google.github.io/adk-docs/agents/models/google-gemini/) -- Model configuration, Vertex AI auth methods

### Secondary (MEDIUM confidence)
- [ADK + Twilio Phone Agent (DEV.to)](https://dev.to/julian-hecker/building-a-realtime-phone-agent-with-adk-and-twilio-12a3) -- Complete reference architecture, audio conversion pipeline, concurrent task pattern
- [Tool Use with Live API](https://ai.google.dev/gemini-api/docs/live-api/tools) -- Function calling behavior, NON_BLOCKING tools, scheduling
- [Gemini Live API Overview](https://ai.google.dev/gemini-api/docs/live-api) -- Session management, context window compression

### Tertiary (LOW confidence)
- [google-adk v1.26.0 on PyPI](https://pypi.org/project/google-adk/) -- Version confirmed via search, not directly verified on PyPI page
- [google-genai v1.66.0 on PyPI](https://pypi.org/project/google-genai/) -- Version confirmed via search

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- ADK docs are official, model names verified against Vertex AI docs, patterns from official dev guides
- Architecture: HIGH -- FastAPI WebSocket + ADK Runner pattern is documented in official ADK streaming guides and verified by community reference implementations
- Pitfalls: HIGH -- Audio format specs confirmed in official docs, session limits confirmed, version issues verified against PyPI
- Tools: MEDIUM -- ToolContext behavior in live sessions specifically is not extensively documented; the ADK+Twilio reference validates the overall pattern but tool execution model during live sessions needs implementation verification

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (ADK releases bi-weekly, but core streaming API is stable)

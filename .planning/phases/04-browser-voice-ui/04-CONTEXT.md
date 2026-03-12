# Phase 4: Browser Voice UI - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a polished React voice interface that connects to the backend WebSocket (`/ws/voice/{lead_id}`), captures microphone audio as PCM 16kHz, plays Sarah's audio responses, handles barge-in (interruption), shows real-time connection status, audio activity visualization, call duration timer, and live transcript -- ready for the competition demo video. Twilio phone integration and Cloud Run deployment are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Call Screen Layout & Visual Style
- Split-panel dashboard: call controls on the left, live transcript on the right
- Dark professional theme (#1a1a2e or similar dark background, light text, accent colors for status)
- No branding header -- full screen dedicated to the call interface
- Sarah avatar with name ("Sarah -- AI Sales Agent") displayed in the left panel with circular avatar/icon
- Basic responsive: panels stack vertically on mobile, optimized for 1280px+ desktop
- Three UI states: pre-call (lead selection + info preview), active call (split-panel), post-call (summary card)
- Pre-call screen: lead info preview (name, phone, email) with large green "Start Call" button below. Button disabled until lead selected
- Post-call screen: summary card showing call duration, outcome (COMMITTED/FOLLOW_UP/DECLINED), and recommended programme
- Post-call outcome data fetched via a new backend REST endpoint (GET /api/call/{lead_id}/latest) after WebSocket closes

### Audio Visualization
- Pulsing concentric circles style for "who is speaking" indicators
- Two circles in left panel, stacked vertically: Sarah's circle above (larger, with avatar), user's circle below (smaller)
- Colors: blue for user, green for Sarah -- high contrast on dark background
- Audio data source: Web Audio API (AudioContext + AnalyserNode) for real microphone amplitude (user) and decoded incoming PCM bytes amplitude (Sarah)

### Lead Selection & Call Initiation
- Dropdown populated from Supabase via new backend proxy endpoint (GET /api/leads) -- keeps Supabase credentials server-side
- Dropdown shows lead name + phone, with last call outcome status next to each lead (e.g., "John - COMMITTED")
- Microphone permission requested on "Start Call" click, not on page load
- WebSocket URL auto-detected from page URL (same-origin): if page at https://example.com, connect to wss://example.com/ws/voice/{id}
- Vite proxy config for development: /ws/* and /api/* forward to localhost:8000
- No re-call guard -- any lead can be called anytime (test phase with 10 leads)

### Live Transcript Display
- Backend sends JSON transcript events on the same WebSocket (text messages for transcript, binary messages for audio)
- Modify voice_handler.py to emit {type: "transcript", speaker: "agent"|"user", text: "..."} JSON messages
- Chat-style speech bubbles in the right panel: Sarah's bubbles on left (green tint), user's bubbles on right (blue tint)
- Streaming word-by-word display as Gemini transcribes -- text appears progressively
- Auto-scroll to latest message
- Simple "Transcript" header at top of right panel

### Claude's Discretion
- Exact CSS implementation (inline styles, CSS modules, or a utility approach)
- AudioWorklet vs ScriptProcessorNode for microphone capture
- PCM encoding/decoding implementation details
- Barge-in technical implementation (how to flush audio buffers when user speaks)
- Exact avatar design (SVG icon, initials, or placeholder image)
- Loading states and error handling UX
- Animation timing and easing for pulsing circles

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/VoiceAgent.jsx`: Stub component ready for implementation
- `frontend/src/App.jsx`: Stub app shell ready for implementation
- `frontend/src/index.jsx`: React 19 entry point with createRoot -- no changes needed
- `frontend/package.json`: React 19 + Vite 6 already configured. No CSS framework, no audio libs yet
- `frontend/Dockerfile`: Multi-stage build (node:22-alpine -> nginx:alpine) ready for Phase 5
- `backend/main.py`: FastAPI with CORS, health check, and WebSocket route at `/ws/voice/{lead_id}`
- `backend/voice_handler.py`: Full WebSocket handler -- accepts connection, fetches lead, loads KB, streams audio bidirectionally. Captures transcription events server-side but doesn't forward them to client yet

### Established Patterns
- Backend uses httpx async for Supabase REST calls with Accept-Profile: sales_agent header
- WebSocket sends/receives raw PCM 16kHz bytes (audio/pcm;rate=16000)
- ADK Runner emits input_transcription and output_transcription events with .text property
- FastAPI CORS allows all origins (tightened in production)
- Config loaded from environment via python-dotenv

### Integration Points
- WebSocket endpoint: `/ws/voice/{lead_id}` -- sends binary PCM audio, needs to also send JSON transcript events
- New REST endpoints needed: GET /api/leads (list leads with status), GET /api/call/{lead_id}/latest (post-call summary)
- Vite dev server needs proxy config to forward /ws/* and /api/* to FastAPI on :8000
- voice_handler.py needs modification: forward transcript events as JSON text messages to WebSocket client

</code_context>

<specifics>
## Specific Ideas

- The split-panel layout lets competition judges see the qualification flow happening in real-time via the transcript while hearing the audio conversation
- Chat bubbles should feel like a modern messaging app (WhatsApp/iMessage style) with the dark theme
- Pulsing circles create a visual "heartbeat" effect that makes the AI feel alive during the demo
- The pre-call -> active call -> post-call flow creates a clear narrative arc for the demo video

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-browser-voice-ui*
*Context gathered: 2026-03-12*

# Phase 4: Browser Voice UI - Research

**Researched:** 2026-03-12
**Domain:** React 19 + Web Audio API + WebSocket binary audio streaming
**Confidence:** HIGH

## Summary

Phase 4 builds a polished React voice interface that connects to the existing FastAPI WebSocket endpoint (`/ws/voice/{lead_id}`), captures microphone audio as PCM 16kHz, plays back Gemini's audio responses (PCM 24kHz), handles barge-in interruption, shows audio visualization, and displays a live transcript -- all styled with a dark professional theme for the competition demo video.

The existing backend sends raw binary PCM bytes from Gemini Live API (24kHz output) and receives raw binary PCM (16kHz input). The backend currently only captures transcripts server-side but does NOT forward them to the client -- this must be modified to send JSON text messages on the same WebSocket alongside binary audio. Two new REST endpoints (GET /api/leads, GET /api/call/{lead_id}/latest) must also be added to the backend. The frontend uses React 19 + Vite 6 with no CSS framework -- CSS Modules are recommended for scoped styling.

**Primary recommendation:** Use AudioWorklet for both microphone capture (16kHz PCM) and audio playback (24kHz PCM) with ring buffer pattern. No third-party audio libraries needed. CSS Modules for styling. No additional React dependencies required beyond what's already in package.json.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Split-panel dashboard: call controls on the left, live transcript on the right
- Dark professional theme (#1a1a2e or similar dark background, light text, accent colors for status)
- No branding header -- full screen dedicated to the call interface
- Sarah avatar with name ("Sarah -- AI Sales Agent") displayed in the left panel with circular avatar/icon
- Basic responsive: panels stack vertically on mobile, optimized for 1280px+ desktop
- Three UI states: pre-call (lead selection + info preview), active call (split-panel), post-call (summary card)
- Pre-call screen: lead info preview (name, phone, email) with large green "Start Call" button below. Button disabled until lead selected
- Post-call screen: summary card showing call duration, outcome (COMMITTED/FOLLOW_UP/DECLINED), and recommended programme
- Post-call outcome data fetched via a new backend REST endpoint (GET /api/call/{lead_id}/latest) after WebSocket closes
- Pulsing concentric circles style for "who is speaking" indicators
- Two circles in left panel, stacked vertically: Sarah's circle above (larger, with avatar), user's circle below (smaller)
- Colors: blue for user, green for Sarah -- high contrast on dark background
- Dropdown populated from Supabase via new backend proxy endpoint (GET /api/leads) -- keeps Supabase credentials server-side
- Dropdown shows lead name + phone, with last call outcome status next to each lead
- Microphone permission requested on "Start Call" click, not on page load
- WebSocket URL auto-detected from page URL (same-origin)
- Vite proxy config for development: /ws/* and /api/* forward to localhost:8000
- No re-call guard -- any lead can be called anytime
- Backend sends JSON transcript events on the same WebSocket (text messages for transcript, binary messages for audio)
- Modify voice_handler.py to emit {type: "transcript", speaker: "agent"|"user", text: "..."} JSON messages
- Chat-style speech bubbles in the right panel: Sarah's bubbles on left (green tint), user's bubbles on right (blue tint)
- Streaming word-by-word display as Gemini transcribes
- Auto-scroll to latest message

### Claude's Discretion
- Exact CSS implementation (inline styles, CSS modules, or a utility approach)
- AudioWorklet vs ScriptProcessorNode for microphone capture
- PCM encoding/decoding implementation details
- Barge-in technical implementation (how to flush audio buffers when user speaks)
- Exact avatar design (SVG icon, initials, or placeholder image)
- Loading states and error handling UX
- Animation timing and easing for pulsing circles

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPL-03 | Browser voice UI (React) for testing Sarah without Twilio credits | Full frontend implementation: WebSocket audio streaming, microphone capture, PCM playback, lead selection via REST proxy, call lifecycle management |
| COMP-01 | Natural interruption handling -- user can speak while Sarah is talking and Sarah stops immediately (barge-in), browser stops playing buffered audio | AudioWorklet ring buffer with `endOfAudio` command to flush playback buffer instantly when user speech detected; voice activity detection via AnalyserNode amplitude threshold |
| COMP-02 | Audio activity visualization in browser UI showing when user and agent are speaking | AnalyserNode for microphone amplitude, incoming PCM byte amplitude calculation for Sarah, pulsing concentric circles animated via requestAnimationFrame |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.0.0 | UI framework | Already in package.json, latest stable |
| React DOM | ^19.0.0 | DOM rendering | Already in package.json |
| Vite | ^6.2.0 | Build tool + dev server | Already in devDependencies, handles proxy config |
| @vitejs/plugin-react | ^4.3.0 | JSX/React transform for Vite | Already in devDependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Web Audio API (browser) | N/A | Microphone capture + audio playback | Core audio infrastructure -- no npm package needed |
| WebSocket API (browser) | N/A | Bidirectional audio + transcript streaming | Built-in browser API -- no npm package needed |
| CSS Modules (Vite built-in) | N/A | Scoped component styles | Vite supports *.module.css natively -- zero config |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AudioWorklet | ScriptProcessorNode | ScriptProcessorNode deprecated since Chrome 64. AudioWorklet runs on audio thread (no UI jank). Use AudioWorklet. |
| CSS Modules | Tailwind CSS | Tailwind adds build config, learning curve, and 30KB+ for 6 components. CSS Modules are zero-config in Vite. |
| pcm-player npm | Custom AudioWorklet player | pcm-player uses deprecated ScriptProcessorNode internally. Custom AudioWorklet player is ~30 lines and better. |
| react-use-websocket | Native WebSocket | The package adds abstraction over a simple connection. We need precise control over binary frames. Use native WebSocket. |

**Installation:**
```bash
# No new packages needed! Everything is already in package.json or built into the browser.
cd frontend && npm install
```

**Dev dependencies for testing (if adding tests):**
```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── index.html                          # Vite entry point (MUST CREATE)
├── vite.config.js                      # Proxy config for /ws/* and /api/* (MUST CREATE)
├── package.json                        # Already exists
├── Dockerfile                          # Already exists (multi-stage nginx)
└── src/
    ├── index.jsx                       # Already exists (createRoot)
    ├── App.jsx                         # Root component -- state machine (pre-call/active/post-call)
    ├── App.module.css                  # Root layout styles
    ├── components/
    │   ├── PreCallScreen.jsx           # Lead dropdown + info preview + Start Call button
    │   ├── PreCallScreen.module.css
    │   ├── ActiveCallScreen.jsx        # Split-panel: left (controls+viz) + right (transcript)
    │   ├── ActiveCallScreen.module.css
    │   ├── PostCallScreen.jsx          # Summary card with outcome
    │   ├── PostCallScreen.module.css
    │   ├── AudioVisualizer.jsx         # Pulsing concentric circles component
    │   ├── AudioVisualizer.module.css
    │   ├── TranscriptPanel.jsx         # Chat bubbles with auto-scroll
    │   └── TranscriptPanel.module.css
    ├── hooks/
    │   ├── useVoiceSession.js          # WebSocket connection + audio pipeline orchestration
    │   └── useAudioVisualization.js    # AnalyserNode + requestAnimationFrame loop
    ├── audio/
    │   ├── pcm-recorder-processor.js   # AudioWorklet: mic capture -> Float32 -> PCM 16-bit
    │   └── pcm-player-processor.js     # AudioWorklet: PCM 24kHz -> ring buffer -> speakers
    └── utils/
        └── pcm.js                      # Float32<->Int16 conversion helpers
```

### Pattern 1: AudioWorklet for Microphone Capture (16kHz PCM)
**What:** Captures microphone audio at 16kHz, converts Float32 to Int16 PCM, sends as binary WebSocket frames.
**When to use:** Always -- this is the only non-deprecated approach.
**Example:**
```javascript
// Source: https://google.github.io/adk-docs/streaming/dev-guide/part5/

// pcm-recorder-processor.js (AudioWorklet - runs on audio thread)
class PCMRecorderProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    if (inputs[0] && inputs[0][0]) {
      this.port.postMessage(new Float32Array(inputs[0][0]));
    }
    return true;
  }
}
registerProcessor("pcm-recorder-processor", PCMRecorderProcessor);

// In React hook (main thread)
const audioCtx = new AudioContext({ sampleRate: 16000 });
await audioCtx.audioWorklet.addModule(
  new URL("../audio/pcm-recorder-processor.js", import.meta.url)
);
const stream = await navigator.mediaDevices.getUserMedia({
  audio: { channelCount: 1 }
});
const source = audioCtx.createMediaStreamSource(stream);
const recorder = new AudioWorkletNode(audioCtx, "pcm-recorder-processor");
source.connect(recorder);

recorder.port.onmessage = (e) => {
  const pcm16 = convertFloat32ToPCM16(e.data);
  ws.send(pcm16); // Binary frame
};
```

### Pattern 2: AudioWorklet for Playback (24kHz PCM Ring Buffer)
**What:** Receives binary PCM frames from WebSocket, buffers in ring buffer, plays through AudioContext at 24kHz.
**When to use:** Always for incoming Gemini audio.
**Example:**
```javascript
// Source: https://google.github.io/adk-docs/streaming/dev-guide/part5/

// pcm-player-processor.js (AudioWorklet - runs on audio thread)
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 24000 * 180; // 3 minutes max
    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;

    this.port.onmessage = (event) => {
      if (event.data.command === "clearBuffer") {
        // BARGE-IN: flush all buffered audio instantly
        this.readIndex = this.writeIndex;
        return;
      }
      const int16 = new Int16Array(event.data);
      for (let i = 0; i < int16.length; i++) {
        this.buffer[this.writeIndex] = int16[i] / 32768;
        this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
        if (this.writeIndex === this.readIndex) {
          this.readIndex = (this.readIndex + 1) % this.bufferSize;
        }
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0][0];
    for (let i = 0; i < output.length; i++) {
      output[i] = this.buffer[this.readIndex];
      if (this.readIndex !== this.writeIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }
    return true;
  }
}
registerProcessor("pcm-player-processor", PCMPlayerProcessor);
```

### Pattern 3: WebSocket Message Multiplexing (Binary + JSON on Same Connection)
**What:** The backend sends binary frames (audio) and JSON text frames (transcripts) on the same WebSocket. The frontend distinguishes by checking `typeof event.data`.
**When to use:** For all WebSocket message handling.
**Example:**
```javascript
// Frontend message handler
ws.binaryType = "arraybuffer";
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Binary frame = PCM audio from Sarah
    playerNode.port.postMessage(event.data);
    updateSarahAmplitude(event.data); // For visualization
  } else {
    // Text frame = JSON transcript or status event
    const msg = JSON.parse(event.data);
    if (msg.type === "transcript") {
      addTranscriptBubble(msg.speaker, msg.text);
    }
  }
};
```

### Pattern 4: Barge-In Detection + Buffer Flush
**What:** Detect when user starts speaking (via microphone amplitude threshold), immediately flush Sarah's playback buffer to stop her mid-sentence.
**When to use:** Implements COMP-01 natural interruption handling.
**Example:**
```javascript
// In the recorder's onmessage handler
recorder.port.onmessage = (e) => {
  const pcm16 = convertFloat32ToPCM16(e.data);
  ws.send(pcm16);

  // Voice activity detection via amplitude
  const amplitude = computeRMS(e.data);
  if (amplitude > VAD_THRESHOLD && isSarahSpeaking) {
    // Barge-in detected! Flush playback buffer
    playerNode.port.postMessage({ command: "clearBuffer" });
  }
};

function computeRMS(float32Array) {
  let sum = 0;
  for (let i = 0; i < float32Array.length; i++) {
    sum += float32Array[i] * float32Array[i];
  }
  return Math.sqrt(sum / float32Array.length);
}
```

### Pattern 5: React State Machine for UI States
**What:** Three distinct screens managed by a single state variable in App.jsx.
**When to use:** Core UI flow management.
**Example:**
```javascript
const [screen, setScreen] = useState("pre-call"); // "pre-call" | "active" | "post-call"
const [selectedLead, setSelectedLead] = useState(null);
const [callSummary, setCallSummary] = useState(null);

// Transitions:
// pre-call -> active: when "Start Call" clicked and WebSocket opens
// active -> post-call: when WebSocket closes, fetch summary from REST endpoint
// post-call -> pre-call: when "New Call" clicked
```

### Pattern 6: Vite Proxy Configuration for Development
**What:** Forward /ws/* and /api/* to the FastAPI backend on localhost:8000.
**When to use:** Development only. In production, nginx or Cloud Run handles routing.
**Example:**
```javascript
// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

### Anti-Patterns to Avoid
- **Creating AudioContext on page load:** Browser policy requires user gesture (click) before creating AudioContext. Create it inside the "Start Call" click handler.
- **Using ScriptProcessorNode:** Deprecated, runs on main thread, causes audio glitches. Use AudioWorklet.
- **Opening multiple WebSocket connections:** React 19 Strict Mode double-fires useEffect. Use useRef to track connection state and prevent duplicate connections.
- **Base64 encoding PCM audio:** Binary WebSocket frames are 33% smaller than base64 JSON. Our backend already sends raw bytes -- keep it that way.
- **Playing audio with `<audio>` element or MediaSource API:** These require encoded formats (MP3, WAV). Raw PCM must use Web Audio API directly.
- **Assuming 16kHz playback:** Gemini Live API outputs 24kHz PCM. The playback AudioContext MUST be created with `{ sampleRate: 24000 }`. This is different from the recording AudioContext at 16kHz.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio capture/processing | Custom MediaRecorder wrapper | AudioWorklet with Float32->Int16 conversion | AudioWorklet runs on audio thread, handles sample rate natively |
| Audio playback buffering | Manual AudioBufferSourceNode scheduling | AudioWorklet ring buffer player | Ring buffer absorbs network jitter automatically |
| Voice activity detection | Silence detection from scratch | RMS amplitude from AudioWorklet data + threshold | Simple and effective -- 5 lines of code |
| WebSocket reconnection | Custom retry logic | Not needed for this phase | Single call session, user clicks Start again if disconnected |
| Component styling scoping | BEM naming conventions | CSS Modules (*.module.css) | Vite handles this natively, zero config |
| Responsive layout | Media query framework | CSS Grid + single `@media (max-width: 768px)` | Two breakpoints is all we need for split-panel stacking |

**Key insight:** The Web Audio API provides everything needed for this phase. No audio libraries are required. The browser's native AudioWorklet + WebSocket + AudioContext APIs handle microphone capture, playback, visualization, and buffer management with better performance than any npm package.

## Common Pitfalls

### Pitfall 1: AudioContext Requires User Gesture
**What goes wrong:** `new AudioContext()` created outside a click handler gets auto-suspended by Chrome/Safari. Audio appears to work in dev but silently fails for users.
**Why it happens:** Browser autoplay policy blocks audio context creation without user interaction.
**How to avoid:** Create BOTH AudioContexts (16kHz recorder + 24kHz player) inside the "Start Call" button click handler, BEFORE opening the WebSocket.
**Warning signs:** AudioContext.state is "suspended" instead of "running".

### Pitfall 2: Two Different Sample Rates (16kHz In, 24kHz Out)
**What goes wrong:** Using a single AudioContext for both recording and playback. Audio plays back too fast or too slow, pitch is wrong.
**Why it happens:** Gemini Live API accepts 16kHz input but outputs 24kHz. These are fixed and non-configurable.
**How to avoid:** Create TWO separate AudioContexts: `new AudioContext({ sampleRate: 16000 })` for recording and `new AudioContext({ sampleRate: 24000 })` for playback.
**Warning signs:** Sarah sounds like a chipmunk (played too fast) or slowed down (played too slow).

### Pitfall 3: React Strict Mode Double WebSocket
**What goes wrong:** Two WebSocket connections opened simultaneously, causing duplicate audio streams and garbled playback.
**Why it happens:** React 19 Strict Mode mounts/unmounts/remounts components in development, causing useEffect to fire twice.
**How to avoid:** Use `useRef` to track WebSocket instance. Check `wsRef.current` before creating new connection. Always close in cleanup function.
**Warning signs:** Duplicate "call_started" events in backend logs. Audio plays twice.

### Pitfall 4: AudioWorklet Module Loading Path
**What goes wrong:** `audioWorklet.addModule()` fails with 404 or MIME type error. Worklet processors not found.
**Why it happens:** AudioWorklet modules are loaded via URL, not bundled by Vite. Path must resolve correctly in both dev and production.
**How to avoid:** Use `new URL("./path.js", import.meta.url)` syntax which Vite handles correctly for both dev and production builds.
**Warning signs:** Console error: "Failed to load module script" or "The user aborted a request".

### Pitfall 5: Barge-In Sensitivity Tuning
**What goes wrong:** Either barge-in triggers on background noise (too sensitive) or doesn't trigger when user speaks (too insensitive).
**Why it happens:** VAD threshold set too low or too high for the environment.
**How to avoid:** Start with RMS threshold ~0.01-0.02 for typical microphone input. Add a minimum duration check (e.g., 3 consecutive frames above threshold) to avoid triggering on clicks/pops.
**Warning signs:** Sarah stops talking when user coughs or a door slams. Or: user speaks loudly and Sarah keeps talking over them.

### Pitfall 6: WebSocket Binary Type Not Set
**What goes wrong:** Binary audio data arrives as Blob instead of ArrayBuffer, breaking PCM processing.
**Why it happens:** Default WebSocket binaryType is "blob" in browsers.
**How to avoid:** Set `ws.binaryType = "arraybuffer"` immediately after creating the WebSocket.
**Warning signs:** `event.data instanceof ArrayBuffer` returns false. TypeError when creating Int16Array from Blob.

### Pitfall 7: Memory Leak from AnalyserNode Animation Loop
**What goes wrong:** requestAnimationFrame loop continues after component unmount, causing memory leak and "setState on unmounted component" warnings.
**Why it happens:** Animation loop not cancelled in useEffect cleanup.
**How to avoid:** Store requestAnimationFrame ID in ref, call cancelAnimationFrame in cleanup. Or use a `running` ref flag checked each frame.
**Warning signs:** Browser memory usage climbs after multiple call sessions.

## Code Examples

### Float32 to Int16 PCM Conversion
```javascript
// Source: https://google.github.io/adk-docs/streaming/dev-guide/part5/
export function convertFloat32ToPCM16(float32Array) {
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s * 0x7fff;
  }
  return pcm16.buffer;
}
```

### RMS Amplitude for Visualization
```javascript
// For AnalyserNode-based visualization (pulsing circles)
export function computeRMS(float32Array) {
  let sum = 0;
  for (let i = 0; i < float32Array.length; i++) {
    sum += float32Array[i] * float32Array[i];
  }
  return Math.sqrt(sum / float32Array.length);
}

// For incoming PCM bytes (Sarah's amplitude)
export function computePCMAmplitude(arrayBuffer) {
  const int16 = new Int16Array(arrayBuffer);
  let sum = 0;
  for (let i = 0; i < int16.length; i++) {
    const normalized = int16[i] / 32768;
    sum += normalized * normalized;
  }
  return Math.sqrt(sum / int16.length);
}
```

### Backend Transcript Forwarding (voice_handler.py modification)
```python
# Source: Existing codebase pattern -- voice_handler.py downstream_audio()
# ADD: Forward transcript events as JSON text messages to WebSocket client

# After capturing user speech transcription:
if (
    hasattr(event, "input_transcription")
    and event.input_transcription
    and event.input_transcription.text
):
    call_session.append_user_transcript(event.input_transcription.text)
    # NEW: Forward to browser client
    try:
        await websocket.send_json({
            "type": "transcript",
            "speaker": "user",
            "text": event.input_transcription.text,
        })
    except WebSocketDisconnect:
        return

# After capturing agent speech transcription:
if (
    hasattr(event, "output_transcription")
    and event.output_transcription
    and event.output_transcription.text
):
    call_session.append_agent_transcript(event.output_transcription.text)
    # NEW: Forward to browser client
    try:
        await websocket.send_json({
            "type": "transcript",
            "speaker": "agent",
            "text": event.output_transcription.text,
        })
    except WebSocketDisconnect:
        return
```

### New Backend REST Endpoints (main.py additions)
```python
# GET /api/leads -- proxy to Supabase (keeps credentials server-side)
@app.get("/api/leads")
async def list_leads():
    """List all leads with latest call outcome status."""
    url = f"{config.supabase_url}/rest/v1/leads?select=id,name,phone,email,call_outcome,status&order=name"
    headers = {
        "apikey": config.supabase_service_key,
        "Authorization": f"Bearer {config.supabase_service_key}",
        "Accept": "application/json",
        "Accept-Profile": "sales_agent",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()


# GET /api/call/{lead_id}/latest -- post-call summary
@app.get("/api/call/{lead_id}/latest")
async def get_latest_call(lead_id: str):
    """Get the most recent call log for a lead."""
    url = (
        f"{config.supabase_url}/rest/v1/call_logs"
        f"?lead_id=eq.{lead_id}&order=created_at.desc&limit=1"
    )
    headers = {
        "apikey": config.supabase_service_key,
        "Authorization": f"Bearer {config.supabase_service_key}",
        "Accept": "application/json",
        "Accept-Profile": "sales_agent",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else {"error": "No call logs found"}
```

### Vite Config with WebSocket Proxy
```javascript
// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

### index.html (Vite entry point -- MUST CREATE)
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sarah - Cloudboosta AI Sales Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/index.jsx"></script>
  </body>
</html>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ScriptProcessorNode for audio processing | AudioWorklet | Chrome 66 (2018), now universal | Audio runs on dedicated thread, no UI jank |
| Base64 audio in JSON WebSocket frames | Binary WebSocket frames | Always available, now standard | 33% less bandwidth, no encode/decode overhead |
| createScriptProcessor for visualization | AnalyserNode.getByteTimeDomainData | Long-standing | Purpose-built for visualization, no processing cost |
| Manual AudioBuffer scheduling | AudioWorklet ring buffer | Became standard ~2020 | Automatic jitter absorption, no scheduling complexity |
| React 18 useEffect patterns | React 19 same patterns + cleanup awareness | 2024 | Strict Mode double-fire requires ref guards for WebSocket |

**Deprecated/outdated:**
- ScriptProcessorNode: Deprecated since spec 2014, replaced by AudioWorklet. Still works in all browsers but runs on main thread.
- pcm-player npm package: Uses ScriptProcessorNode internally. Build custom AudioWorklet player instead (30 lines).

## Critical Technical Discovery: Dual Sample Rate

**This is the most important finding for implementation.**

The Gemini Live API has asymmetric sample rates:
- **Input (microphone -> Gemini):** 16,000 Hz (16kHz), MIME type `audio/pcm;rate=16000`
- **Output (Gemini -> speakers):** 24,000 Hz (24kHz), fixed, non-configurable

This means the frontend MUST create **two separate AudioContext instances**:
1. `new AudioContext({ sampleRate: 16000 })` -- for microphone capture
2. `new AudioContext({ sampleRate: 24000 })` -- for audio playback

Source: [Gemini Live API docs](https://ai.google.dev/gemini-api/docs/live-guide) -- "Audio output always uses a sample rate of 24kHz."

The existing backend `voice_handler.py` already handles this correctly:
- Line 215-216: Sends `audio/pcm;rate=16000` MIME type for input
- Line 240: Sends `part.inline_data.data` (24kHz PCM bytes) to WebSocket client

## Backend Modifications Required

The frontend phase requires these backend changes (estimated 50 lines total):

1. **voice_handler.py:** Forward transcript events as JSON text messages (see Code Examples above). Add ~20 lines to `downstream_audio()`.

2. **main.py:** Add two REST endpoints for lead listing and call summary (see Code Examples above). Add ~30 lines + `import httpx`.

3. **main.py:** Add `from fastapi.responses import JSONResponse` if not already imported.

These backend changes are prerequisites for the frontend and should be implemented first.

## Open Questions

1. **AudioWorklet CORS in production**
   - What we know: AudioWorklet modules load via URL fetch. In development, Vite serves them from the same origin.
   - What's unclear: Whether the nginx Docker config needs special headers for .js files in the worklet path.
   - Recommendation: Test during Phase 5 deployment. For Phase 4, development mode handles this automatically.

2. **Gemini transcription event timing**
   - What we know: ADK emits `input_transcription` and `output_transcription` events, but timing relative to audio chunks is not guaranteed.
   - What's unclear: Whether transcripts arrive word-by-word or sentence-by-sentence. This affects the "streaming word-by-word display" requirement.
   - Recommendation: Implement the transcript display to handle both cases -- append new text to the latest bubble from the same speaker, create new bubble on speaker change.

3. **VAD threshold calibration**
   - What we know: RMS amplitude threshold ~0.01-0.02 works for typical environments.
   - What's unclear: Optimal threshold for the competition demo environment.
   - Recommendation: Make threshold a constant at the top of the hook file (e.g., `const VAD_THRESHOLD = 0.015`) for easy tuning during testing.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (not yet installed) + pytest 9.0.2 (backend, already installed) |
| Config file | None for frontend -- see Wave 0. Backend: tests/conftest.py exists |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` (after setup) |
| Full suite command | `cd frontend && npx vitest run && cd ../tests && python -m pytest -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPL-03 | WebSocket connects and streams audio bidirectionally | integration | `cd tests && python -m pytest test_voice_session.py -x` | Existing (backend WebSocket tests) |
| DEPL-03 | React app renders and shows pre-call screen | smoke | `cd frontend && npx vitest run src/App.test.jsx` | Wave 0 |
| DEPL-03 | GET /api/leads returns lead list | integration | `cd tests && python -m pytest test_api_endpoints.py::test_list_leads -x` | Wave 0 |
| DEPL-03 | GET /api/call/{id}/latest returns call summary | integration | `cd tests && python -m pytest test_api_endpoints.py::test_latest_call -x` | Wave 0 |
| COMP-01 | Barge-in: playback buffer clears when user speaks | unit | `cd frontend && npx vitest run src/hooks/useVoiceSession.test.js` | Wave 0 |
| COMP-02 | Audio amplitude calculation produces valid values | unit | `cd frontend && npx vitest run src/utils/pcm.test.js` | Wave 0 |
| COMP-01 | Transcript forwarding sends JSON on WebSocket | integration | `cd tests && python -m pytest test_voice_session.py::test_transcript_forwarding -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run --reporter=verbose`
- **Per wave merge:** `cd frontend && npx vitest run && cd ../tests && python -m pytest -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/vitest.config.js` -- Vitest configuration (environment: jsdom)
- [ ] `frontend/src/App.test.jsx` -- Basic render test for App component
- [ ] `frontend/src/utils/pcm.test.js` -- Unit tests for PCM conversion helpers
- [ ] `tests/test_api_endpoints.py` -- Integration tests for new REST endpoints
- [ ] `tests/test_voice_session.py` -- Add test_transcript_forwarding (extend existing file)
- [ ] Install: `cd frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`

## Sources

### Primary (HIGH confidence)
- [ADK Streaming Dev Guide Part 5](https://google.github.io/adk-docs/streaming/dev-guide/part5/) -- AudioWorklet patterns, PCM conversion, WebSocket binary streaming, ring buffer player
- [Gemini Live API Capabilities Guide](https://ai.google.dev/gemini-api/docs/live-guide) -- Audio format specs (16kHz in, 24kHz out), PCM encoding details
- [MDN Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API) -- AnalyserNode, AudioWorklet, AudioContext APIs
- [MDN AnalyserNode.getByteFrequencyData](https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode/getByteFrequencyData) -- Visualization data extraction
- [Vite Server Options](https://vite.dev/config/server-options) -- Proxy configuration with WebSocket support
- [MDN ScriptProcessorNode](https://developer.mozilla.org/en-US/docs/Web/API/ScriptProcessorNode) -- Deprecation status confirmation

### Secondary (MEDIUM confidence)
- [Streaming PCM data + WebSocket + Web Audio API](https://medium.com/@adriendesbiaux/streaming-pcm-data-websocket-web-audio-api-part-1-2-5465e84c36ea) -- Practical implementation patterns
- [Handling Interruptions in Speech-to-Speech Services](https://medium.com/@roshini.rafy/handling-interruptions-in-speech-to-speech-services-a-complete-guide-4255c5aa2d84) -- Barge-in latency targets (P50 ~200ms detection, ~300ms stop)
- [2025 Voice AI Guide Part 3](https://medium.com/@programmerraja/2025-voice-ai-guide-how-to-make-your-own-real-time-voice-agent-part-3-7ca328aaea72) -- Barge-in implementation patterns
- [React 19 Strict Mode useEffect Guide](https://dev.to/pockit_tools/why-is-useeffect-running-twice-the-complete-guide-to-react-19-strict-mode-and-effect-cleanup-1n60) -- Double-fire prevention patterns

### Tertiary (LOW confidence)
- None -- all findings verified against primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- React 19 + Vite 6 already in package.json, Web Audio API is browser-native, all verified
- Architecture: HIGH -- AudioWorklet pattern from official ADK docs, ring buffer from ADK reference implementation, Vite proxy from official docs
- Pitfalls: HIGH -- Dual sample rate confirmed by Gemini Live API docs, Strict Mode double-fire well-documented, AudioContext user gesture requirement is browser-enforced
- Audio format: HIGH -- 16kHz input / 24kHz output confirmed by official Gemini docs, verified against existing backend code

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable APIs -- Web Audio, WebSocket, React 19 are all mature)

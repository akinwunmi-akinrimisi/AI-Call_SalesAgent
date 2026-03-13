/**
 * useVoiceSession -- WebSocket + audio pipeline orchestration hook.
 *
 * Manages the full bidirectional audio pipeline between the browser
 * microphone and the Sarah voice agent backend over WebSocket.
 *
 * Audio playback uses Google's AudioStreamer pattern (scheduled
 * AudioBufferSourceNodes) — ported from their official reference:
 * https://github.com/google-gemini/multimodal-live-api-web-console
 *
 * Features:
 * - 16kHz mic capture via AudioWorklet (pcm-recorder-processor)
 * - 24kHz playback via AudioStreamer (scheduled buffers, gapless)
 * - Barge-in detection: stops scheduled playback when user speaks
 * - Amplitude tracking for visualization (user + Sarah)
 * - Transcript accumulation from server JSON messages
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { convertFloat32ToPCM16, computeRMS, computePCMAmplitude } from "../utils/pcm";
import { AudioStreamer } from "../lib/audio-streamer";

// Build version — visible in console to confirm code is fresh after refresh
const BUILD_VERSION = "v3-audiostreamer-" + Date.now();

/**
 * Voice Activity Detection threshold for barge-in.
 */
export const VAD_THRESHOLD = 0.015;

/**
 * Barge-in detection logic (exported for testing -- COMP-01).
 */
export function checkBargeIn(rms, isSarahSpeaking, audioStreamer) {
  if (rms > VAD_THRESHOLD && isSarahSpeaking && audioStreamer) {
    audioStreamer.stop();
    return true;
  }
  return false;
}

let transcriptIdCounter = 0;

/**
 * Custom React hook for managing a voice call session.
 */
export function useVoiceSession() {
  // ---- State ----
  const [status, setStatus] = useState("idle");
  const [transcripts, setTranscripts] = useState([]);
  const [userAmplitude, setUserAmplitude] = useState(0);
  const [sarahAmplitude, setSarahAmplitude] = useState(0);
  const [callStartTime, setCallStartTime] = useState(null);

  // ---- Refs ----
  const wsRef = useRef(null);
  const recordContextRef = useRef(null);
  const playContextRef = useRef(null);
  const recorderNodeRef = useRef(null);
  const audioStreamerRef = useRef(null);
  const streamRef = useRef(null);
  const isSarahSpeakingRef = useRef(false);
  const frameCountRef = useRef(0);
  const sarahSilenceTimerRef = useRef(null);

  // ---- endCall ----
  const endCall = useCallback(() => {
    // Close WebSocket
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close(1000, "Call ended by user");
    }
    wsRef.current = null;

    // Stop audio streamer
    if (audioStreamerRef.current) {
      audioStreamerRef.current.stop();
      audioStreamerRef.current = null;
    }

    // Stop MediaStream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // Close AudioContexts
    if (recordContextRef.current && recordContextRef.current.state !== "closed") {
      recordContextRef.current.close().catch(() => {});
      recordContextRef.current = null;
    }
    if (playContextRef.current && playContextRef.current.state !== "closed") {
      playContextRef.current.close().catch(() => {});
      playContextRef.current = null;
    }

    recorderNodeRef.current = null;

    setStatus("ended");
  }, []);

  // ---- startCall ----
  const startCall = useCallback(
    async (leadId) => {
      // React Strict Mode guard: prevent double creation
      if (wsRef.current) return;

      console.log("[VoiceSession]", BUILD_VERSION, "starting call for", leadId);

      setStatus("connecting");
      setTranscripts([]);
      setUserAmplitude(0);
      setSarahAmplitude(0);
      isSarahSpeakingRef.current = false;
      frameCountRef.current = 0;

      try {
        // 1. Create recording AudioContext at 16kHz (MUST be in click handler)
        const recordContext = new AudioContext({ sampleRate: 16000 });
        recordContextRef.current = recordContext;
        console.log("[VoiceSession] Record context sampleRate:", recordContext.sampleRate);

        // 2. Create playback AudioContext at system default rate.
        // AudioBuffers are created at 24kHz — browser auto-resamples.
        // Avoids Chrome/Windows issues with non-standard 24kHz contexts.
        const playContext = new AudioContext();
        playContextRef.current = playContext;
        console.log("[VoiceSession] Play context sampleRate:", playContext.sampleRate, "(system default)");

        // Ensure context is running (Chrome autoplay policy)
        if (playContext.state === "suspended") {
          await playContext.resume();
        }

        // 3. Load AudioWorklet for recording only
        const recorderUrl = new URL(
          "../audio/pcm-recorder-processor.js",
          import.meta.url
        );
        await recordContext.audioWorklet.addModule(recorderUrl);

        // 4. Request microphone
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1 },
        });
        streamRef.current = stream;

        // 5. Wire recording pipeline
        const source = recordContext.createMediaStreamSource(stream);
        const recorderNode = new AudioWorkletNode(
          recordContext,
          "pcm-recorder-processor"
        );
        recorderNodeRef.current = recorderNode;
        source.connect(recorderNode);

        // 6. Create AudioStreamer for playback (Google's reference pattern)
        const audioStreamer = new AudioStreamer(playContext);
        audioStreamerRef.current = audioStreamer;
        console.log("[VoiceSession] AudioStreamer created");

        // 7. Open WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/voice/${leadId}`;
        const ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer"; // CRITICAL: prevents Blob default
        wsRef.current = ws;

        // 8. Recorder onmessage: convert and send to WebSocket + barge-in
        recorderNode.port.onmessage = (event) => {
          const float32Data = event.data;
          const pcm16Buffer = convertFloat32ToPCM16(float32Data);

          // Send to server if WebSocket is open
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(pcm16Buffer);
          }

          // Compute user amplitude (throttle to every 3rd frame)
          frameCountRef.current++;
          if (frameCountRef.current % 3 === 0) {
            const rms = computeRMS(float32Data);
            setUserAmplitude(rms);

            // Barge-in detection
            if (checkBargeIn(rms, isSarahSpeakingRef.current, audioStreamer)) {
              isSarahSpeakingRef.current = false;
              // Resume streamer for next response
              audioStreamer.resume();
            }
          }
        };

        // 9. WebSocket event handlers
        ws.onopen = () => {
          console.log("[VoiceSession] WebSocket connected");
          setStatus("connected");
          setCallStartTime(new Date());
        };

        let audioChunkCount = 0;
        ws.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) {
            audioChunkCount++;

            // Log first few chunks for diagnostics
            if (audioChunkCount <= 3 || audioChunkCount % 100 === 0) {
              console.log(
                "[VoiceSession] Audio chunk #" + audioChunkCount,
                event.data.byteLength + " bytes",
                audioStreamer.diagnostics
              );
            }

            // Feed PCM16 audio to the streamer for scheduled playback
            audioStreamer.addPCM16(event.data);

            // Compute Sarah amplitude
            const amplitude = computePCMAmplitude(event.data);
            if (amplitude > 0.005) {
              isSarahSpeakingRef.current = true;
              setSarahAmplitude(amplitude);
            }

            // Reset silence timer
            if (sarahSilenceTimerRef.current) {
              clearTimeout(sarahSilenceTimerRef.current);
            }
            sarahSilenceTimerRef.current = setTimeout(() => {
              isSarahSpeakingRef.current = false;
              setSarahAmplitude(0);
            }, 300);
          } else {
            // Text message -- parse as JSON transcript
            try {
              const msg = JSON.parse(event.data);
              if (msg.type === "ready") {
                console.log("[VoiceSession] Backend ready signal received");
              } else if (msg.type === "transcript") {
                setTranscripts((prev) => {
                  // Append to last entry if same speaker
                  if (
                    prev.length > 0 &&
                    prev[prev.length - 1].speaker === msg.speaker
                  ) {
                    const updated = [...prev];
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      text: updated[updated.length - 1].text + msg.text,
                    };
                    return updated;
                  }
                  return [
                    ...prev,
                    {
                      speaker: msg.speaker,
                      text: msg.text,
                      id: ++transcriptIdCounter,
                    },
                  ];
                });
              }
            } catch (e) {
              // Ignore unparseable messages
            }
          }
        };

        ws.onclose = () => {
          console.log("[VoiceSession] WebSocket closed");
          setStatus("ended");
        };

        ws.onerror = (error) => {
          console.error("[VoiceSession] WebSocket error:", error);
          setStatus("ended");
        };
      } catch (error) {
        console.error("[VoiceSession] Failed to start call:", error);
        endCall();
      }
    },
    [endCall]
  );

  // ---- Cleanup on unmount ----
  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  return {
    status,
    transcripts,
    userAmplitude,
    sarahAmplitude,
    callStartTime,
    startCall,
    endCall,
  };
}

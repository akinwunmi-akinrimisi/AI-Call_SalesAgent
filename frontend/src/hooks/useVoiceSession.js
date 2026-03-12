/**
 * useVoiceSession -- WebSocket + audio pipeline orchestration hook.
 *
 * Manages the full bidirectional audio pipeline between the browser
 * microphone and the Sarah voice agent backend over WebSocket.
 *
 * Features:
 * - 16kHz mic capture via AudioWorklet (pcm-recorder-processor)
 * - 24kHz playback via AudioWorklet ring buffer (pcm-player-processor)
 * - Barge-in detection: flushes playback buffer when user speaks over Sarah
 * - Amplitude tracking for visualization (user + Sarah)
 * - Transcript accumulation from server JSON messages
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { convertFloat32ToPCM16, computeRMS, computePCMAmplitude } from "../utils/pcm";

/**
 * Voice Activity Detection threshold for barge-in.
 * When user audio RMS exceeds this while Sarah is speaking,
 * the playback buffer is flushed. Can be tuned based on
 * microphone sensitivity and ambient noise levels.
 */
export const VAD_THRESHOLD = 0.015;

/**
 * Barge-in detection logic (exported for testing -- COMP-01).
 *
 * Checks if the user is speaking loudly enough over Sarah's audio
 * and flushes the playback buffer to allow natural interruption.
 *
 * @param {number} rms - RMS amplitude of user audio (0-1)
 * @param {boolean} isSarahSpeaking - Whether Sarah is currently speaking
 * @param {{ postMessage: Function }} playerPort - AudioWorklet player port
 * @returns {boolean} True if barge-in was triggered
 */
export function checkBargeIn(rms, isSarahSpeaking, playerPort) {
  if (rms > VAD_THRESHOLD && isSarahSpeaking && playerPort) {
    playerPort.postMessage({ command: "clearBuffer" });
    return true;
  }
  return false;
}

let transcriptIdCounter = 0;

/**
 * Custom React hook for managing a voice call session.
 *
 * @returns {{
 *   status: string,
 *   transcripts: Array<{speaker: string, text: string, id: number}>,
 *   userAmplitude: number,
 *   sarahAmplitude: number,
 *   callStartTime: Date|null,
 *   startCall: (leadId: string) => Promise<void>,
 *   endCall: () => void,
 * }}
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
  const playerNodeRef = useRef(null);
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
    playerNodeRef.current = null;

    setStatus("ended");
  }, []);

  // ---- startCall ----
  const startCall = useCallback(
    async (leadId) => {
      // React Strict Mode guard: prevent double creation
      if (wsRef.current) return;

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

        // 2. Create playback AudioContext at 24kHz
        const playContext = new AudioContext({ sampleRate: 24000 });
        playContextRef.current = playContext;

        // 3. Load AudioWorklet modules
        const recorderUrl = new URL(
          "../audio/pcm-recorder-processor.js",
          import.meta.url
        );
        const playerUrl = new URL(
          "../audio/pcm-player-processor.js",
          import.meta.url
        );

        await recordContext.audioWorklet.addModule(recorderUrl);
        await playContext.audioWorklet.addModule(playerUrl);

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

        // 6. Wire playback pipeline
        const playerNode = new AudioWorkletNode(
          playContext,
          "pcm-player-processor"
        );
        playerNodeRef.current = playerNode;
        playerNode.connect(playContext.destination);

        // 7. Open WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/voice/${leadId}`;
        const ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer"; // CRITICAL: prevents Blob default
        wsRef.current = ws;

        // 8. Recorder onmessage: convert and send to WebSocket + barge-in detection
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
            if (checkBargeIn(rms, isSarahSpeakingRef.current, playerNode.port)) {
              isSarahSpeakingRef.current = false;
            }
          }
        };

        // 9. WebSocket event handlers
        ws.onopen = () => {
          setStatus("connected");
          setCallStartTime(new Date());
        };

        ws.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) {
            // Binary audio from Sarah -- send to player
            playerNode.port.postMessage(event.data);

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
            }, 200);
          } else {
            // Text message -- parse as JSON transcript
            try {
              const msg = JSON.parse(event.data);
              if (msg.type === "transcript") {
                setTranscripts((prev) => [
                  ...prev,
                  {
                    speaker: msg.speaker,
                    text: msg.text,
                    id: ++transcriptIdCounter,
                  },
                ]);
              }
            } catch (e) {
              // Ignore unparseable messages
            }
          }
        };

        ws.onclose = () => {
          setStatus("ended");
        };

        ws.onerror = (error) => {
          console.error("WebSocket error:", error);
          setStatus("ended");
        };
      } catch (error) {
        console.error("Failed to start call:", error);
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

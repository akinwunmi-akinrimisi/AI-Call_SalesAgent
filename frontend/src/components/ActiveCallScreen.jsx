/**
 * ActiveCallScreen -- Split-panel layout for live voice call.
 *
 * Left panel: Audio visualizers (Sarah + User), connection status,
 * call duration timer, and End Call button.
 * Right panel: Live transcript with chat-style bubbles.
 *
 * @param {{
 *   status: string,
 *   transcripts: Array,
 *   userAmplitude: number,
 *   sarahAmplitude: number,
 *   callStartTime: Date|null,
 *   onEndCall: Function
 * }} props
 */

import { useState, useEffect } from "react";
import AudioVisualizer from "./AudioVisualizer";
import TranscriptPanel from "./TranscriptPanel";
import styles from "./ActiveCallScreen.module.css";

export default function ActiveCallScreen({
  status,
  transcripts,
  userAmplitude,
  sarahAmplitude,
  callStartTime,
  onEndCall,
}) {
  const [elapsed, setElapsed] = useState(0);

  // Call duration timer
  useEffect(() => {
    if (!callStartTime) return;

    const interval = setInterval(() => {
      const seconds = Math.floor((Date.now() - callStartTime.getTime()) / 1000);
      setElapsed(seconds);
    }, 1000);

    return () => clearInterval(interval);
  }, [callStartTime]);

  // Format elapsed seconds as mm:ss
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";

  return (
    <div className={styles.screen}>
      {/* Left Panel: Visualizers + Controls */}
      <div className={styles.leftPanel}>
        <div className={styles.visualizers}>
          <AudioVisualizer
            amplitude={sarahAmplitude}
            color="green"
            size={140}
            label="Sarah"
            avatar={true}
          />
          <AudioVisualizer
            amplitude={userAmplitude}
            color="blue"
            size={100}
            label="You"
            avatar={false}
          />
        </div>

        {/* Connection Status */}
        <div className={styles.statusBar}>
          <div
            className={`${styles.statusDot} ${
              isConnected
                ? styles.statusConnected
                : isConnecting
                ? styles.statusConnecting
                : ""
            }`}
          />
          <span>{isConnected ? "Connected" : isConnecting ? "Connecting..." : status}</span>
        </div>

        {/* Call Duration Timer */}
        <div className={styles.timer}>{formatTime(elapsed)}</div>

        {/* End Call Button */}
        <button className={styles.endCallButton} onClick={onEndCall}>
          End Call
        </button>
      </div>

      {/* Right Panel: Transcript */}
      <div className={styles.rightPanel}>
        <TranscriptPanel transcripts={transcripts} />
      </div>
    </div>
  );
}

/**
 * Cloudboosta Voice Agent -- Root Application Component
 *
 * Implements a three-screen state machine:
 * - pre-call:  Lead selection and call initiation
 * - active:    Live call with audio visualization and transcript
 * - post-call: Call summary with outcome and duration
 */

import { useState, useEffect, useRef } from "react";
import { useVoiceSession } from "./hooks/useVoiceSession";
import PreCallScreen from "./components/PreCallScreen";
import PostCallScreen from "./components/PostCallScreen";
import styles from "./App.module.css";

// Lazy import ActiveCallScreen to avoid errors before Task 2 creates it
let ActiveCallScreen = null;
try {
  // This will be replaced in Task 2 with a proper import
  ActiveCallScreen = null;
} catch (e) {
  // Component not yet created
}

export default function App() {
  const [screen, setScreen] = useState("pre-call");
  const [selectedLead, setSelectedLead] = useState(null);
  const [callSummary, setCallSummary] = useState(null);
  const [callDuration, setCallDuration] = useState(0);

  const {
    status,
    transcripts,
    userAmplitude,
    sarahAmplitude,
    callStartTime,
    startCall,
    endCall,
  } = useVoiceSession();

  // Track previous status to detect "connected" -> "ended" transition
  const prevStatusRef = useRef(status);

  useEffect(() => {
    const prevStatus = prevStatusRef.current;
    prevStatusRef.current = status;

    if (prevStatus === "connected" && status === "ended" && selectedLead) {
      // Call just ended -- fetch summary
      const fetchSummary = async () => {
        try {
          const res = await fetch(`/api/call/${selectedLead.id}/latest`);
          if (res.ok) {
            const data = await res.json();
            setCallSummary(data);
          }
        } catch (err) {
          console.error("Failed to fetch call summary:", err);
        }
      };

      // Compute call duration
      if (callStartTime) {
        const durationSeconds = Math.floor(
          (Date.now() - callStartTime.getTime()) / 1000
        );
        setCallDuration(durationSeconds);
      }

      fetchSummary();
      setScreen("post-call");
    }
  }, [status, selectedLead, callStartTime]);

  const handleStartCall = async () => {
    if (!selectedLead) return;
    await startCall(selectedLead.id);
    setScreen("active");
  };

  const handleNewCall = () => {
    setScreen("pre-call");
    setSelectedLead(null);
    setCallSummary(null);
    setCallDuration(0);
  };

  return (
    <div className={styles.app}>
      {screen === "pre-call" && (
        <PreCallScreen
          onSelectLead={setSelectedLead}
          onStartCall={handleStartCall}
          selectedLead={selectedLead}
        />
      )}

      {screen === "active" && ActiveCallScreen && (
        <ActiveCallScreen
          status={status}
          transcripts={transcripts}
          userAmplitude={userAmplitude}
          sarahAmplitude={sarahAmplitude}
          callStartTime={callStartTime}
          onEndCall={endCall}
        />
      )}

      {screen === "active" && !ActiveCallScreen && (
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <p>Call active -- ActiveCallScreen component pending Task 2</p>
          <button
            onClick={endCall}
            style={{
              padding: "12px 24px",
              background: "#ef5350",
              color: "white",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            End Call
          </button>
        </div>
      )}

      {screen === "post-call" && (
        <PostCallScreen
          callSummary={callSummary}
          onNewCall={handleNewCall}
          callDuration={callDuration}
        />
      )}
    </div>
  );
}

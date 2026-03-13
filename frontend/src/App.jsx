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
import ActiveCallScreen from "./components/ActiveCallScreen";
import PostCallScreen from "./components/PostCallScreen";
import styles from "./App.module.css";

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

  // Track previous status to detect transition to "ended"
  const prevStatusRef = useRef(status);

  useEffect(() => {
    const prevStatus = prevStatusRef.current;
    prevStatusRef.current = status;

    // Transition to post-call when status becomes "ended" from any active state
    if (status === "ended" && prevStatus !== "ended" && screen === "active") {
      // Compute call duration
      if (callStartTime) {
        const durationSeconds = Math.floor(
          (Date.now() - callStartTime.getTime()) / 1000
        );
        setCallDuration(durationSeconds);
      }

      // Fetch summary if we had a lead selected
      if (selectedLead) {
        fetch(`/api/call/${selectedLead.id}/latest`)
          .then((res) => res.ok ? res.json() : null)
          .then((data) => { if (data) setCallSummary(data); })
          .catch((err) => console.error("Failed to fetch call summary:", err));
      }

      setScreen("post-call");
    }
  }, [status, selectedLead, callStartTime, screen]);

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

      {screen === "active" && (
        <ActiveCallScreen
          status={status}
          transcripts={transcripts}
          userAmplitude={userAmplitude}
          sarahAmplitude={sarahAmplitude}
          callStartTime={callStartTime}
          onEndCall={() => {
            endCall();
            // Compute duration before transitioning
            if (callStartTime) {
              setCallDuration(Math.floor((Date.now() - callStartTime.getTime()) / 1000));
            }
            if (selectedLead) {
              fetch(`/api/call/${selectedLead.id}/latest`)
                .then((res) => res.ok ? res.json() : null)
                .then((data) => { if (data) setCallSummary(data); })
                .catch(() => {});
            }
            setScreen("post-call");
          }}
        />
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

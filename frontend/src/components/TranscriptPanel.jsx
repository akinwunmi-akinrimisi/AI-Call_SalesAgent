/**
 * TranscriptPanel -- Chat-style speech bubbles with auto-scroll.
 *
 * Displays a live transcript of the conversation with agent bubbles
 * on the left (green tint) and user bubbles on the right (blue tint).
 *
 * @param {{ transcripts: Array<{speaker: string, text: string, id: string|number}> }} props
 */

import { useEffect, useRef } from "react";
import styles from "./TranscriptPanel.module.css";

export default function TranscriptPanel({ transcripts }) {
  const messagesRef = useRef(null);

  // Auto-scroll to bottom when new transcripts arrive
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [transcripts.length]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>Transcript</div>

      {transcripts.length === 0 ? (
        <div className={styles.emptyState}>Waiting for conversation...</div>
      ) : (
        <div className={styles.messages} ref={messagesRef}>
          {transcripts.map((entry) => {
            const isAgent = entry.speaker === "agent";
            return (
              <div
                key={entry.id}
                className={`${styles.bubbleGroup} ${
                  isAgent ? styles.agentGroup : styles.userGroup
                }`}
              >
                <div
                  className={`${styles.speakerLabel} ${
                    !isAgent ? styles.userSpeakerLabel : ""
                  }`}
                >
                  {isAgent ? "Sarah" : "You"}
                </div>
                <div
                  className={`${styles.bubble} ${
                    isAgent ? styles.agentBubble : styles.userBubble
                  }`}
                >
                  {entry.text}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

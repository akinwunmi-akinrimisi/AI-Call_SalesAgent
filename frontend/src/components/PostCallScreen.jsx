import styles from "./PostCallScreen.module.css";

/**
 * PostCallScreen -- Call summary with outcome, duration, and programme.
 *
 * Displays after a call ends with color-coded outcome
 * and a "New Call" button to return to pre-call screen.
 *
 * @param {{ callSummary: object, onNewCall: Function, callDuration: number }} props
 */
export default function PostCallScreen({ callSummary, onNewCall, callDuration }) {
  /**
   * Format seconds as mm:ss
   */
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  /**
   * Get CSS class for outcome color coding
   */
  const getOutcomeClass = (outcome) => {
    if (!outcome) return styles.value;
    const upper = outcome.toUpperCase();
    if (upper === "COMMITTED") return `${styles.value} ${styles.committed}`;
    if (upper === "FOLLOW_UP") return `${styles.value} ${styles.followUp}`;
    if (upper === "DECLINED") return `${styles.value} ${styles.declined}`;
    return styles.value;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>Call Ended</div>

      <div className={styles.card}>
        <div className={styles.row}>
          <span className={styles.label}>Duration</span>
          <span className={styles.value}>
            {formatDuration(callDuration || 0)}
          </span>
        </div>

        <div className={styles.row}>
          <span className={styles.label}>Outcome</span>
          <span className={getOutcomeClass(callSummary?.outcome)}>
            {callSummary?.outcome || "Unknown"}
          </span>
        </div>

        <div className={styles.row}>
          <span className={styles.label}>Recommended Programme</span>
          <span className={styles.value}>
            {callSummary?.recommended_programme || "Not determined"}
          </span>
        </div>
      </div>

      <button className={styles.newCallButton} onClick={onNewCall}>
        New Call
      </button>
    </div>
  );
}

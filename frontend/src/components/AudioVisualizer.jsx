/**
 * AudioVisualizer -- Pulsing concentric circles for audio activity.
 *
 * Renders three concentric rings that scale based on audio amplitude,
 * with color coding (green for Sarah, blue for user).
 *
 * @param {{ amplitude: number, color: string, size: number, label: string, avatar: boolean }} props
 */

import { useAudioVisualization } from "../hooks/useAudioVisualization";
import styles from "./AudioVisualizer.module.css";

const COLOR_MAP = {
  green: {
    outer: "rgba(0, 200, 83, 0.15)",
    middle: "rgba(0, 200, 83, 0.3)",
    inner: "#00c853",
  },
  blue: {
    outer: "rgba(74, 144, 217, 0.15)",
    middle: "rgba(74, 144, 217, 0.3)",
    inner: "#4a90d9",
  },
};

export default function AudioVisualizer({ amplitude, color, size, label, avatar }) {
  const smoothed = useAudioVisualization(amplitude);
  const colors = COLOR_MAP[color] || COLOR_MAP.green;

  const outerSize = size * 1.8;
  const middleSize = size * 1.4;
  const innerSize = size;

  const outerScale = 1 + smoothed * 0.4 * 1.3;
  const middleScale = 1 + smoothed * 0.4 * 1.15;
  const innerScale = 1 + smoothed * 0.4;

  const fontSize = Math.round(size * 0.35);

  return (
    <div className={styles.container}>
      <div
        className={styles.rings}
        style={{ width: outerSize, height: outerSize }}
      >
        {/* Outer ring */}
        <div
          className={styles.ring}
          style={{
            width: outerSize,
            height: outerSize,
            background: colors.outer,
            transform: `scale(${outerScale})`,
          }}
        />

        {/* Middle ring */}
        <div
          className={styles.ring}
          style={{
            width: middleSize,
            height: middleSize,
            background: colors.middle,
            transform: `scale(${middleScale})`,
            left: (outerSize - middleSize) / 2,
            top: (outerSize - middleSize) / 2,
          }}
        />

        {/* Inner ring (solid) */}
        <div
          className={styles.innerRing}
          style={{
            width: innerSize,
            height: innerSize,
            background: colors.inner,
            transform: `scale(${innerScale})`,
            position: "absolute",
            left: (outerSize - innerSize) / 2,
            top: (outerSize - innerSize) / 2,
            fontSize,
          }}
        >
          {avatar ? (
            <span className={styles.avatarText}>S</span>
          ) : (
            <span className={styles.micIcon}>
              <svg
                width={fontSize}
                height={fontSize}
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="9" y="2" width="6" height="11" rx="3" />
                <path d="M5 10a7 7 0 0 0 14 0" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            </span>
          )}
        </div>
      </div>

      <div className={styles.label}>{label}</div>
    </div>
  );
}

/**
 * useAudioVisualization -- Smooth amplitude interpolation for audio visualization.
 *
 * Takes raw amplitude (0-1) and smooths it using requestAnimationFrame
 * with linear interpolation for buttery animation of pulsing circles.
 *
 * @param {number} amplitude - Raw amplitude value (0-1)
 * @returns {number} Smoothed amplitude value (0-1)
 */

import { useState, useRef, useEffect } from "react";

export function useAudioVisualization(amplitude) {
  const [smoothedAmplitude, setSmoothedAmplitude] = useState(0);
  const targetRef = useRef(0);
  const smoothedRef = useRef(0);
  const frameIdRef = useRef(null);
  const runningRef = useRef(true);

  // Update target when amplitude changes
  useEffect(() => {
    targetRef.current = amplitude;
  }, [amplitude]);

  // Animation loop
  useEffect(() => {
    runningRef.current = true;

    const animate = () => {
      if (!runningRef.current) return;

      // Lerp toward target amplitude (factor ~0.15 for smooth animation)
      const lerp = 0.15;
      smoothedRef.current += (targetRef.current - smoothedRef.current) * lerp;

      // Snap to zero when very close to avoid perpetual animation
      if (smoothedRef.current < 0.001 && targetRef.current < 0.001) {
        smoothedRef.current = 0;
      }

      setSmoothedAmplitude(smoothedRef.current);
      frameIdRef.current = requestAnimationFrame(animate);
    };

    frameIdRef.current = requestAnimationFrame(animate);

    return () => {
      runningRef.current = false;
      if (frameIdRef.current) {
        cancelAnimationFrame(frameIdRef.current);
      }
    };
  }, []);

  return smoothedAmplitude;
}

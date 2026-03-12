/**
 * PCM audio utility functions.
 *
 * Provides conversion between Float32 and Int16 PCM formats,
 * and RMS amplitude computation for visualization and VAD.
 */

/**
 * Convert Float32Array audio samples to Int16 PCM ArrayBuffer.
 *
 * Clamps each sample to [-1, 1] range before scaling to Int16.
 *
 * @param {Float32Array} float32Array - Input audio samples (-1 to 1 range)
 * @returns {ArrayBuffer} Int16 PCM audio data
 */
export function convertFloat32ToPCM16(float32Array) {
  const int16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const clamped = Math.max(-1, Math.min(1, float32Array[i]));
    int16[i] = clamped * 0x7fff;
  }
  return int16.buffer;
}

/**
 * Compute RMS (Root Mean Square) amplitude of Float32 audio samples.
 *
 * Returns a value in the 0-1 range representing the overall loudness.
 *
 * @param {Float32Array} float32Array - Input audio samples
 * @returns {number} RMS amplitude (0 to 1)
 */
export function computeRMS(float32Array) {
  if (!float32Array || float32Array.length === 0) return 0;

  let sumSquares = 0;
  for (let i = 0; i < float32Array.length; i++) {
    sumSquares += float32Array[i] * float32Array[i];
  }
  return Math.sqrt(sumSquares / float32Array.length);
}

/**
 * Compute RMS amplitude from an Int16 PCM ArrayBuffer.
 *
 * Normalizes Int16 samples to Float32 range before computing RMS.
 *
 * @param {ArrayBuffer} arrayBuffer - Int16 PCM audio data
 * @returns {number} RMS amplitude (0 to 1)
 */
export function computePCMAmplitude(arrayBuffer) {
  if (!arrayBuffer || arrayBuffer.byteLength === 0) return 0;

  const int16 = new Int16Array(arrayBuffer);
  let sumSquares = 0;
  for (let i = 0; i < int16.length; i++) {
    const normalized = int16[i] / 32768;
    sumSquares += normalized * normalized;
  }
  return Math.sqrt(sumSquares / int16.length);
}

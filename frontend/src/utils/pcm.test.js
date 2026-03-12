import { describe, it, expect } from "vitest";
import {
  convertFloat32ToPCM16,
  computeRMS,
  computePCMAmplitude,
} from "./pcm.js";

describe("convertFloat32ToPCM16", () => {
  it("converts known Float32 values to correct Int16 values", () => {
    const input = new Float32Array([0, 0.5, -0.5, 1.0, -1.0]);
    const buffer = convertFloat32ToPCM16(input);
    const int16 = new Int16Array(buffer);

    expect(int16[0]).toBe(0); // silence
    expect(Math.abs(int16[1] - 16383)).toBeLessThanOrEqual(1); // 0.5 * 32767
    expect(Math.abs(int16[2] - -16383)).toBeLessThanOrEqual(1); // -0.5 * 32767
    expect(int16[3]).toBe(32767); // max positive
    expect(int16[4]).toBe(-32767); // max negative
  });
});

describe("computeRMS", () => {
  it("returns 0 for silence", () => {
    const silence = new Float32Array([0, 0, 0, 0]);
    expect(computeRMS(silence)).toBe(0);
  });

  it("returns 1.0 for constant full-scale signal", () => {
    const fullScale = new Float32Array([1.0, 1.0, 1.0, 1.0]);
    expect(computeRMS(fullScale)).toBeCloseTo(1.0, 5);
  });

  it("returns ~0.707 for alternating full-scale sine-like signal", () => {
    const sine = new Float32Array([1.0, -1.0, 1.0, -1.0]);
    expect(computeRMS(sine)).toBeCloseTo(1.0, 5);
  });

  it("returns 0 for empty array", () => {
    expect(computeRMS(new Float32Array([]))).toBe(0);
  });

  it("returns 0 for null input", () => {
    expect(computeRMS(null)).toBe(0);
  });
});

describe("computePCMAmplitude", () => {
  it("returns correct RMS from Int16 ArrayBuffer", () => {
    // Create a known Int16 ArrayBuffer: half-scale signal
    const int16 = new Int16Array([16384, -16384, 16384, -16384]);
    const rms = computePCMAmplitude(int16.buffer);
    // 16384 / 32768 = 0.5, RMS of [0.5, -0.5, 0.5, -0.5] = 0.5
    expect(rms).toBeCloseTo(0.5, 1);
  });

  it("returns 0 for empty buffer", () => {
    expect(computePCMAmplitude(new ArrayBuffer(0))).toBe(0);
  });

  it("returns 0 for null input", () => {
    expect(computePCMAmplitude(null)).toBe(0);
  });
});

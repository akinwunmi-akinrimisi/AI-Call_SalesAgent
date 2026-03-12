/**
 * Tests for useVoiceSession hook -- barge-in buffer flush logic.
 *
 * Validates COMP-01: When the user speaks over Sarah (RMS > VAD_THRESHOLD
 * while isSarahSpeaking=true), the playback buffer is flushed via
 * clearBuffer command sent to the player AudioWorklet port.
 *
 * Uses the extracted checkBargeIn function for direct testing.
 */

import { describe, it, expect, vi } from "vitest";
import { checkBargeIn, VAD_THRESHOLD } from "./useVoiceSession";

describe("checkBargeIn (COMP-01 barge-in buffer flush)", () => {
  it("flushes playback buffer when user speaks over Sarah", () => {
    const mockPort = { postMessage: vi.fn() };

    // RMS well above threshold, Sarah is speaking
    const result = checkBargeIn(0.5, true, mockPort);

    expect(result).toBe(true);
    expect(mockPort.postMessage).toHaveBeenCalledWith({
      command: "clearBuffer",
    });
  });

  it("does not flush when user audio is below VAD threshold", () => {
    const mockPort = { postMessage: vi.fn() };

    // RMS below threshold (0.01 < 0.015)
    const result = checkBargeIn(0.01, true, mockPort);

    expect(result).toBe(false);
    expect(mockPort.postMessage).not.toHaveBeenCalled();
  });

  it("does not flush when Sarah is not speaking", () => {
    const mockPort = { postMessage: vi.fn() };

    // High RMS but Sarah is not speaking
    const result = checkBargeIn(0.5, false, mockPort);

    expect(result).toBe(false);
    expect(mockPort.postMessage).not.toHaveBeenCalled();
  });

  it("does not flush when playerPort is null", () => {
    // Edge case: port not yet initialized
    const result = checkBargeIn(0.5, true, null);

    expect(result).toBe(false);
  });

  it("flushes at exactly the VAD threshold boundary", () => {
    const mockPort = { postMessage: vi.fn() };

    // RMS just barely above threshold
    const result = checkBargeIn(VAD_THRESHOLD + 0.001, true, mockPort);

    expect(result).toBe(true);
    expect(mockPort.postMessage).toHaveBeenCalledWith({
      command: "clearBuffer",
    });
  });

  it("does not flush at exactly the VAD threshold", () => {
    const mockPort = { postMessage: vi.fn() };

    // RMS exactly at threshold (not above)
    const result = checkBargeIn(VAD_THRESHOLD, true, mockPort);

    expect(result).toBe(false);
    expect(mockPort.postMessage).not.toHaveBeenCalled();
  });
});

describe("VAD_THRESHOLD constant", () => {
  it("is set to 0.015", () => {
    expect(VAD_THRESHOLD).toBe(0.015);
  });
});

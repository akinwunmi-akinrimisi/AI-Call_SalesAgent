import { describe, it, expect, vi } from "vitest";
import { checkBargeIn, VAD_THRESHOLD } from "./useVoiceSession";

describe("checkBargeIn (COMP-01 barge-in buffer flush)", () => {
  it("stops playback when user speaks over Sarah", () => {
    const mockStreamer = { stop: vi.fn() };
    const result = checkBargeIn(0.5, true, mockStreamer);
    expect(result).toBe(true);
    expect(mockStreamer.stop).toHaveBeenCalled();
  });

  it("does not stop when user audio is below VAD threshold", () => {
    const mockStreamer = { stop: vi.fn() };
    const result = checkBargeIn(0.01, true, mockStreamer);
    expect(result).toBe(false);
    expect(mockStreamer.stop).not.toHaveBeenCalled();
  });

  it("does not stop when Sarah is not speaking", () => {
    const mockStreamer = { stop: vi.fn() };
    const result = checkBargeIn(0.5, false, mockStreamer);
    expect(result).toBe(false);
    expect(mockStreamer.stop).not.toHaveBeenCalled();
  });

  it("does not stop when streamer is null", () => {
    const result = checkBargeIn(0.5, true, null);
    expect(result).toBe(false);
  });

  it("stops at exactly above VAD threshold", () => {
    const mockStreamer = { stop: vi.fn() };
    const result = checkBargeIn(VAD_THRESHOLD + 0.001, true, mockStreamer);
    expect(result).toBe(true);
    expect(mockStreamer.stop).toHaveBeenCalled();
  });

  it("does not stop at exactly the VAD threshold", () => {
    const mockStreamer = { stop: vi.fn() };
    const result = checkBargeIn(VAD_THRESHOLD, true, mockStreamer);
    expect(result).toBe(false);
    expect(mockStreamer.stop).not.toHaveBeenCalled();
  });
});

describe("VAD_THRESHOLD constant", () => {
  it("is set to 0.015", () => {
    expect(VAD_THRESHOLD).toBe(0.015);
  });
});

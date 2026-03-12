import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

// Mock useVoiceSession hook to return idle state defaults
vi.mock("./hooks/useVoiceSession", () => ({
  useVoiceSession: () => ({
    status: "idle",
    transcripts: [],
    userAmplitude: 0,
    sarahAmplitude: 0,
    callStartTime: null,
    startCall: vi.fn(),
    endCall: vi.fn(),
  }),
}));

// Mock fetch for PreCallScreen lead loading
globalThis.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve([
        {
          id: "1",
          name: "Test Lead",
          phone: "+44123456789",
          email: "test@example.com",
          call_outcome: null,
          status: "new",
        },
      ]),
  })
);

describe("App", () => {
  it("renders without crashing", () => {
    render(<App />);
    // Should not throw
  });

  it("initially shows Start Call button text (pre-call screen)", () => {
    render(<App />);
    expect(screen.getByText("Start Call")).toBeTruthy();
  });
});

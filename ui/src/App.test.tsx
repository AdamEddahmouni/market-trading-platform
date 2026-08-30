import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./api/hooks", () => ({
  queryKeys: {
    context: ["context"],
    attention: ["attention"],
    assistantMessages: (conversationId: string | null) => ["assistant", conversationId],
    assistantConversations: ["assistant-conversations"],
  },
  useContextQuery: () => ({
    isLoading: false,
    error: null,
    data: {
      as_of_context: {
        mode: "REPLAY",
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
        as_of_time: "2026-08-30T12:00:00Z",
        timezone: "America/New_York",
      },
      capability_states: [],
      quality_summary: { state: "PASS" },
      scope_symbols: ["BIYA"],
    },
  }),
  useAttentionQuery: () => ({ data: { items: [] } }),
  useReplaySessionQuery: () => ({ data: undefined }),
  useAssistantStatusQuery: () => ({ data: undefined }),
  useAssistantMessagesQuery: () => ({ data: undefined, isLoading: false }),
}));

describe("App mode launcher integration", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  async function enterMode(label: "Demo" | "Paper" | "Live") {
    fireEvent.click(await screen.findByRole("button", { name: new RegExp(label, "i") }));
    if (label === "Live") {
      fireEvent.click(screen.getByRole("button", { name: "Enter live data" }));
    }
    await screen.findByRole("navigation", { name: "Primary" });
  }

  it("gates the workstation behind the fresh-session mode launcher", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Choose how you enter the market." }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Loading replay context…")).not.toBeInTheDocument();
  });

  it.each([
    ["Demo", "DEMO"],
    ["Paper", "PAPER"],
    ["Live", "LIVE"],
  ] as const)("opens the real workstation after entering %s", async (label, mode) => {
    render(<App />);

    await enterMode(label);

    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent(mode);
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
    expect(screen.queryByText(/environment ready/i)).not.toBeInTheDocument();
  });

  it("resets the route before switching and re-entering", async () => {
    render(<App />);
    await enterMode("Demo");
    window.history.pushState({}, "", "/workspace/BIYA");

    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    expect(window.location.pathname).toBe("/");

    await enterMode("Demo");
    expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "NOW" })).toHaveClass("active");
  });
});

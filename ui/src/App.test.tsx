import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./api/client";

const replaySession = { cursor_index: 0, event_count: 4 };

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
  useAttentionQuery: () => ({ data: { items: [] }, isLoading: false, error: null }),
  useReplaySessionQuery: () => ({
    isLoading: false,
    error: null,
    data: replaySession,
  }),
  useAssistantStatusQuery: () => ({ data: undefined }),
  useAssistantMessagesQuery: () => ({ data: undefined, isLoading: false }),
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: true,
    data: undefined,
  }),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("App mode launcher integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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

  it("opens the Demo dashboard", async () => {
    render(<App />);
    await enterMode("Demo");
    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("DEMO");
    expect(screen.getByRole("heading", { name: "See the market unfold" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Command Center" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Paper Command" })).not.toBeInTheDocument();
  });

  it("opens Paper Command in Paper mode", async () => {
    render(<App />);
    await enterMode("Paper");
    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("PAPER");
    expect(await screen.findByRole("heading", { name: "Paper Command" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Command Center" })).not.toBeInTheDocument();
  });

  it("keeps Live on Command Center", async () => {
    render(<App />);
    await enterMode("Live");
    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("LIVE");
    expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
  });

  it("resets the route before switching and re-entering", async () => {
    render(<App />);
    await enterMode("Demo");
    window.history.pushState({}, "", "/workspace/BIYA");

    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    expect(window.location.pathname).toBe("/");

    await enterMode("Demo");
    expect(screen.getByRole("heading", { name: "See the market unfold" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "NOW" })).toHaveClass("active");
  });

  it("confirms a scrub before changing the cursor and refreshes existing queries", async () => {
    const scrub = vi.spyOn(api, "scrubReplay").mockResolvedValueOnce({});
    const invalidate = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    render(<App />);
    await enterMode("Demo");
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    await waitFor(() => expect(screen.getByText("Event 2 of 4")).toBeInTheDocument());
    expect(scrub).toHaveBeenCalledWith(1);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["context"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["attention"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["instrument"] });
  });

  it("retains the confirmed cursor and announces a failed scrub", async () => {
    vi.spyOn(api, "scrubReplay").mockRejectedValueOnce(new Error("offline"));
    render(<App />);
    await enterMode("Demo");
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    await screen.findByText(/Replay could not move/);
    expect(screen.getByText("Event 1 of 4")).toBeInTheDocument();
  });
});

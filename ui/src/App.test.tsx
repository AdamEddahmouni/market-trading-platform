import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./api/hooks", () => ({
  queryKeys: {
    context: ["context"],
    attention: ["attention"],
    assistantMessages: (conversationId: string | null) => ["assistant", conversationId],
    assistantConversations: ["assistant-conversations"],
  },
  useContextQuery: () => ({ isLoading: true, error: null, data: undefined }),
  useAttentionQuery: () => ({ data: { items: [] } }),
  useReplaySessionQuery: () => ({ data: undefined }),
  useAssistantStatusQuery: () => ({ data: undefined }),
  useAssistantMessagesQuery: () => ({ data: undefined, isLoading: false }),
}));

describe("App mode launcher integration", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it("gates the workstation behind the fresh-session mode launcher", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Choose how you enter the market." }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Loading replay context…")).not.toBeInTheDocument();
  });
});

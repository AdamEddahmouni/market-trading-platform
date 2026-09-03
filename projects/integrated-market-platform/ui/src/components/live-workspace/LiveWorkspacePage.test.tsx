import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveWorkspacePage } from "./LiveWorkspacePage";

vi.mock("../../api/hooks", () => ({
  useContextQuery: () => ({
    data: {
      as_of_context: {
        mode: "LIVE",
        data_mode: "LIVE_OBSERVATIONAL",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
        as_of_time: "2026-08-30T12:00:00Z",
        timezone: "America/New_York",
        data_provider: "MOOMOO",
      },
      quality_summary: { state: "PASS" },
    },
  }),
  useWorkspaceEvidenceQuery: () => ({ data: undefined, isLoading: false }),
}));

vi.mock("../live/LiveMarketPanel", () => ({
  LiveMarketPanel: () => null,
}));

describe("LiveWorkspacePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it("renders read-only live workspace without order controls", () => {
    render(
      <MemoryRouter>
        <LiveWorkspacePage
          instrumentId="AAPL"
          bars={[]}
          features={[]}
          squeeze={null}
          replayChartAvailable={false}
          onScrub={() => undefined}
          cursorIndex={0}
          maxIndex={0}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
  });
});

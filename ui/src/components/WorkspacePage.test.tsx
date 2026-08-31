import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mode } from "./mode-session/types";
import type { PaperOrderDraft } from "./paper-now/paperOrderDraft";
import { WorkspacePage } from "./WorkspacePage";

const portfolio = {
  account: {
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    data_mode: "FIXTURE_REPLAY",
  },
  risk: { limits: { max_order_shares: 100 } },
};

vi.mock("../api/hooks", () => ({
  useContextQuery: () => ({
    data: {
      as_of_context: {
        mode: "REPLAY",
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "INTERNAL_SIMULATION",
        execution_authority: "PAPER_ONLY",
        as_of_time: "2026-08-30T12:00:00Z",
        timezone: "America/New_York",
      },
      quality_summary: { state: "PASS" },
    },
  }),
  useWorkspaceEvidenceQuery: () => ({ data: undefined, isLoading: false }),
  usePaperPortfolioQuery: () => ({ data: portfolio }),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("./live/LiveMarketPanel", () => ({
  LiveMarketPanel: () => null,
}));

function renderPage(mode: Mode, paperActionsPermitted: boolean, initialPaperOrderDraft?: PaperOrderDraft) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <WorkspacePage
          mode={mode}
          paperActionsPermitted={paperActionsPermitted}
          initialPaperOrderDraft={initialPaperOrderDraft}
          instrumentId="BIYA"
          bars={[]}
          features={[]}
          squeeze={null}
          replayChartAvailable={false}
          onScrub={() => undefined}
          cursorIndex={0}
          maxIndex={0}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("WorkspacePage mode restrictions", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it.each(["DEMO", "LIVE"] as const)(
    "does not render an order ticket in %s",
    (mode) => {
      renderPage(mode, true);

      expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
      expect(screen.getByRole("note")).toHaveTextContent(/controls are unavailable/i);
    },
  );

  it("fails closed when global Paper permission is false", () => {
    renderPage("PAPER", false);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("renders the order ticket for globally and locally authorized Paper", () => {
    renderPage("PAPER", true);

    expect(screen.getByText("Order ticket")).toBeInTheDocument();
  });

  it("passes an accepted draft into the authorized Paper ticket", async () => {
    renderPage("PAPER", true, {
      version: 1,
      instrumentId: "BIYA",
      side: "SELL",
      quantity: 12,
      orderType: "MARKET",
    });

    expect(await screen.findByDisplayValue("12")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SELL" })).toHaveAttribute("aria-pressed", "true");
  });
});

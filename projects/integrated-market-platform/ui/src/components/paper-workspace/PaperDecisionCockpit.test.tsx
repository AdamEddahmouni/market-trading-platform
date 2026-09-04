import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperDecisionCockpit } from "./PaperDecisionCockpit";

const portfolio = {
  account: {
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    data_mode: "FIXTURE_REPLAY",
    session_id: "sess-1",
    currency: "USD",
    buying_power_minor: 10000,
    realized_pnl_display: "$0",
  },
  risk: { limits: { max_order_shares: 100, max_position_shares: 500, max_open_orders: 10 }, kill_switch_active: false, open_order_count: 0, reconciliation_status: "PASS" },
  positions: [],
  orders: [],
  exposure: { gross_shares: 0 },
  pnl: { total_display: "$0" },
  data_health: { state: "PASS" },
  reconciliation_status: "PASS",
};

vi.mock("../../api/hooks", () => ({
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePaperPortfolioQuery: () => ({ data: portfolio, refetch: vi.fn() }),
}));

function renderCockpit(initialPaperOrderDraft?: Parameters<typeof PaperDecisionCockpit>[0]["initialPaperOrderDraft"]) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PaperDecisionCockpit
          instrumentId="BIYA"
          initialPaperOrderDraft={initialPaperOrderDraft}
          portfolio={portfolio as never}
          portfolioPhase="ready"
          paperActionsAvailable
          evidence={undefined}
          evidencePhase="empty"
          dataLabel="Fixture replay"
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperDecisionCockpit", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it("renders decision cockpit without lane handoff", () => {
    renderCockpit();
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByText(/No handoff — review workspace evidence before drafting/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Order ticket" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Handoff from/i })).not.toBeInTheDocument();
  });

  it("renders lane handoff panel for lane draft", () => {
    renderCockpit({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "lane:order-flow",
    });
    expect(screen.getByRole("heading", { name: /Handoff from Order Flow/i })).toBeInTheDocument();
    expect(screen.getByText(/Preview status/i)).toBeInTheDocument();
  });

  it("renders attention handoff panel for Paper Command draft", () => {
    renderCockpit({
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "attention-biya",
      sourceContext: { headline: "BIYA setup", tier: 1, reasons: [{ code: "PRICE_VOLUME", label: "Expanded" }] },
    });
    expect(screen.getByRole("heading", { name: "Attention handoff" })).toBeInTheDocument();
    expect(screen.getByText(/Opened from Paper Command attention attention-biya/i)).toBeInTheDocument();
    expect(screen.getByText("BIYA setup")).toBeInTheDocument();
  });
});

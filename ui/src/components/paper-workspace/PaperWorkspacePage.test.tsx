import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import { PaperWorkspacePage } from "./PaperWorkspacePage";

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

const evidence = {
  instrument: "BIYA",
  as_of_context: {
    mode: "REPLAY",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    as_of_time: "2026-08-31T12:00:00Z",
    timezone: "America/New_York",
  },
  lanes: [],
  what_matters_now: [],
  evidence_mix_summary: "MIXED",
  research_context_execution_authority: "RESEARCH_ONLY",
};

vi.mock("../../api/hooks", () => ({
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
  useWorkspaceEvidenceQuery: () => ({ data: evidence, isLoading: false, isError: false }),
  usePaperPortfolioQuery: () => ({ data: portfolio, isLoading: false, isError: false }),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("../live/LiveMarketPanel", () => ({
  LiveMarketPanel: () => null,
}));

const observabilityProps = {
  instrumentId: "BIYA",
  bars: [],
  features: [],
  squeeze: null,
  replayChartAvailable: false,
  onScrub: () => undefined,
  cursorIndex: 0,
  maxIndex: 0,
};

function renderPage(paperActionsPermitted: boolean, initialPaperOrderDraft?: PaperOrderDraft) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PaperWorkspacePage
          {...observabilityProps}
          paperActionsPermitted={paperActionsPermitted}
          initialPaperOrderDraft={initialPaperOrderDraft}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperWorkspacePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );
  });

  it("fails closed when global Paper permission is false", () => {
    renderPage(false);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Paper authority unavailable/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
  });

  it("renders the decision cockpit and order ticket for authorized Paper", () => {
    renderPage(true);

    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preview status" })).toBeInTheDocument();
    expect(screen.getByText("Order ticket")).toBeInTheDocument();
  });

  it("passes an accepted draft into the authorized Paper ticket", async () => {
    renderPage(true, {
      version: 1,
      instrumentId: "BIYA",
      side: "SELL",
      quantity: 12,
      orderType: "MARKET",
    });

    expect(await screen.findByDisplayValue("12")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SELL" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows lane handoff panel when draft provenance is from a workspace lane", () => {
    renderPage(true, {
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "lane:squeeze",
    });

    expect(screen.getByRole("heading", { name: /Handoff from Short Squeeze/i })).toBeInTheDocument();
    expect(screen.getByText(/placeholder, not a recommendation/i)).toBeInTheDocument();
    expect(screen.getByText(/Origin:/i)).toBeInTheDocument();
  });

  it("shows attention handoff panel when draft provenance is from Paper Command", () => {
    renderPage(true, {
      version: 1,
      instrumentId: "BIYA",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: "attention-biya",
      sourceContext: {
        headline: "BIYA setup",
        tier: 1,
        reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
      },
    });

    expect(screen.getByRole("heading", { name: "Attention handoff" })).toBeInTheDocument();
    expect(screen.getByText("BIYA setup")).toBeInTheDocument();
    expect(screen.getAllByText(/attention-biya/).length).toBeGreaterThan(0);
  });

  it("shows neutral entry without fake handoff on direct workspace entry", () => {
    renderPage(true);
    expect(screen.getByText(/No handoff — review workspace evidence before drafting/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Handoff from/i })).not.toBeInTheDocument();
  });
});

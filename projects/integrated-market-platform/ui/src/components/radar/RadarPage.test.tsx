import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { RadarPage } from "./RadarPage";

const summaryMock = vi.hoisted(() => ({
  data: {
    items: [] as OpportunityReviewRow[],
    feed_status: "EMPTY" as string,
    unready_reason: undefined as string | undefined,
    next_action: undefined as string | undefined,
  },
  isLoading: false,
  isError: false,
}));

const ackMutate = vi.hoisted(() => vi.fn());

const mediaState = vi.hoisted(() => ({ narrow: false }));

vi.stubGlobal(
  "matchMedia",
  (query: string) => ({
    matches: mediaState.narrow && query.includes("max-width"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
);

vi.mock("../../api/opportunityClient", () => ({
  useOpportunitiesSummaryQuery: () => ({
    data: summaryMock.data,
    isLoading: summaryMock.isLoading,
    isError: summaryMock.isError,
    refetch: vi.fn(),
  }),
  useOpportunityEvidenceQuery: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  useOpportunityAckMutation: () => ({ mutate: ackMutate, isPending: false }),
}));

vi.mock("../../api/hooks", async () => {
  const actual = await vi.importActual<typeof import("../../api/hooks")>("../../api/hooks");
  return {
    ...actual,
    usePaperPortfolioQuery: () => ({
      isLoading: false,
      isError: false,
      data: { account: { paper_account_id: "paper-acct-1" } },
    }),
    useExploreSqueezeQuery: () => ({ isLoading: false, data: undefined }),
    useExploreSqueezeScannerQuery: () => ({ isLoading: false, data: undefined }),
    useExploreFuturesQuery: () => ({ isLoading: false, data: undefined }),
    useExploreCatalystQuery: () => ({ isLoading: false, data: undefined }),
  };
});

vi.mock("../../api/tradeReviewClient", () => ({
  useTradeReviewsQuery: () => ({ data: { items: [] }, isLoading: false, isError: false }),
}));

const rankedRow: OpportunityReviewRow = {
  summary_id: "sum-1",
  instrument_id: "BIYA",
  headline: "BIYA momentum ignition watch",
  opportunity_id: "opp-1",
  identity_kind: "OPPORTUNITY_V1",
  eligibility_state: "ELIGIBLE",
  lifecycle_state: "ACTIVE",
  next_safe_action: "OPEN_WORKSPACE",
  rank_order: 1,
  explanation_ref: "explain:opportunity:opp-1",
  ranking_vector: {
    basis: "COMPARATOR_LEXICOGRAPHIC",
    dimensions: [
      { name: "attention_score", status: "PRESENT", value: 74.5 },
      { name: "freshness", status: "PRESENT", value: "FRESH" },
      { name: "liquidity", status: "MISSING" },
    ],
    rank_order: 1,
  },
  data_quality: { status: "PASS", freshness: "FRESH", source: "unit-test" },
};

const mixedPayload = {
  available: true,
  mode: "SEMI_LIVE",
  candidate_role: "INVESTIGATE",
  execution_authority: "NONE",
  market_session: "REGULAR",
  generated_at: "2026-08-24T15:00:00Z",
  discovery_as_of: "2026-08-24T14:59:00Z",
  candidate_count: 2,
  live_subscription_summary: { active: 1, cap: 12 },
  refresh_in_progress: false,
  refresh_interval_seconds: 120,
  poll_interval_seconds: 3,
  provider_health: [
    { provider: "FINVIZ_ELITE", connection: "HEALTHY", role: "DISCOVERY", reason: null },
    { provider: "MOOMOO", connection: "CONNECTED", reason: null, subscribed_candidates: 1 },
  ],
  lane_counts: { MOMENTUM: 1, SQUEEZE: 1 },
  screen_outcomes: [
    { screen_id: "UNUSUAL_VOLUME_DISCOVERY", status: "PASS", candidate_count: 1, reason: null },
  ],
  candidates: [
    {
      instrument_id: "AAPL",
      candidate_role: "INVESTIGATE",
      lanes: ["MOMENTUM"],
      screen_matches: ["UNUSUAL_VOLUME_DISCOVERY"],
      matched_reasons: ["UNUSUAL_VOLUME"],
      metrics: { price: 101, change_pct: 4.2, rel_volume: 3.1, volume: 1250000 },
      discovery_as_of: "2026-08-24T14:59:00Z",
      quality: "PASS",
      provenance: [{ provider: "FINVIZ_ELITE", screen_id: "UNUSUAL_VOLUME_DISCOVERY" }],
      attention_score: 74.5,
      attention_components: { setup_strength: 31 },
      ranking_reasons: ["RVOL_3.10", "FRESH_L1_QUOTE"],
      supporting_evidence: ["relative volume 3.10x exceeds baseline"],
      caveats: ["no verified catalyst"],
      market: {
        provider: "MOOMOO",
        status: "LIVE",
        last_price: 101.2,
        bid_price: 101.1,
        ask_price: 101.3,
        spread_pct: 0.1978,
        volume: 1300000,
        quality: "PASS",
        reason: null,
      },
      data_status: "LIVE",
      freshness_label: "480 ms",
      queue_rank: 1,
    },
    {
      instrument_id: "GME",
      candidate_role: "INVESTIGATE",
      lanes: ["SQUEEZE"],
      screen_matches: ["SHORT_SQUEEZE_DISCOVERY"],
      matched_reasons: ["HIGH_SHORT_FLOAT"],
      metrics: { price: 24.1, short_float_pct: 22.4 },
      discovery_as_of: "2026-08-24T14:58:00Z",
      quality: "PASS",
      provenance: [{ provider: "FINVIZ_ELITE", screen_id: "SHORT_SQUEEZE_DISCOVERY" }],
      attention_score: 48,
      attention_components: { setup_strength: 20 },
      ranking_reasons: ["SHORT_FLOAT_22.4_PCT"],
      market: {
        provider: "FINVIZ_ELITE",
        status: "UNAVAILABLE",
        last_price: 24.1,
        quality: "PASS",
        reason: "NOT_SUBSCRIBED",
      },
      data_status: "UNAVAILABLE",
      freshness_label: "UNAVAILABLE",
      queue_rank: 2,
    },
  ],
};

function jsonResponse(payload: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);
}

function renderRadar(
  mode: "DEMO" | "PAPER" | "LIVE",
  tab: "opportunities" | "screeners" = "opportunities",
  paperActionsPermitted = false,
  initialPath?: string,
) {
  const path = initialPath ?? (tab === "screeners" ? "/radar/screeners" : "/radar");
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/radar"
          element={
            <RadarPage
              mode={mode}
              tab="opportunities"
              paperActionsPermitted={paperActionsPermitted}
              onExplain={vi.fn()}
              onExplainRef={vi.fn()}
              onInspect={vi.fn()}
              onOpenWorkspace={vi.fn()}
            />
          }
        />
        <Route
          path="/radar/screeners"
          element={
            <RadarPage
              mode={mode}
              tab="screeners"
              paperActionsPermitted={paperActionsPermitted}
              onExplain={vi.fn()}
              onExplainRef={vi.fn()}
              onInspect={vi.fn()}
              onOpenWorkspace={vi.fn()}
            />
          }
        />
        <Route path="/workspace/:instrumentId" element={<div>Workspace opened</div>} />
        <Route path="/control" element={<div>Control</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RadarPage opportunities tab", () => {
  beforeEach(() => {
    summaryMock.data = { items: [], feed_status: "EMPTY", unready_reason: undefined, next_action: undefined };
    summaryMock.isLoading = false;
    summaryMock.isError = false;
    ackMutate.mockClear();
    mediaState.narrow = false;
  });

  it("renders the page header and tabs", () => {
    renderRadar("PAPER", "opportunities", true);
    expect(screen.getByRole("heading", { name: "Radar" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Radar sections" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Opportunities" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("explains why the queue is empty", () => {
    renderRadar("DEMO");
    expect(screen.getByText(/No opportunities right now/i)).toBeInTheDocument();
    expect(screen.getByText(/empty queue is valid/i)).toBeInTheDocument();
  });

  it("renders the feed UNREADY state as a human banner with an action", () => {
    summaryMock.data = {
      items: [],
      feed_status: "UNREADY",
      unready_reason: "PROVIDER_WARMUP",
      next_action: "/control",
    };
    renderRadar("PAPER", "opportunities", true);
    expect(screen.getByRole("status")).toHaveTextContent(/Opportunity radar isn't ready/);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute("href", "/control");
  });

  it("renders the live by-design empty state when the feed is unavailable", () => {
    summaryMock.data = { items: [], feed_status: "UNAVAILABLE", unready_reason: undefined, next_action: undefined };
    renderRadar("LIVE");
    expect(screen.getByTestId("imp-ui-empty-state")).toHaveTextContent(
      /Live mode has no opportunity engine/i,
    );
  });

  it("treats a non-live UNAVAILABLE feed as a fault with a Control action", () => {
    summaryMock.data = { items: [], feed_status: "UNAVAILABLE", unready_reason: undefined, next_action: "/control" };
    renderRadar("PAPER", "opportunities", true);
    const empty = screen.getByTestId("imp-ui-empty-state");
    expect(empty).toHaveTextContent(/Opportunity feed unavailable/i);
    expect(empty).not.toHaveTextContent(/Live mode has no opportunity engine/i);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute("href", "/control");
  });

  it("renders the error state with retry", () => {
    summaryMock.isError = true;
    renderRadar("PAPER", "opportunities", true);
    expect(screen.getByRole("alert")).toHaveTextContent(/Opportunity ranking is unavailable/);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders ranked rows with state, evidence, freshness, and next action", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const queue = screen.getByTestId("imp-radar-queue");
    expect(queue).toHaveTextContent("BIYA momentum ignition watch");
    expect(queue).toHaveTextContent("2/3 inputs");
    expect(queue).toHaveTextContent("Fresh");
    expect(queue).toHaveTextContent("Open workspace");
    expect(queue).toHaveTextContent("Detected");
  });

  it("selects a row and shows the progressive detail card", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const card = await screen.findByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("BIYA momentum ignition watch");
    expect(card).toHaveTextContent("2 of 3 ranking inputs present");
    // L2 epistemic layers (Evidence layers) open by default; deeper sections stay collapsed
    expect(within(card).getByText("Evidence layers")).toBeInTheDocument();
    expect(card).toHaveTextContent("Observed facts");
    expect(card).toHaveTextContent("Data freshness");
    const technical = screen.getByText("Technical details");
    fireEvent.click(technical);
    expect(card).toHaveTextContent("summary_id");
    fireEvent.click(screen.getByText("Historical & research context"));
    expect(screen.getByRole("link", { name: "Open Research evidence" })).toHaveAttribute(
      "href",
      "/research/evidence",
    );
  });

  it("offers watch/dismiss/review acks only with paper authority", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const card = screen.getByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("paper-acct-1");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(ackMutate).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" });
  });

  it("hides acks without paper authority and says so", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", false);
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    expect(screen.getByText(/Paper actions unavailable in this mode/i)).toBeInTheDocument();
  });

  it("marks demo read-only", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("DEMO");
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getAllByText(/Read-only in this mode/i).length).toBeGreaterThan(0);
  });

  it("keeps detail inline on wide layouts without a sheet", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    expect(await screen.findByTestId("imp-radar-detail-card")).toBeInTheDocument();
    const queue = screen.getByTestId("imp-radar-queue");
    fireEvent.click(within(queue).getByText("BIYA momentum ignition watch"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("follows the Command bridge deep link to the preselected row", async () => {
    const bridgedRow: OpportunityReviewRow = {
      ...rankedRow,
      summary_id: "att-strategy-9",
      opportunity_id: null,
      identity_kind: "NOT_OPPORTUNITY_V1",
      headline: "Strategy signal review",
      rank_order: 2,
    };
    summaryMock.data = { items: [rankedRow, bridgedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true, "/radar?selected=att-strategy-9");
    const card = await screen.findByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("Strategy signal review");
    expect(card).not.toHaveTextContent("BIYA momentum ignition watch");
  });
});

describe("RadarPage mobile detail sheet", () => {
  beforeEach(() => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    summaryMock.isLoading = false;
    summaryMock.isError = false;
    ackMutate.mockClear();
    mediaState.narrow = true;
  });

  it("opens the detail as a dismissable sheet and keeps the queue scannable", async () => {
    renderRadar("PAPER", "opportunities", true);
    // Narrow layout: no inline detail column, queue stays visible.
    expect(screen.queryByTestId("imp-radar-detail-card")).not.toBeInTheDocument();
    expect(screen.getByTestId("imp-radar-queue")).toBeInTheDocument();

    fireEvent.click(screen.getByText("BIYA momentum ignition watch"));
    const sheet = await screen.findByRole("dialog");
    expect(sheet).toHaveAttribute("aria-label", "Opportunity detail");
    expect(sheet).toHaveTextContent("BIYA momentum ignition watch");
    expect(sheet).toHaveTextContent("2 of 3 ranking inputs present");
    // Queue context is preserved behind the sheet.
    expect(screen.getByTestId("imp-radar-queue")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close detail" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape and reopens on the next selection", async () => {
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(screen.getByText("BIYA momentum ignition watch"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("BIYA momentum ignition watch"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("keeps paper ack gating identical inside the sheet", async () => {
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(screen.getByText("BIYA momentum ignition watch"));
    const sheet = await screen.findByRole("dialog");
    fireEvent.click(within(sheet).getByRole("button", { name: "Watch" }));
    expect(ackMutate).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" });
  });
});

describe("RadarPage screeners tab", () => {
  beforeEach(() => {
    summaryMock.data = { items: [], feed_status: "EMPTY", unready_reason: undefined, next_action: undefined };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string | URL | Request) => {
        const path = typeof url === "string" ? url : url.toString();
        if (path.includes("/discover/mixed/release")) {
          return jsonResponse({ released_symbols: 0 });
        }
        return jsonResponse(mixedPayload);
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it("hosts the mixed live screener with explicit market-data status", async () => {
    renderRadar("PAPER", "screeners", true);
    expect(await screen.findByRole("heading", { name: "Mixed live screener" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mixed Live" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("EXEC NONE · INVESTIGATE only")).toBeInTheDocument();
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("LIVE · 480 ms")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/discover/mixed/refresh",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("filters lanes and keeps inspectable ranking evidence", async () => {
    renderRadar("PAPER", "screeners", true);
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: "SQUEEZE" }));
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.getByText("GME")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Evidence"));
    expect(screen.getByText(/SHORT_FLOAT_22.4_PCT/)).toBeInTheDocument();
  });

  it("uses the read-only projection for three-second polling and pauses when hidden", async () => {
    vi.useFakeTimers();
    renderRadar("PAPER", "screeners", true);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole("heading", { name: "Mixed live screener" })).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(3_000);
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledWith("/discover/mixed", expect.objectContaining({ method: "GET" }));

    const callsBeforeHidden = vi.mocked(fetch).mock.calls.length;
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => {
      vi.advanceTimersByTime(120_000);
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledTimes(callsBeforeHidden);
  });

  it("promotes only after an explicit workspace action", async () => {
    renderRadar("PAPER", "screeners", true);
    await screen.findByText("AAPL");
    fireEvent.click(screen.getAllByRole("button", { name: "Open Workspace" })[0]);
    expect(await screen.findByText("Workspace opened")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/discover/promote-to-live-analysis",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ instrument_id: "AAPL" }) }),
    );
  });

  it("hides refresh mutations in Demo and Live", async () => {
    const { unmount } = renderRadar("DEMO", "screeners");
    await screen.findByText("AAPL");
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
    unmount();
    renderRadar("LIVE", "screeners");
    await screen.findAllByText("AAPL");
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open live canary" })).toBeInTheDocument();
  });

  it("bridges research screens to the Research evidence finding", async () => {
    renderRadar("PAPER", "screeners", true);
    expect(
      await screen.findByRole("link", { name: "Open the research evidence behind these screens" }),
    ).toHaveAttribute("href", "/research/evidence?panel=squeeze_outcomes");
  });
});

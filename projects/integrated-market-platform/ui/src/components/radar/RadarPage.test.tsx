import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
    withheld_ranked_count: undefined as number | undefined,
    book_honesty: undefined as string | undefined,
    as_of_context: undefined as
      | {
          mode: string;
          data_mode?: string;
          as_of_time: string;
          timezone: string;
          data_provider?: string;
          as_of_provenance?: string;
        }
      | undefined,
    quality_summary: undefined as { state: string } | undefined,
  },
  isLoading: false,
  isError: false,
}));

const ackMutateAsync = vi.hoisted(() =>
  vi.fn(async (vars: { rowId: string; action: string }) => ({
    summary_id: vars.rowId.startsWith("opp-") ? `sum-${vars.rowId.slice(4)}` : vars.rowId,
    opportunity_id: vars.rowId,
    action: vars.action === "watch" ? "WATCHED" : vars.action === "dismiss" ? "DISMISSED" : "REVIEWED",
    trade_review_id: `tr-${vars.rowId}`,
    decision_trace_mode: "CONTROLLED_REPLAY",
    created_at_ns: 1,
  })),
);

const tradeReviewsFetch = vi.hoisted(() =>
  vi.fn(async (opportunityId: string) => ({
    opportunity_id: opportunityId,
    items: [] as Array<{ review_id: string; review_mode: string; decision: string; notes?: string }>,
  })),
);

const tradeReviewStore = vi.hoisted(() => ({
  items: [] as Array<{ review_id: string; review_mode: string; decision: string; notes?: string }>,
  listeners: new Set<() => void>(),
}));

const contextMock = vi.hoisted(() => ({
  data: {
    as_of_context: {
      mode: "REPLAY",
      data_mode: "FIXTURE_REPLAY",
      as_of_time: "2026-09-22T14:05:08Z",
      timezone: "America/New_York",
      controlled_replay: false,
      evidence_class: undefined as string | undefined,
      execution_authority: "BLOCKED",
    },
  },
}));

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
  useOpportunityAckMutation: () => ({
    mutate: vi.fn(),
    mutateAsync: ackMutateAsync,
    isPending: false,
  }),
}));

vi.mock("../../api/hooks", async () => {
  const actual = await vi.importActual<typeof import("../../api/hooks")>("../../api/hooks");
  return {
    ...actual,
    useContextQuery: () => ({
      isLoading: false,
      isError: false,
      data: contextMock.data,
    }),
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
  getTradeReviewsForOpportunity: async (opportunityId: string) => {
    const result = await tradeReviewsFetch(opportunityId);
    tradeReviewStore.items = result.items ?? [];
    tradeReviewStore.listeners.forEach((listener) => listener());
    return result;
  },
  useTradeReviewsQuery: (opportunityId: string | null | undefined, enabled = true) => {
    // Local require keeps the mock free of top-level React import cycles.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const React = require("react") as typeof import("react");
    const [, setTick] = React.useState(0);
    React.useEffect(() => {
      if (!enabled || !opportunityId) return undefined;
      const listener = () => setTick((value: number) => value + 1);
      tradeReviewStore.listeners.add(listener);
      void tradeReviewsFetch(String(opportunityId)).then((result) => {
        tradeReviewStore.items = result.items ?? [];
        listener();
      });
      return () => {
        tradeReviewStore.listeners.delete(listener);
      };
    }, [enabled, opportunityId]);
    return {
      data: { opportunity_id: String(opportunityId ?? ""), items: tradeReviewStore.items },
      isLoading: false,
      isError: false,
      isFetching: false,
    };
  },
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
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
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
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RadarPage opportunities tab", () => {
  beforeEach(() => {
    summaryMock.data = { items: [], feed_status: "EMPTY", unready_reason: undefined, next_action: undefined };
    summaryMock.isLoading = false;
    summaryMock.isError = false;
    ackMutateAsync.mockReset();
    ackMutateAsync.mockImplementation(async (vars: { rowId: string; action: string }) => ({
      summary_id: vars.rowId.startsWith("opp-") ? `sum-${vars.rowId.slice(4)}` : vars.rowId,
      opportunity_id: vars.rowId,
      action: vars.action === "watch" ? "WATCHED" : vars.action === "dismiss" ? "DISMISSED" : "REVIEWED",
      trade_review_id: `tr-${vars.rowId}`,
      decision_trace_mode: "CONTROLLED_REPLAY",
      created_at_ns: 1,
    }));
    tradeReviewsFetch.mockReset();
    tradeReviewsFetch.mockImplementation(async (opportunityId: string) => ({
      opportunity_id: opportunityId,
      items: [
        {
          review_id: `tr-${opportunityId}`,
          review_mode: "WATCHED_OPPORTUNITY",
          decision: "WATCH",
          notes: "durable",
        },
      ],
    }));
    tradeReviewStore.items = [];
    tradeReviewStore.listeners.clear();
    mediaState.narrow = false;
    contextMock.data.as_of_context.controlled_replay = false;
    contextMock.data.as_of_context.evidence_class = undefined;
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
    expect(screen.getByText(/investigation screener on the Screeners tab/i)).toBeInTheDocument();
    expect(screen.queryByText(/mixed live/i)).not.toBeInTheDocument();
  });

  it("does not call Paper discovery a mixed live screener", () => {
    renderRadar("PAPER", "opportunities", true);
    expect(
      screen.getByText(/Ranked opportunities, the investigation screener, and donor research screens/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/mixed live/i)).not.toBeInTheDocument();
  });

  it("does not call Live Radar a discovery-surface monitor", () => {
    renderRadar("LIVE");
    expect(
      screen.getByText(/Read-only monitor over investigation surfaces/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/discovery surfaces/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Live is read-only here/i)).toBeInTheDocument();
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

  it("explains withheld live rows when the receive clock is missing", () => {
    summaryMock.data = {
      items: [],
      feed_status: "UNREADY",
      unready_reason: "LIVE_AS_OF_UNAVAILABLE",
      next_action: "/control",
      withheld_ranked_count: 3,
      book_honesty: "RANKED_ROWS_WITHHELD_NO_LIVE_CLOCK",
    };
    renderRadar("LIVE", "opportunities", false);
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent(/live clock is unavailable/i);
    expect(banner).toHaveTextContent(/withheld 3 ranked row/i);
    expect(banner).toHaveTextContent(/not Item 9 calibration/i);
    expect(banner).toHaveTextContent(/Live execution stays OFF/i);
    expect(banner).not.toHaveTextContent(/3\/3/);
    expect(banner).not.toHaveTextContent(/CALIBRATED/);
    const brief = screen.getByTestId("imp-radar-operator-brief");
    expect(brief).toHaveTextContent("How fresh?");
    expect(brief).toHaveTextContent(/NOT_APPLICABLE/);
    expect(brief).toHaveTextContent("How many ranked rows were withheld?");
    expect(brief).toHaveTextContent(/withheld 3 ranked row/);
    expect(brief).toHaveTextContent("What would invalidate it?");
    expect(brief).toHaveTextContent(/missing live receive clock/i);
    expect(brief).toHaveTextContent("Why might action be refused?");
    expect(brief).toHaveTextContent(/never grants live execution/i);
    expect(brief).not.toHaveTextContent(/3\/3/);
    expect(brief).not.toHaveTextContent(/CALIBRATED/);
  });

  it("renders the live by-design empty state when the feed is unavailable", () => {
    summaryMock.data = { items: [], feed_status: "UNAVAILABLE", unready_reason: undefined, next_action: undefined };
    renderRadar("LIVE");
    const empty = screen.getByTestId("imp-ui-empty-state");
    expect(empty).toHaveAttribute("aria-label", "Live has no opportunity engine");
    expect(empty).toHaveTextContent(/by design, not a feed fault/i);
    expect(empty).toHaveTextContent(/Live execution stays OFF/i);
    expect(empty).not.toHaveTextContent(/Opportunity feed unavailable/i);
    expect(empty).not.toHaveTextContent(/cannot be trusted/i);
  });

  it("treats a non-live UNAVAILABLE feed as a fault with a Control action", () => {
    summaryMock.data = { items: [], feed_status: "UNAVAILABLE", unready_reason: undefined, next_action: "/control" };
    renderRadar("PAPER", "opportunities", true);
    const empty = screen.getByTestId("imp-ui-empty-state");
    expect(empty).toHaveTextContent(/Opportunity feed unavailable/i);
    expect(empty).not.toHaveTextContent(/Live has no opportunity engine/i);
    expect(empty).not.toHaveTextContent(/Live mode has no opportunity engine/i);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute("href", "/control");
  });

  it("renders the error state with retry", () => {
    summaryMock.isError = true;
    renderRadar("PAPER", "opportunities", true);
    expect(screen.getByRole("alert")).toHaveTextContent(/Opportunity ranking is unavailable/);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders ranked rows with an opportunity-first L1 scan instead of a next-action CTA", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const queue = screen.getByTestId("imp-radar-queue");
    const scan = within(queue).getByTestId("imp-radar-queue-scan");
    expect(screen.getByTestId("imp-radar-feed-truth")).toBeInTheDocument();
    expect(queue).toHaveTextContent("2/3 inputs");
    expect(queue).toHaveTextContent("Detected");
    expect(queue).toHaveTextContent("Ranked on Comparator lexicographic");
    expect(scan).toHaveTextContent("Inference vs observation?");
    expect(scan).toHaveTextContent("BIYA momentum ignition watch");
    expect(scan).toHaveTextContent("not a provider observation");
    expect(queue).toHaveTextContent("unit-test");
    expect(queue).toHaveTextContent(/Never grants live execution/i);
    // Missing conflict fields stay UNKNOWN — never a verified empty set.
    expect(queue).toHaveTextContent(/UNKNOWN — no conflict or supersession fields attached/i);
    expect(queue).not.toHaveTextContent(/No attached conflicts/i);
    const conflictBlock = Array.from(queue.querySelectorAll("[data-honesty]")).find((el) =>
      /no conflict or supersession fields attached/i.test(el.textContent ?? ""),
    );
    expect(conflictBlock).toBeDefined();
    expect(conflictBlock).toHaveAttribute("data-honesty", "UNKNOWN");
    expect(
      within(conflictBlock as HTMLElement).getByText("UNKNOWN", {
        selector: ".imp-radar-brief-honesty",
      }),
    ).toBeInTheDocument();
    expect(scan).not.toHaveTextContent("What action is available?");
    expect(within(queue).queryByText("Open workspace")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Watch BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Explain BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open workspace for BIYA" })).toBeInTheDocument();
    const brief = within(screen.getByTestId("imp-radar-detail-card")).getByTestId(
      "imp-radar-operator-brief",
    );
    expect(brief).toHaveTextContent("Why might action be refused?");
    expect(brief).toHaveTextContent("never grants live execution");
    expect(brief).toHaveTextContent("What is unknown?");
    expect(brief).toHaveTextContent("ranking.liquidity MISSING");
  });

  it("renders backend provider_linkage_warnings and invents nothing when empty", () => {
    const warned: OpportunityReviewRow = {
      ...rankedRow,
      instrument_id: "NVDA",
      headline: "MillerKnoll announces new lineup",
      provider_linkage_warnings: ["uncorroborated", "contextual concern"],
    };
    summaryMock.data = {
      items: [warned],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    const detail = screen.getByTestId("imp-radar-detail-card");
    expect(within(detail).getByTestId("imp-radar-provider-linkage-warnings")).toHaveTextContent(
      "uncorroborated, contextual concern",
    );
    const brief = within(detail).getByTestId("imp-radar-operator-brief");
    expect(brief).toHaveTextContent("Provider linkage?");
    expect(brief).toHaveTextContent("uncorroborated, contextual concern");
    expect(detail).not.toHaveTextContent(/wrong ticker/i);
    expect(detail).toHaveTextContent("NVDA");
  });

  it("omits provider linkage UI when the backend array is empty", () => {
    summaryMock.data = {
      items: [rankedRow],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    expect(screen.queryByTestId("imp-radar-provider-linkage-warnings")).not.toBeInTheDocument();
    expect(screen.getByTestId("imp-radar-operator-brief")).not.toHaveTextContent("Provider linkage?");
  });

  it("posts watch/dismiss from the queue through the existing ack API", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(screen.getByRole("button", { name: "Watch BIYA" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Watch BIYA" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Dismiss BIYA" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "dismiss" }),
    );
  });

  it("moves selection with keyboard and watches/dismisses via w/d when paper-gated", async () => {
    const second: OpportunityReviewRow = {
      ...rankedRow,
      summary_id: "sum-2",
      opportunity_id: "opp-2",
      instrument_id: "GME",
      headline: "GME squeeze continuation",
      rank_order: 2,
    };
    summaryMock.data = {
      items: [rankedRow, second],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    const firstCard = await screen.findByTestId("imp-radar-detail-card");
    expect(firstCard).toHaveTextContent("BIYA momentum ignition watch");
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => {
      expect(screen.getByTestId("imp-radar-detail-card")).toHaveTextContent("GME squeeze continuation");
    });
    fireEvent.keyDown(window, { key: "w" });
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-2", action: "watch" }),
    );
    await waitFor(() => expect(tradeReviewsFetch).toHaveBeenCalled());
    fireEvent.keyDown(window, { key: "d" });
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-2", action: "dismiss" }),
    );
  });

  it("selects a row and shows the progressive detail card", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const card = await screen.findByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("BIYA momentum ignition watch");
    expect(card).toHaveTextContent("2 of 3 ranking inputs present");
    const brief = within(card).getByTestId("imp-radar-operator-brief");
    expect(brief).toHaveTextContent("What happened?");
    expect(brief).toHaveTextContent("Why is IMP showing this?");
    expect(brief).toHaveTextContent("How fresh?");
    expect(brief).toHaveTextContent("Where is the evidence?");
    expect(brief).toHaveTextContent("Which providers support it?");
    expect(brief).toHaveTextContent("Which facts conflict?");
    expect(brief).toHaveTextContent("Inference vs observation?");
    expect(brief).toHaveTextContent("What is unknown?");
    expect(brief).toHaveTextContent("What would invalidate it?");
    expect(brief).toHaveTextContent("What action is available?");
    expect(brief).toHaveTextContent("Why might action be refused?");
    expect(brief).toHaveTextContent("UNKNOWN — no conflict or supersession fields attached");
    expect(brief).toHaveTextContent("never grants live execution");
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

  it("offers watch/dismiss/review acks only with paper authority", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const card = screen.getByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("paper-acct-1");
    fireEvent.click(within(card).getByRole("button", { name: "Watch" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
    await waitFor(() => expect(within(card).getByRole("button", { name: "Watch" })).not.toBeDisabled());
    fireEvent.click(within(card).getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "dismiss" }),
    );
  });

  it("offers Preview in Paper only for watched eligible Paper rows and opens workspace with opportunity handoff", async () => {
    const watched: OpportunityReviewRow = {
      ...rankedRow,
      lifecycle_state: "WATCHED",
    };
    summaryMock.data = { items: [watched], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const card = screen.getByTestId("imp-radar-detail-card");
    expect(screen.getByTestId("imp-radar-preview-in-paper")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview in Paper" }));
    await waitFor(() => expect(screen.getByText("Workspace opened")).toBeInTheDocument());
  });

  it("hides Preview in Paper when the opportunity is not watched", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    expect(screen.queryByTestId("imp-radar-preview-in-paper")).not.toBeInTheDocument();
  });

  it("hides Preview in Paper for controlled-replay learning acks without Paper authority", () => {
    contextMock.data.as_of_context.controlled_replay = true;
    contextMock.data.as_of_context.evidence_class = "CONTROLLED_REPLAY";
    summaryMock.data = {
      items: [{ ...rankedRow, lifecycle_state: "WATCHED" }],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("DEMO", "opportunities", false);
    expect(screen.queryByTestId("imp-radar-preview-in-paper")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Watch" })).toBeInTheDocument();
    contextMock.data.as_of_context.controlled_replay = false;
    contextMock.data.as_of_context.evidence_class = undefined;
  });

  it("refuses Preview in Paper when eligibility fails even if previously watched", () => {
    summaryMock.data = {
      items: [
        {
          ...rankedRow,
          lifecycle_state: "WATCHED",
          eligibility_state: "INELIGIBLE",
          next_safe_action: "STOP",
        },
      ],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    expect(screen.queryByTestId("imp-radar-preview-in-paper")).not.toBeInTheDocument();
  });

  it("hides acks without paper authority and says so", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", false);
    expect(screen.queryByRole("button", { name: "Watch BIYA" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    expect(screen.getByText(/Paper actions unavailable in this mode/i)).toBeInTheDocument();
  });

  it("marks demo read-only", () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("DEMO");
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(/exploration only/i);
    expect(note).toHaveTextContent(/full investigation desk/i);
    expect(note).not.toHaveTextContent(/discovery desk/i);
    expect(screen.getByText(/investigation screeners on recorded data/i)).toBeInTheDocument();
    expect(screen.queryByText(/discovery screeners/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Read-only in this mode/i).length).toBeGreaterThan(0);
  });

  it("enables Watch/Dismiss on DEMO when backend marks controlled_replay", async () => {
    contextMock.data.as_of_context.controlled_replay = true;
    contextMock.data.as_of_context.evidence_class = "CONTROLLED_REPLAY";
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("DEMO", "opportunities", false);
    expect(screen.getByText(/CONTROLLED REPLAY · NOT LIVE MARKET DATA/i)).toBeInTheDocument();
    const card = screen.getByTestId("imp-radar-detail-card");
    expect(card).toHaveTextContent("controlled-replay-operator");
    fireEvent.click(within(card).getByRole("button", { name: "Watch" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
    await waitFor(() => expect(within(card).getByRole("button", { name: "Watch" })).not.toBeDisabled());
    fireEvent.click(within(card).getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "dismiss" }),
    );
    contextMock.data.as_of_context.controlled_replay = false;
    contextMock.data.as_of_context.evidence_class = undefined;
  });

  it("keeps STALE rows honest and refuses Live paper acks", async () => {
    const staleRow: OpportunityReviewRow = {
      ...rankedRow,
      data_quality: { status: "DEGRADED", freshness: "STALE", source: "unit-test" },
      eligibility_state: "INELIGIBLE",
      next_safe_action: "STOP",
      lifecycle_state: "EXPIRED",
    };
    summaryMock.data = { items: [staleRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("LIVE", "opportunities", false);
    const queue = screen.getByTestId("imp-radar-queue");
    expect(queue).toHaveTextContent(/Expired/i);
    expect(queue).toHaveTextContent(/STALE/i);
    expect(queue).toHaveTextContent(/never grants live execution/i);
    expect(queue).toHaveTextContent(/INELIGIBLE/i);
    expect(within(queue).queryByText("Open workspace")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch BIYA" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    const brief = within(await screen.findByTestId("imp-radar-detail-card")).getByTestId(
      "imp-radar-operator-brief",
    );
    expect(brief).toHaveTextContent(/never grants live execution/i);
    expect(brief).toHaveTextContent(/STALE/i);
    expect(brief).toHaveTextContent(/INELIGIBLE/i);
  });

  it("surfaces STALE on an eligible Paper row without upgrading to FRESH", async () => {
    const staleEligible: OpportunityReviewRow = {
      ...rankedRow,
      data_quality: {
        status: "DEGRADED",
        freshness: "STALE",
        source: "TEST_ONLY_FIXTURE",
        reason_codes: ["STALE_AFTER_THRESHOLD"],
      },
      // Drop ranking freshness PRESENT/FRESH so the queue cannot look upgraded.
      ranking_vector: {
        basis: "COMPARATOR_LEXICOGRAPHIC",
        dimensions: [{ name: "attention_score", status: "PRESENT", value: 74.5 }],
        rank_order: 1,
      },
    };
    summaryMock.data = {
      items: [staleEligible],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    const queue = screen.getByTestId("imp-radar-queue");
    expect(queue).toHaveTextContent(/STALE/i);
    const brief = within(await screen.findByTestId("imp-radar-detail-card")).getByTestId(
      "imp-radar-operator-brief",
    );
    const howFresh = within(brief)
      .getByText("How fresh?")
      .closest(".imp-radar-brief-row");
    expect(howFresh).toHaveTextContent(/STALE/i);
    expect(howFresh).not.toHaveTextContent(/\bFRESH\b/);
    // Freshness and eligibility stay orthogonal: eligible Paper still offers Watch.
    fireEvent.click(screen.getByRole("button", { name: "Watch BIYA" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
  });

  it("surfaces contradicted agent enrichment as inference, not observation", async () => {
    const contradictedRow: OpportunityReviewRow = {
      ...rankedRow,
      metadata: { agent_enrichment: { status: "CONTRADICTED" } },
    };
    summaryMock.data = {
      items: [contradictedRow],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    renderRadar("PAPER", "opportunities", true);
    const scan = within(screen.getByTestId("imp-radar-queue")).getByTestId("imp-radar-queue-scan");
    expect(scan).toHaveTextContent(/CONTRADICTED/);
    expect(scan).toHaveTextContent(/not a provider observation/i);
    expect(screen.getByTestId("imp-radar-queue")).toHaveTextContent(/Conflict:/i);
    expect(screen.getByTestId("imp-radar-queue")).toHaveTextContent(/CONTRADICTED/);
    const brief = within(await screen.findByTestId("imp-radar-detail-card")).getByTestId(
      "imp-radar-operator-brief",
    );
    expect(brief).toHaveTextContent(/Inference vs observation/i);
    expect(brief).toHaveTextContent(/CONTRADICTED/);
    expect(brief).toHaveTextContent(/not a provider observation/i);
    expect(brief).toHaveTextContent(/Which facts conflict/i);
  });

  it("keeps detail inline on wide layouts without a sheet", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    expect(await screen.findByTestId("imp-radar-detail-card")).toBeInTheDocument();
    const queue = screen.getByTestId("imp-radar-queue");
    fireEvent.click(queue.querySelector('[data-stable-key="opp-1"]') as HTMLElement);
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
    ackMutateAsync.mockClear();
    mediaState.narrow = true;
  });

  it("opens the detail as a dismissable sheet and keeps the queue scannable", async () => {
    renderRadar("PAPER", "opportunities", true);
    // Narrow layout: no inline detail column, queue stays visible.
    expect(screen.queryByTestId("imp-radar-detail-card")).not.toBeInTheDocument();
    expect(screen.getByTestId("imp-radar-queue")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("imp-radar-queue").querySelector('[data-stable-key="opp-1"]') as HTMLElement);
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
    fireEvent.click(screen.getByTestId("imp-radar-queue").querySelector('[data-stable-key="opp-1"]') as HTMLElement);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("imp-radar-queue").querySelector('[data-stable-key="opp-1"]') as HTMLElement);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("keeps paper ack gating identical inside the sheet", async () => {
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(screen.getByTestId("imp-radar-queue").querySelector('[data-stable-key="opp-1"]') as HTMLElement);
    const sheet = await screen.findByRole("dialog");
    fireEvent.click(within(sheet).getByRole("button", { name: "Watch" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
    await waitFor(() => expect(within(sheet).getByRole("button", { name: "Watch" })).not.toBeDisabled());
    fireEvent.click(within(sheet).getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "dismiss" }),
    );
  });
});

describe("RadarPage durable decision closure", () => {
  beforeEach(() => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    summaryMock.isLoading = false;
    summaryMock.isError = false;
    ackMutateAsync.mockReset();
    ackMutateAsync.mockImplementation(async (vars: { rowId: string; action: string }) => ({
      summary_id: vars.rowId.startsWith("opp-") ? `sum-${vars.rowId.slice(4)}` : vars.rowId,
      opportunity_id: vars.rowId,
      action: vars.action === "watch" ? "WATCHED" : vars.action === "dismiss" ? "DISMISSED" : "REVIEWED",
      trade_review_id: `tr-${vars.rowId}`,
      decision_trace_mode: "CONTROLLED_REPLAY",
      created_at_ns: 1,
    }));
    tradeReviewsFetch.mockReset();
    // Default: no durable review yet — Watch/Dismiss materialization is tested explicitly.
    tradeReviewsFetch.mockImplementation(async (opportunityId: string) => ({
      opportunity_id: opportunityId,
      items: [],
    }));
    tradeReviewStore.items = [];
    tradeReviewStore.listeners.clear();
    mediaState.narrow = false;
    contextMock.data.as_of_context.controlled_replay = false;
    contextMock.data.as_of_context.evidence_class = undefined;
  });

  it("after Watch success, reconciles authoritative trade review without manual refresh", async () => {
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    tradeReviewsFetch.mockImplementation(async (opportunityId: string) => {
      if (ackMutateAsync.mock.calls.length === 0) {
        return { opportunity_id: opportunityId, items: [] };
      }
      return {
        opportunity_id: opportunityId,
        items: [
          {
            review_id: "tr-opp-1",
            review_mode: "WATCHED_OPPORTUNITY",
            decision: "WATCH",
            notes: "durable",
          },
        ],
      };
    });
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(screen.getByText("Historical & research context"));
    await waitFor(() => expect(screen.getByText(/No durable trade review yet/i)).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("imp-radar-detail-card")).getByRole("button", { name: "Watch" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "watch" }),
    );
    await waitFor(() => expect(tradeReviewsFetch).toHaveBeenCalled());
    await waitFor(() => {
      expect(screen.getByTestId("trade-review-learning-panel")).toHaveTextContent("WATCHED_OPPORTUNITY");
      expect(screen.queryByText(/No durable trade review yet/i)).not.toBeInTheDocument();
    });
  });

  it("after Dismiss success, shows decision closure when opportunity leaves the active queue", async () => {
    const second: OpportunityReviewRow = {
      ...rankedRow,
      summary_id: "sum-2",
      opportunity_id: "opp-2",
      instrument_id: "GME",
      headline: "GME squeeze continuation",
      rank_order: 2,
    };
    summaryMock.data = {
      items: [rankedRow, second],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
    };
    tradeReviewsFetch.mockResolvedValue({
      opportunity_id: "opp-1",
      items: [
        {
          review_id: "tr-opp-1",
          review_mode: "REJECTED_OPPORTUNITY",
          decision: "DISMISS",
        },
      ],
    });
    // When the ack mutation succeeds, drop the dismissed row from the ranked summary
    // so selection fallthrough + no-ghost behavior is exercised.
    ackMutateAsync.mockImplementation(async (vars: { rowId: string; action: string }) => {
      const result = {
        summary_id: vars.rowId.startsWith("opp-") ? `sum-${vars.rowId.slice(4)}` : vars.rowId,
        opportunity_id: vars.rowId,
        action: vars.action === "watch" ? "WATCHED" : vars.action === "dismiss" ? "DISMISSED" : "REVIEWED",
        trade_review_id: `tr-${vars.rowId}`,
        decision_trace_mode: "CONTROLLED_REPLAY",
        created_at_ns: 1,
      };
      if (vars.action === "dismiss") {
        summaryMock.data = {
          items: [second],
          feed_status: "READY",
          unready_reason: undefined,
          next_action: undefined,
        };
      }
      return result;
    });
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(within(screen.getByTestId("imp-radar-detail-card")).getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(ackMutateAsync).toHaveBeenCalledWith({ rowId: "opp-1", action: "dismiss" }),
    );
    await waitFor(() => {
      const banner = screen.getByTestId("decision-closure-banner");
      expect(banner).toHaveTextContent(/Dismiss accepted/i);
      expect(banner).toHaveTextContent(/left active queue/i);
      expect(banner).toHaveTextContent("opp-1");
    });
    await waitFor(() => {
      expect(screen.getByTestId("imp-radar-detail-card")).toHaveTextContent("GME squeeze continuation");
      expect(screen.getByTestId("imp-radar-detail-card")).not.toHaveTextContent(
        "BIYA momentum ignition watch",
      );
    });
  });

  it("on mutation failure, does not show durable review success", async () => {
    ackMutateAsync.mockRejectedValueOnce(new Error("ACK_FAILED"));
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    const callsBefore = tradeReviewsFetch.mock.calls.length;
    fireEvent.click(within(screen.getByTestId("imp-radar-detail-card")).getByRole("button", { name: "Watch" }));
    await waitFor(() => {
      expect(screen.getAllByText(/Operator action failed/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryByTestId("decision-closure-banner")).not.toBeInTheDocument();
    // Failed mutation must not trigger post-ack reconciliation fetches.
    expect(tradeReviewsFetch.mock.calls.length).toBe(callsBefore);
  });

  it("when action accepted but review fetch misses expected id, reports reconciliation failure", async () => {
    tradeReviewsFetch.mockResolvedValue({
      opportunity_id: "opp-1",
      items: [],
    });
    summaryMock.data = { items: [rankedRow], feed_status: "READY", unready_reason: undefined, next_action: undefined };
    renderRadar("PAPER", "opportunities", true);
    fireEvent.click(within(screen.getByTestId("imp-radar-detail-card")).getByRole("button", { name: "Watch" }));
    await waitFor(() => {
      expect(screen.getAllByText(/durable review retrieval failed/i).length).toBeGreaterThan(0);
      expect(screen.getAllByRole("button", { name: /Retry review retrieval/i }).length).toBeGreaterThan(0);
    });
  });
});

describe("RadarPage feed truth strip", () => {
  beforeEach(() => {
    summaryMock.isLoading = false;
    summaryMock.isError = false;
    ackMutateAsync.mockClear();
    mediaState.narrow = false;
  });

  it("labels replay context as non-current", () => {
    summaryMock.data = {
      items: [rankedRow],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
      as_of_context: {
        mode: "REPLAY",
        data_mode: "FIXTURE_REPLAY",
        as_of_time: "2026-08-24T15:00:00Z",
        timezone: "America/New_York",
        data_provider: "unit-fixture",
        as_of_provenance: "fixture",
      },
    };
    renderRadar("DEMO", "opportunities", false);
    const strip = screen.getByTestId("imp-radar-feed-truth");
    expect(strip).toHaveAttribute("data-non-current", "true");
    expect(strip).toHaveTextContent(/Replay — not live market time/i);
    expect(strip).toHaveTextContent(/must not be read as current/i);
    expect(strip).not.toHaveTextContent(/Current observational feed/i);
    // READY must not use the live tone under FIXTURE_REPLAY / non-current class.
    const readyPill = within(strip)
      .getAllByTestId("imp-ui-state-pill")
      .find((pill) => /Ready/i.test(pill.textContent ?? ""));
    expect(readyPill).toBeDefined();
    expect(readyPill).not.toHaveAttribute("data-tone", "live");
    expect(readyPill).toHaveAttribute("data-tone", "replay");
  });

  it("keeps READY as live tone only for current observational feeds", () => {
    summaryMock.data = {
      items: [rankedRow],
      feed_status: "READY",
      unready_reason: undefined,
      next_action: undefined,
      as_of_context: {
        mode: "LIVE",
        data_mode: "LIVE_OBSERVATIONAL",
        as_of_time: "2026-08-24T15:00:00Z",
        timezone: "America/New_York",
        data_provider: "live-unit",
        as_of_provenance: "live_receive",
      },
    };
    renderRadar("PAPER", "opportunities", true);
    const strip = screen.getByTestId("imp-radar-feed-truth");
    expect(strip).toHaveAttribute("data-non-current", "false");
    const readyPill = within(strip)
      .getAllByTestId("imp-ui-state-pill")
      .find((pill) => /Ready/i.test(pill.textContent ?? ""));
    expect(readyPill).toHaveAttribute("data-tone", "live");
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

  it("hosts the investigation-only screener with explicit market-data status", async () => {
    renderRadar("PAPER", "screeners", true);
    expect(await screen.findByRole("heading", { name: "Investigation screener" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigation" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: "Investigation-only screener" })).toBeInTheDocument();
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
    expect(screen.getByRole("heading", { name: "Investigation screener" })).toBeInTheDocument();

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

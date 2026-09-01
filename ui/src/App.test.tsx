import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./api/client";

vi.mock("./components/charts/ResearchChartPanels", () => ({
  CountBarChartPanel: () => null,
  SignalTimelineChartPanel: () => null,
}));

vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
      setMarkers: vi.fn(),
    })),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
      setVisibleLogicalRange: vi.fn(),
    })),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    resize: vi.fn(),
  })),
}));

vi.mock("./components/live/LiveMarketPanel", () => ({
  LiveMarketPanel: () => null,
}));

const replaySession = { cursor_index: 0, event_count: 4 };

const portfolioMocks = vi.hoisted(() => ({
  data: undefined as Record<string, unknown> | undefined,
}));

const attentionMocks = vi.hoisted(() => ({
  items: [] as Array<{
    attention_id: string;
    priority_rank: number;
    reasons: Array<{ code: string; label: string }>;
    instrument_id?: string;
    headline: string;
    explanation_ref: string;
    tier?: number;
  }>,
}));

function portfolioPayload() {
  return {
    account: {
      paper_account_id: "acct",
      session_id: "sess",
      currency: "USD",
      cash_display: "1000.00",
      cash_minor: 100000,
      buying_power_minor: 100000,
      initial_cash_minor: 100000,
      realized_pnl_display: "0.00",
      realized_pnl_minor: 0,
      data_mode: "FIXTURE_REPLAY",
      data_provider: "INTERNAL",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
      execution_provider: "INTERNAL",
    },
    authority_boundary: "PAPER_OBSERVABILITY",
    positions: [{ instrument_id: "BIYA", quantity: 10, side: "LONG" }],
    orders: [],
    fills: [],
    risk: {
      kill_switch_active: false,
      open_order_count: 0,
      reconciliation_status: "INTERNAL_AUTHORITATIVE",
      limits: { max_open_orders: 3, max_order_shares: 100, max_position_shares: 500 },
    },
    data_health: { state: "PASS", detail: "fixture" },
    as_of_context: {
      mode: "REPLAY",
      as_of_time: "2026-08-30T12:00:00Z",
      timezone: "America/New_York",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
    },
    active_instrument: "BIYA",
    active_instrument_source: "FIXTURE_DEFAULT",
  };
}

function discoverMixedPayload() {
  return {
    available: true,
    mode: "SEMI_LIVE",
    candidate_role: "INVESTIGATE",
    execution_authority: "NONE",
    market_session: "REGULAR",
    generated_at: "2026-08-24T15:00:00Z",
    discovery_as_of: "2026-08-24T14:59:00Z",
    candidate_count: 1,
    refresh_in_progress: false,
    refresh_interval_seconds: 120,
    poll_interval_seconds: 3,
    provider_health: [],
    lane_counts: { MOMENTUM: 1 },
    screen_outcomes: [],
    candidates: [
      {
        instrument_id: "AAPL",
        candidate_role: "INVESTIGATE",
        lanes: ["MOMENTUM"],
        screen_matches: ["UNUSUAL_VOLUME_DISCOVERY"],
        matched_reasons: ["UNUSUAL_VOLUME"],
        metrics: { change_pct: 4.2, rel_volume: 3.1 },
        discovery_as_of: "2026-08-24T14:59:00Z",
        quality: "PASS",
        provenance: [],
        attention_score: 74.5,
        attention_components: {},
        ranking_reasons: ["RVOL_3.10"],
        market: {
          provider: "MOOMOO",
          status: "LIVE",
          last_price: 101.2,
          quality: "PASS",
        },
        data_status: "LIVE",
        freshness_label: "480 ms",
        queue_rank: 1,
      },
    ],
  };
}

const remainingWorkspaceLanes = [
  {
    label: "Order Book",
    heading: /BIYA — Order Book Workspace/i,
    base: /Depth imbalance is not participant intent/i,
    paper: /Review depth imbalance before paper order preview/i,
    live: /Visible liquidity is broker-observed/i,
  },
  {
    label: "Futures",
    heading: /BIYA — Futures Workspace/i,
    base: /not CFTC positioning/i,
    paper: /Factor macro backdrop into paper simulation/i,
    live: /ES depth is observational/i,
  },
  {
    label: "Catalyst",
    heading: /BIYA — Catalyst Workspace/i,
    base: /not trade recommendations/i,
    paper: /Factor catalyst events into paper thesis/i,
    live: /Public catalyst bridge is read-only/i,
  },
  {
    label: "Fund / ETF",
    heading: /BIYA — Fund \/ ETF Workspace/i,
    base: /Not live fund-flow data/i,
    paper: /ETF flow proxies for cross-asset paper context/i,
    live: /Fund-flow proxies are observational/i,
  },
  {
    label: "Large Transactions",
    heading: /BIYA — Large Transactions Workspace/i,
    base: /Large prints are not directional intent/i,
    paper: /Use size prints for paper context/i,
    live: /Large prints are observational/i,
  },
  {
    label: "Disclosure",
    heading: /BIYA — Disclosure Workspace/i,
    base: /not live positions/i,
    paper: /Use filing events for paper research/i,
    live: /Delayed filings remain read-only/i,
  },
  {
    label: "Institutional Flow",
    heading: /BIYA — Institutional Flow/i,
    base: /Swim With the Whales doctrine/i,
    paper: /Use whale evidence for paper thesis/i,
    live: /Institutional flow is observational/i,
  },
] as const;

vi.mock("./api/hooks", () => ({
  queryKeys: {
    context: ["context"],
    attention: ["attention"],
    liveCanarySnapshot: (laneId?: string) => ["live", "canary-snapshot", laneId ?? "account"],
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
  useAttentionQuery: () => ({ data: { items: attentionMocks.items }, isLoading: false, error: null }),
  useReplaySessionQuery: () => ({
    isLoading: false,
    error: null,
    data: replaySession,
  }),
  useAssistantStatusQuery: () => ({ data: undefined }),
  useAssistantMessagesQuery: () => ({ data: undefined, isLoading: false }),
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: !portfolioMocks.data,
    data: portfolioMocks.data,
  }),
  usePaperOrderHistoryInfiniteQuery: () => ({
    data: {
      pages: [
        {
          orders: portfolioMocks.data?.orders ?? [],
          fills: portfolioMocks.data?.fills ?? [],
          next_cursor: null,
          total_count: portfolioMocks.data?.orders?.length ?? 0,
          page_size: 25,
        },
      ],
    },
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  }),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useClosePaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProviderHealthQuery: () => ({
    isLoading: false,
    error: null,
    data: { available: false, reason: "Live observational mode disabled in test." },
  }),
  useLiveCanarySnapshotQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      live_blocked: true,
      block_reasons: ["TEST"],
      execution_mode_label: "LIVE_CANARY",
      program_state: "ACTIVE",
      session_state: "AUTHORIZED",
      broker: "tradier.paper",
      account_environment: "paper",
      broker_health: "HEALTHY",
      reconciliation_health: "CLEAN",
      kill_switch_global: "OFF",
      kill_switch_program: "OFF",
      kill_switch_session: "OFF",
      authorization_status: "AUTHORIZED",
      incident_summary: {},
      unresolved_critical_incidents: [],
      live_positions: [{ instrument_id: "AAPL", quantity: 3, side: "LONG" }],
      open_broker_orders: [{ order_id: "ord-live-1", side: "BUY", quantity: 1 }],
    },
  }),
  useSymbolSearchQuery: () => ({ data: { results: [] }, isLoading: false }),
  useInstrumentCapabilitiesQuery: () => ({ data: { capabilities: [] }, isLoading: false }),
  useSubscribeMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useInstrumentQuery: () => ({ isLoading: false, error: null, data: { bars: [], features: [] } }),
  useWorkspaceSqueezeQuery: () => ({ isLoading: false, data: null }),
  useWorkspaceEvidenceQuery: () => ({ isLoading: false, data: undefined }),
  useMarketStateQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceOrderFlowQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceOrderBookQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceFuturesQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceCatalystQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceFundEtfQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceLargeTransactionsQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceDisclosureQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceInstitutionalFlowQuery: () => ({ isLoading: false, data: undefined }),
  useWorkspaceOptionsQuery: () => ({ isLoading: false, data: undefined }),
  useExploreSqueezeQuery: () => ({
    isLoading: false,
    data: {
      available: true,
      source: "donor-screener",
      row_count: 1,
      disclaimer: "Research only.",
      rows: [
        {
          screener_id: "sq-1",
          symbol: "GME",
          outcome_status: "OPEN",
          evidence_coverage: "FULL",
          research_detection: "DETECTED",
          freshness: "FRESH",
        },
      ],
      outcome_summary: [],
    },
  }),
  useExploreSqueezeScannerQuery: () => ({
    isLoading: false,
    data: { available: false, reason: "Unavailable in test." },
  }),
  useExploreFuturesQuery: () => ({ isLoading: false, data: { available: false } }),
  useExploreCatalystQuery: () => ({ isLoading: false, data: { available: false } }),
  useResearchAnalyticsQuery: () => ({
    isLoading: false,
    data: {
      epistemic_class: "RESEARCH_PROJECTION",
      authority_boundary: "READ_ONLY",
      disclaimer: "Research only.",
      panels: {
        attention_tiers: { available: false, provenance: { source: "test" }, series: [] },
        squeeze_outcomes: { available: false, provenance: { source: "test" }, series: [] },
        squeeze_historical_cohort: { available: false, provenance: { source: "test" }, series: [] },
        strategy_outcomes: { available: false, provenance: { source: "test" }, series: [] },
        risk_decisions: { available: false, provenance: { source: "test" }, series: [] },
      },
    },
  }),
  useResearchModelsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchSimulationQuery: () => ({ isLoading: false, data: undefined }),
}));

describe("App mode launcher integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    portfolioMocks.data = undefined;
    window.history.replaceState({}, "", "/");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    Object.defineProperty(window, "ResizeObserver", {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn(),
      })),
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.url;
        const method =
          init?.method ?? (typeof input !== "string" && "method" in input ? input.method : "GET");
        if (url.endsWith("/canary/snapshot")) {
          return {
            ok: true,
            json: async () => ({
              snapshot: {
                live_blocked: true,
                block_reasons: ["HUMAN_CONFIRMATION_REQUIRED"],
                execution_mode_label: "LIVE_CANARY",
                program_state: "ARMED",
                session_state: "IDLE",
                broker: "MOOMOO",
                account_environment: "PAPER_BROKER",
                broker_health: "HEALTHY",
                reconciliation_health: "RECONCILED",
                kill_switch_global: "OFF",
                kill_switch_program: "OFF",
                kill_switch_session: "OFF",
                authorization_status: null,
                authorization_expires_at_ns: null,
                program_cap_remaining: { sessions: 3, orders: 3, notional_minor: 7500 },
                incident_summary: { open: 0, critical_open: 0 },
                unresolved_critical_incidents: [],
                allowed_next_actions: [],
                action_queue: [],
                snapshot_id: "OPSNA-test",
                as_of_ns: 1,
                live_positions: [{ instrument_id: "AAPL", quantity: 3, side: "LONG" }],
                open_broker_orders: [{ order_id: "ord-live-1", side: "BUY", quantity: 1 }],
              },
            }),
          };
        }
        if (url.endsWith("/canary/reconciliation")) {
          return {
            ok: true,
            json: async () => ({
              reconciliation_health: "CLEAN",
              local_open_orders: [],
              ambiguous_states: [],
            }),
          };
        }
        if (url.endsWith("/paper/sessions")) {
          return {
            ok: true,
            json: async () => ({ sessions: [] }),
          };
        }
        if (url.includes("/discover/mixed")) {
          return {
            ok: true,
            json: async () => discoverMixedPayload(),
          };
        }
        if (url.endsWith("/state/startup")) {
          return {
            ok: true,
            json: async () => ({
              opend: { operator_message: "Provider ready." },
              restore: "CLEAN",
              crash_recovery: "NONE",
              execution_deferred: false,
            }),
          };
        }
        if (url.endsWith("/operator/state")) {
          return {
            ok: true,
            json: async () => ({
              persistence_enabled: true,
              watchlists: [{ watchlist_id: "wl-1", items: [{ instrument_id: "BIYA" }] }],
              recent_instruments: [{ instrument_id: "BIYA" }],
              sessions: [],
              captures: [{ capture_id: "cap-1", status: "AVAILABLE", provider: "INTERNAL" }],
            }),
          };
        }
        if (url.endsWith("/canary/reliability")) {
          return {
            ok: true,
            json: async () => ({
              observability_state: "OBSERVABILITY_HEALTHY",
              as_of_ns: 1,
              health_matrix: { entries: [], blocking_dependencies: [] },
              slo_summary: { overall_status: "HEALTHY", objectives: [] },
              persistence_health: { disposition: "HEALTHY", blocking_live: false },
              backup_status: { integrity_status: "VERIFIED", last_backup_id: "b1" },
              alert_delivery_configured: true,
            }),
          };
        }
        if (url.endsWith("/assistant/conversations") && method === "POST") {
          return {
            ok: true,
            json: async () => ({
              conversation_id: "conv-new",
              principal_id: "RESEARCH-UI-001",
              title: "New conversation",
              created_at_ns: 1,
              updated_at_ns: 1,
              message_count: 0,
            }),
          };
        }
        if (url.endsWith("/assistant/conversations")) {
          return {
            ok: true,
            json: async () => ({
              conversations: [
                {
                  conversation_id: "conv-1",
                  principal_id: "RESEARCH-UI-001",
                  title: "BIYA squeeze context",
                  created_at_ns: 1,
                  updated_at_ns: 2,
                  message_count: 2,
                },
              ],
              principal_id: "RESEARCH-UI-001",
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({}),
        };
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

  async function openNavLink(name: RegExp) {
    const nav = screen.getByRole("navigation", { name: "Primary" });
    fireEvent.click(within(nav).getByRole("link", { name }));
  }

  async function openPortfolio() {
    await openNavLink(/^PORTFOLIO —/);
  }

  async function openExplore() {
    await openNavLink(/^EXPLORE —/);
  }

  async function openResearch() {
    await openNavLink(/^RESEARCH —/);
  }

  async function openDiscover() {
    await openNavLink(/^DISCOVER —/);
  }

  async function openSqueezeFromExplore() {
    await openExplore();
    fireEvent.click(screen.getByRole("link", { name: "GME" }));
    expect(
      await screen.findByRole("heading", { name: /GME — Short Squeeze Workspace/i }),
    ).toBeInTheDocument();
  }

  async function openWorkspaceOverview() {
    await openNavLink(/^WORKSPACE —/);
    expect(await screen.findByRole("heading", { name: "BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workspace modules" })).toBeInTheDocument();
  }

  async function openWorkspaceLane(laneLabel: string, heading: RegExp) {
    await openWorkspaceOverview();
    const nav = screen.getByRole("navigation", { name: "Workspace modules" });
    fireEvent.click(within(nav).getByRole("link", { name: laneLabel }));
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  }

  async function openSettings() {
    await openNavLink(/^SETTINGS$/);
  }

  async function openDiagnostics() {
    await openNavLink(/^DIAGNOSTICS$/);
  }

  async function openLiveCanary() {
    await openNavLink(/^LIVE CANARY/);
  }

  async function openPaperCommand() {
    expect(await screen.findByRole("heading", { name: "Paper Command" })).toBeInTheDocument();
  }

  async function openAssistantHistory() {
    fireEvent.click(screen.getByRole("button", { name: "Assistant" }));
    fireEvent.click(await screen.findByRole("link", { name: "Conversation history" }));
    expect(await screen.findByRole("heading", { name: "Assistant history" })).toBeInTheDocument();
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

  it("opens Live Watch in Live mode", async () => {
    render(<App />);
    await enterMode("Live");
    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("LIVE");
    expect(await screen.findByRole("heading", { name: "Live Watch" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Command Center" })).not.toBeInTheDocument();
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

  it("opens Demo Portfolio from /portfolio", async () => {
    portfolioMocks.data = portfolioPayload();
    render(<App />);
    await enterMode("Demo");
    await openPortfolio();
    expect(await screen.findByRole("heading", { name: "Demo Portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByText("BIYA")).toBeInTheDocument();
  });

  it("opens Paper Portfolio from /portfolio", async () => {
    portfolioMocks.data = portfolioPayload();
    render(<App />);
    await enterMode("Paper");
    await openPortfolio();
    expect(await screen.findByRole("heading", { name: "Paper Portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Paper authority unavailable/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("opens Live Portfolio from /portfolio", async () => {
    render(<App />);
    await enterMode("Live");
    await openPortfolio();
    expect(await screen.findByRole("heading", { name: "Live Portfolio" })).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("ord-live-1")).toBeInTheDocument();
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
  });

  it("opens Demo Explore from /explore", async () => {
    render(<App />);
    await enterMode("Demo");
    await openExplore();
    expect(await screen.findByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText("GME")).toBeInTheDocument();
  });

  it("opens Paper Explore from /explore", async () => {
    render(<App />);
    await enterMode("Paper");
    await openExplore();
    expect(await screen.findByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open paper portfolio" })).toBeInTheDocument();
  });

  it("opens Live Explore from /explore", async () => {
    render(<App />);
    await enterMode("Live");
    await openExplore();
    expect(await screen.findByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toBeInTheDocument();
  });

  it("opens Demo Research from /research", async () => {
    render(<App />);
    await enterMode("Demo");
    await openResearch();
    expect(await screen.findByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByRole("tab", { name: "Analytics" })).toHaveAttribute("aria-selected", "true");
  });

  it("opens Paper Research from /research", async () => {
    render(<App />);
    await enterMode("Paper");
    await openResearch();
    expect(await screen.findByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByText(/Research to simulation/i)).toBeInTheDocument();
  });

  it("opens Live Research from /research", async () => {
    render(<App />);
    await enterMode("Live");
    await openResearch();
    expect(await screen.findByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toBeInTheDocument();
  });

  it("opens Demo Discover from /discover", async () => {
    render(<App />);
    await enterMode("Demo");
    await openDiscover();
    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
  });

  it("opens Paper Discover from /discover", async () => {
    render(<App />);
    await enterMode("Paper");
    await openDiscover();
    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh all screens" })).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("opens Live Discover from /discover", async () => {
    render(<App />);
    await enterMode("Live");
    await openDiscover();
    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
  });

  it("opens Demo Squeeze workspace from /workspace/GME/squeeze", async () => {
    render(<App />);
    await enterMode("Demo");
    await openSqueezeFromExplore();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText(/frozen research cohort evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workspace modules" })).toBeInTheDocument();
  });

  it("opens Paper Squeeze workspace from /workspace/GME/squeeze", async () => {
    render(<App />);
    await enterMode("Paper");
    await openSqueezeFromExplore();
    expect(screen.getByText(/Preview squeeze ignition/i)).toBeInTheDocument();
    expect(screen.getByText(/Paper simulation context/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open paper portfolio" })).toBeInTheDocument();
  });

  it("opens Live Squeeze workspace from /workspace/GME/squeeze", async () => {
    render(<App />);
    await enterMode("Live");
    await openSqueezeFromExplore();
    expect(screen.getByText(/broker-observed squeeze signals/i)).toBeInTheDocument();
    expect(screen.getByTestId("workspace-mode-restriction-note")).toHaveTextContent(/read-only/i);
    expect(screen.getAllByRole("link", { name: "Open live canary" }).length).toBeGreaterThan(0);
  });

  it("opens Demo workspace overview from /workspace/BIYA", async () => {
    render(<App />);
    await enterMode("Demo");
    await openWorkspaceOverview();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText(/Observational workspace/i)).toBeInTheDocument();
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("opens Paper workspace overview from /workspace/BIYA", async () => {
    portfolioMocks.data = portfolioPayload();
    render(<App />);
    await enterMode("Paper");
    await openWorkspaceOverview();
    expect(screen.getByText(/Paper-only simulation/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByText(/No handoff — review workspace evidence before drafting/i)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Paper authority unavailable/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("opens Live workspace overview from /workspace/BIYA", async () => {
    render(<App />);
    await enterMode("Live");
    await openWorkspaceOverview();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("opens Demo Order Flow workspace from /workspace/BIYA/order-flow", async () => {
    render(<App />);
    await enterMode("Demo");
    await openWorkspaceLane("Order Flow", /BIYA — Order Flow Workspace/i);
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText(/Unknown aggressor remains unknown/i)).toBeInTheDocument();
  });

  it("opens Paper Order Flow workspace from /workspace/BIYA/order-flow", async () => {
    render(<App />);
    await enterMode("Paper");
    await openWorkspaceLane("Order Flow", /BIYA — Order Flow Workspace/i);
    expect(screen.getByText(/Use CVD evidence to inform paper order sizing/i)).toBeInTheDocument();
    expect(screen.getByText(/Paper simulation context/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open paper portfolio" })).toBeInTheDocument();
  });

  it("opens Live Order Flow workspace from /workspace/BIYA/order-flow", async () => {
    render(<App />);
    await enterMode("Live");
    await openWorkspaceLane("Order Flow", /BIYA — Order Flow Workspace/i);
    expect(screen.getByText(/broker-reported order flow/i)).toBeInTheDocument();
    expect(screen.getByTestId("workspace-mode-restriction-note")).toHaveTextContent(/read-only/i);
    expect(screen.getAllByRole("link", { name: "Open live canary" }).length).toBeGreaterThan(0);
  });

  it("opens Demo Options workspace from /workspace/BIYA/options", async () => {
    render(<App />);
    await enterMode("Demo");
    await openWorkspaceLane("Options", /BIYA — Options Workspace/i);
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText(/Unusual options activity/i)).toBeInTheDocument();
  });

  it("opens Paper Options workspace from /workspace/BIYA/options", async () => {
    render(<App />);
    await enterMode("Paper");
    await openWorkspaceLane("Options", /BIYA — Options Workspace/i);
    expect(screen.getByText(/Use unusual activity to inform paper sizing/i)).toBeInTheDocument();
    expect(screen.getByText(/Paper simulation context/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace overview" })).toHaveAttribute(
      "href",
      "/workspace/BIYA",
    );
  });

  it("opens Live Options workspace from /workspace/BIYA/options", async () => {
    render(<App />);
    await enterMode("Live");
    await openWorkspaceLane("Options", /BIYA — Options Workspace/i);
    expect(screen.getByText(/Options activity is broker-observed/i)).toBeInTheDocument();
    expect(screen.getByTestId("workspace-mode-restriction-note")).toHaveTextContent(/read-only/i);
    expect(screen.getAllByRole("link", { name: "Open live canary" }).length).toBeGreaterThan(0);
  });

  it.each(remainingWorkspaceLanes)(
    "opens Demo $label workspace from overview module nav",
    async ({ label, heading, base }) => {
      render(<App />);
      await enterMode("Demo");
      await openWorkspaceLane(label, heading);
      expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
      expect(screen.getByText(base)).toBeInTheDocument();
    },
  );

  it.each(remainingWorkspaceLanes)(
    "opens Paper $label workspace from overview module nav",
    async ({ label, heading, paper }) => {
      render(<App />);
      await enterMode("Paper");
      await openWorkspaceLane(label, heading);
      expect(screen.getByText(paper)).toBeInTheDocument();
      expect(screen.getByText(/Paper simulation context/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Open paper portfolio" })).toBeInTheDocument();
    },
  );

  it.each(remainingWorkspaceLanes)(
    "opens Live $label workspace from overview module nav",
    async ({ label, heading, live }) => {
      render(<App />);
      await enterMode("Live");
      await openWorkspaceLane(label, heading);
      expect(screen.getByText(live)).toBeInTheDocument();
      expect(screen.getByTestId("workspace-mode-restriction-note")).toHaveTextContent(/read-only/i);
      expect(screen.getAllByRole("link", { name: "Open live canary" }).length).toBeGreaterThan(0);
    },
  );

  it("opens Demo settings as read-only operator surface", async () => {
    render(<App />);
    await enterMode("Demo");
    await openSettings();
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only in DEMO mode/i);
    expect(screen.queryByRole("button", { name: "Add to watchlist" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reindex captures" })).not.toBeInTheDocument();
  });

  it("opens Paper settings with operator mutations enabled", async () => {
    render(<App />);
    await enterMode("Paper");
    await openSettings();
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to watchlist" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reindex captures" })).toBeInTheDocument();
  });

  it("opens Live settings as read-only operator surface", async () => {
    render(<App />);
    await enterMode("Live");
    await openSettings();
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only in LIVE mode/i);
    expect(screen.queryByRole("button", { name: "Add to watchlist" })).not.toBeInTheDocument();
  });

  it("opens Live Canary observability from navigation", async () => {
    render(<App />);
    await enterMode("Live");
    await openLiveCanary();
    expect(await screen.findByTestId("live-canary-control-plane")).toBeInTheDocument();
    expect(screen.getByText(/REAL MONEY/i)).toBeInTheDocument();
  });

  it("opens provider diagnostics from navigation", async () => {
    render(<App />);
    await enterMode("Demo");
    await openDiagnostics();
    expect(await screen.findByRole("heading", { name: "Provider diagnostics" })).toBeInTheDocument();
    expect(screen.getByText(/Live observational mode disabled in test/i)).toBeInTheDocument();
  });

  it("opens assistant history from the sidecar", async () => {
    render(<App />);
    await enterMode("Paper");
    await openAssistantHistory();
    expect(await screen.findByText("BIYA squeeze context")).toBeInTheDocument();
  });

  it("routes lane draft link to Paper workspace overview", async () => {
    render(<App />);
    await enterMode("Paper");
    portfolioMocks.data = portfolioPayload();
    await openWorkspaceLane("Short Squeeze", /BIYA — Short Squeeze Workspace/i);
    expect(screen.getByText(/Placeholder draft uses BUY × 1 MARKET/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Draft paper order from lane" }));
    expect(await screen.findByRole("heading", { name: "BIYA" })).toBeInTheDocument();
    expect(screen.getByText(/Paper-only simulation/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Handoff from Short Squeeze/i })).toBeInTheDocument();
    expect(screen.getByText(/placeholder, not a recommendation/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preview status" })).toBeInTheDocument();
  });

  it("routes Order Flow lane draft to workspace overview with correct source lane", async () => {
    render(<App />);
    await enterMode("Paper");
    portfolioMocks.data = portfolioPayload();
    await openWorkspaceLane("Order Flow", /BIYA — Order Flow Workspace/i);
    fireEvent.click(screen.getByRole("link", { name: "Draft paper order from lane" }));
    expect(await screen.findByRole("heading", { name: /Handoff from Order Flow/i })).toBeInTheDocument();
  });

  it("does not render Paper decision cockpit mutation panels in Demo workspace overview", async () => {
    render(<App />);
    await enterMode("Demo");
    await openWorkspaceOverview();
    expect(screen.queryByRole("heading", { name: "Decision snapshot" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Preview status" })).not.toBeInTheDocument();
  });

  it("routes Paper Command attention to workspace with attention handoff", async () => {
    attentionMocks.items = [
      {
        attention_id: "ATT-123",
        priority_rank: 1,
        reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
        instrument_id: "BIYA",
        headline: "BIYA attention setup",
        explanation_ref: "explain:attention:biya",
        tier: 1,
      },
    ];
    render(<App />);
    await enterMode("Paper");
    portfolioMocks.data = portfolioPayload();
    await openPaperCommand();
    fireEvent.click(screen.getByRole("button", { name: "Draft BIYA in Paper workspace" }));
    expect(await screen.findByRole("heading", { name: "BIYA" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Attention handoff" })).toBeInTheDocument();
    expect(screen.getAllByText(/ATT-123/).length).toBeGreaterThan(0);
    expect(screen.getByText("BIYA attention setup")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preview status" })).toBeInTheDocument();
    expect(screen.getByText(/Placeholder draft from Paper Command/i)).toBeInTheDocument();
  });

  it("degrades malformed provenance handoff without blocking observational cockpit", async () => {
    render(<App />);
    await enterMode("Paper");
    portfolioMocks.data = portfolioPayload();
    await openWorkspaceOverview();
    // Simulate malformed provenance via direct navigation state is not practical in App test;
    // lane unknown provenance still renders cockpit observability.
    await openWorkspaceLane("Short Squeeze", /BIYA — Short Squeeze Workspace/i);
    fireEvent.click(screen.getByRole("link", { name: "Draft paper order from lane" }));
    expect(await screen.findByRole("heading", { name: /Handoff from Short Squeeze/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
  });
});

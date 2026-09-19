import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mode } from "../mode-session/types";
import { OperatorControlCenterPage } from "./OperatorControlCenterPage";
import { CONTROL_SECTIONS } from "./controlPresentation";

function response(payload: unknown, ok = true) {
  return Promise.resolve({ ok, json: async () => payload });
}

const DEMO_CONTEXT = {
  as_of_context: {
    mode: "REPLAY",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "NONE",
    execution_authority: "BLOCKED",
    as_of_time: "2026-09-16T12:00:00Z",
    timezone: "America/New_York",
  },
  capability_states: [],
  quality_summary: { state: "GOOD" },
};

const PAPER_CONTEXT = {
  as_of_context: {
    mode: "SIMULATION",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    as_of_time: "2026-09-16T12:00:00Z",
    timezone: "America/New_York",
  },
  capability_states: [],
  quality_summary: { state: "GOOD" },
};

const LIVE_CONTEXT = {
  as_of_context: {
    mode: "LIVE",
    data_mode: "LIVE_OBSERVATIONAL",
    execution_mode: "NONE",
    execution_authority: "BLOCKED",
    data_provider: "MOOMOO",
    as_of_time: "2026-09-16T12:00:00Z",
    timezone: "America/New_York",
  },
  capability_states: [],
  quality_summary: { state: "PASS" },
};

const READY_READINESS = {
  status: "READY",
  checks: [
    { id: "python", label: "Python 3.11", status: "PASS", detail: "Detected Python 3.11.", required: true },
  ],
  providers: [
    {
      provider: "moomoo_observational",
      label: "Moomoo observational",
      role: "primary_observational_market_data",
      credential_state: "NOT_REQUIRED",
      gate_state: "ENABLED",
      transport_state: "REACHABLE",
      next_action: "Confirm OpenD session and entitlements with tools/moomoo/probe.py.",
    },
  ],
};

const DEGRADED_READINESS = {
  status: "ACTION_REQUIRED",
  checks: READY_READINESS.checks,
  providers: [
    {
      provider: "moomoo_observational",
      label: "Moomoo observational",
      role: "primary_observational_market_data",
      credential_state: "NOT_REQUIRED",
      gate_state: "ENABLED",
      transport_state: "UNAVAILABLE",
      next_action: "Start OpenD",
    },
    {
      provider: "finviz",
      label: "Finviz discovery",
      role: "discovery",
      credential_state: "CONFIGURED",
      gate_state: "DISABLED",
      transport_state: "IMPLEMENTED_READ_ONLY",
      next_action: "Ready",
    },
  ],
};

const LIFECYCLE_READY = { status: "READY", services: [], logs: [], update: { status: "CURRENT" } };

function buildDiagnostics(overrides: {
  readiness?: unknown;
  lifecycle?: unknown;
  feed?: unknown;
  diagnosticsOk?: boolean;
  operatorTruth?: unknown;
}) {
  const readiness = overrides.readiness ?? READY_READINESS;
  const lifecycle = overrides.lifecycle ?? LIFECYCLE_READY;
  const feed = overrides.feed ?? FEED_READY;
  return {
    schema_version: "operator-diagnostics/1.0.0",
    severity: "OK",
    ...(overrides.operatorTruth ? { operator_truth: overrides.operatorTruth } : {}),
    sections: {
      lifecycle,
      readiness,
      opportunity_surface: {
        feed_status: (feed as { feed_status?: string }).feed_status,
        unready_reason: (feed as { unready_reason?: string }).unready_reason,
        quality_summary: (feed as { quality_summary?: { state?: string } }).quality_summary,
      },
      runtime: {
        git_sha: "deadbeef00000000000000000000000000000000",
        item9_preflight: { disposition: "NOT_RTH" },
        item9_corpus_status: {
          availability: "AVAILABLE",
          report: {
            calibration_state: "NOT_CALIBRATED",
            fitting_allowed: false,
            sample_gate_progress: { distinct_rth_dates: "2/3" },
          },
        },
        runtime_resilience: {
          collector_process: { active_collector_detected: false, probe_status: "COMPLETED" },
          expected_cycle: { receipt_inventory: { availability: "AVAILABLE" } },
          readiness_vs_liveness: { readiness: { item9_status: "PARTIAL_NOT_CALIBRATED" } },
        },
      },
      governance: {
        headline: "No blocking operator headline.",
        live_execution_env: false,
        interventions: [],
        forbidden: ["enable_live_execution"],
      },
      cycle_recovery: { expected_cycle_failure: "NOT_OBSERVED" },
      evidence_gaps: [],
    },
    human_summary: [],
  };
}

const FEED_READY = {
  as_of_context: DEMO_CONTEXT.as_of_context,
  quality_summary: { state: "GOOD" },
  feed_status: "READY",
  items: [{ summary_id: "s1", headline: "Row" }],
};

const PAPER_PORTFOLIO = {
  as_of_context: PAPER_CONTEXT.as_of_context,
  authority_boundary: "PAPER_OBSERVABILITY",
  account: {
    paper_account_id: "acct-1234567890",
    session_id: "sess-1",
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
  positions: [],
  orders: [],
  fills: [],
  risk: {
    kill_switch_active: false,
    open_order_count: 0,
    reconciliation_status: "INTERNAL_AUTHORITATIVE",
    limits: { max_open_orders: 3, max_order_shares: 100, max_position_shares: 500 },
  },
  data_health: { state: "PASS" },
  session: {
    session_id: "sess-1",
    paper_account_id: "acct-1234567890",
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
  },
};

type StubOverrides = {
  readiness?: unknown;
  diagnosticsOk?: boolean;
  lifecycle?: unknown;
  config?: unknown;
  context?: unknown;
  contextOk?: boolean;
  feed?: unknown;
  portfolio?: unknown;
  operatorTruth?: unknown;
};

function stubFetch(overrides: StubOverrides = {}) {
  const {
    readiness = READY_READINESS,
    diagnosticsOk = true,
    lifecycle = LIFECYCLE_READY,
    config = { providers: [] },
    context = DEMO_CONTEXT,
    contextOk = true,
    feed = FEED_READY,
    portfolio = PAPER_PORTFOLIO,
    operatorTruth,
  } = overrides;
  const diagnostics = buildDiagnostics({ readiness, lifecycle, feed, operatorTruth });
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("/operator/diagnostics")) return response(diagnostics, diagnosticsOk);
      if (path.includes("/operator/lifecycle/actions")) {
        return response({ operation_id: "op-1", status: "QUEUED" });
      }
      if (path.includes("/operator/config")) return response(config);
      if (path.includes("/paper/portfolio")) return response(portfolio);
      if (path.includes("/context")) return response(context, contextOk);
      return response({});
    }),
  );
}

function renderControl(mode: Mode = "DEMO", route = "/control") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[route]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <OperatorControlCenterPage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OperatorControlCenterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the healthy state: real facts, all-clear line, no attention section", async () => {
    stubFetch();
    renderControl("DEMO");

    expect(
      await screen.findByRole("heading", { name: "Platform control" }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/No blocking issues detected/)).toBeInTheDocument();
    expect(await screen.findByText(/calendar-incomplete \(2\/3\)/)).toBeInTheDocument();
    expect(screen.getAllByText(/IDLE, not DEGRADED/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Skip to system status" })).toHaveAttribute(
      "href",
      "#control-system-status",
    );
    expect(screen.getByRole("navigation", { name: "Control sections" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Needs your attention" })).not.toBeInTheDocument();
    // Distinct real states, not a composite score.
    expect(screen.getByText("Setup readiness")).toBeInTheDocument();
    expect(screen.getByText("Platform runtime")).toBeInTheDocument();
    expect(screen.getByText("Backend context")).toBeInTheDocument();
    expect(screen.getByText("Market data")).toBeInTheDocument();
  });

  it("shows execution authority distinctly from data availability", async () => {
    stubFetch({ context: PAPER_CONTEXT, portfolio: PAPER_PORTFOLIO });
    renderControl("PAPER");

    expect(await screen.findByText("Paper orders only")).toBeInTheDocument();
    expect(screen.getByText("Paper trading (simulated fills)")).toBeInTheDocument();
    expect(
      screen.getByText(/Paper orders can be submitted from the Workspace cockpit/),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Paper session open/)).toBeInTheDocument();
    // Data availability never implies execution authority.
    expect(
      screen.getByText(/live market data never implies live execution/i),
    ).toBeInTheDocument();
  });

  it("fails closed when the backend context is unavailable", async () => {
    stubFetch({ contextOk: false });
    renderControl("PAPER");

    const authority = await screen.findByRole("region", { name: "Execution & authority" });
    await waitFor(() => expect(authority).toHaveTextContent(/Backend context unavailable/));
    expect(authority).toHaveTextContent(
      /Execution controls remain locked until the backend context/,
    );
    // Unknown authority never renders as healthy.
    expect(screen.queryByText("Paper orders only")).not.toBeInTheDocument();
  });

  it("surfaces a degraded provider with impact language and a real action", async () => {
    stubFetch({ readiness: DEGRADED_READINESS });
    renderControl("DEMO");

    // Attention section lists the provider issue.
    expect(await screen.findByText("Moomoo observational needs attention")).toBeInTheDocument();
    // Provider row explains capability + impact + next step.
    expect(screen.getByText("Primary live market data (OpenD)")).toBeInTheDocument();
    expect(screen.getByText(/Live quotes stop updating/)).toBeInTheDocument();
    expect(screen.getByText(/Next: Start OpenD/)).toBeInTheDocument();
    // The disabled provider is not presented as urgent work.
    expect(screen.queryByText("Finviz discovery needs attention")).not.toBeInTheDocument();
  });

  it("queues a provider refresh through the real contract", async () => {
    stubFetch({ readiness: DEGRADED_READINESS });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.includes("/operator/providers/moomoo_observational/refresh")) {
        expect(init?.method).toBe("POST");
        return response({ operation_id: "op-1", status: "QUEUED" });
      }
      if (path.includes("/operator/diagnostics")) {
        return response(buildDiagnostics({ readiness: DEGRADED_READINESS }));
      }
      if (path.includes("/operator/config")) return response({ providers: [] });
      if (path.includes("/context")) return response(DEMO_CONTEXT);
      return response({});
    });
    renderControl("DEMO");

    fireEvent.click(
      await screen.findByRole("button", { name: "Refresh Moomoo observational" }),
    );
    await waitFor(() =>
      expect(screen.getByText(/Refresh queued for Moomoo observational/)).toBeInTheDocument(),
    );
  });

  it("explains an UNREADY feed with the humanized reason and impact", async () => {
    stubFetch({
      feed: { ...FEED_READY, feed_status: "UNREADY", unready_reason: "PROVIDER_WARMUP", items: [] },
    });
    renderControl("DEMO");

    const feedSection = await screen.findByRole("region", {
      name: "Opportunity feed readiness",
    });
    await waitFor(() =>
      expect(feedSection).toHaveTextContent(/Opportunity radar isn't ready/),
    );
    expect(feedSection).toHaveTextContent(/Provider warmup/);
    expect(feedSection).toHaveTextContent(/ranked opportunity queue may be incomplete/i);
    // Raw reason code remains available as technical detail.
    expect(feedSection).toHaveTextContent("PROVIDER_WARMUP");
  });

  it("treats a non-live UNAVAILABLE feed as a fault with next steps", async () => {
    stubFetch({
      context: PAPER_CONTEXT,
      feed: { ...FEED_READY, feed_status: "UNAVAILABLE", items: [] },
    });
    renderControl("PAPER");

    const feedSection = await screen.findByRole("region", {
      name: "Opportunity feed readiness",
    });
    await waitFor(() =>
      expect(feedSection).toHaveTextContent(/Opportunity feed unavailable/),
    );
    expect(feedSection).toHaveTextContent(/cannot be trusted right now/);
    expect(feedSection).not.toHaveTextContent(/no opportunity engine/);
  });

  it("treats a Live UNAVAILABLE feed as by-design", async () => {
    stubFetch({
      context: LIVE_CONTEXT,
      feed: { ...FEED_READY, feed_status: "UNAVAILABLE", items: [] },
    });
    renderControl("LIVE");

    const feedSection = await screen.findByRole("region", {
      name: "Opportunity feed readiness",
    });
    await waitFor(() =>
      expect(feedSection).toHaveTextContent(/Live mode has no opportunity engine/),
    );
    expect(feedSection).not.toHaveTextContent(/cannot be trusted right now/);
  });

  it("fails closed when operator diagnostics are unavailable", async () => {
    stubFetch({ diagnosticsOk: false });
    renderControl("DEMO");

    expect(await screen.findByText(/Provider readiness is unavailable/)).toBeInTheDocument();
    expect(await screen.findByText(/Operator diagnostics are unavailable/)).toBeInTheDocument();
    const hero = document.getElementById(CONTROL_SECTIONS.overview);
    expect(hero).toHaveTextContent("Unavailable");
  });

  it("renders loading state before any endpoint resolves", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderControl("DEMO");
    expect(screen.getAllByText("Checking…").length).toBeGreaterThan(0);
    expect(screen.getByText(/Checking providers/)).toBeInTheDocument();
    expect(screen.getByText(/Checking the opportunity feed/)).toBeInTheDocument();
  });

  it("marks and scrolls to the feed section for Command deep-links", async () => {
    stubFetch({
      feed: { ...FEED_READY, feed_status: "UNREADY", unready_reason: "PROVIDER_WARMUP", items: [] },
    });
    renderControl("DEMO", "/control#control-feed");

    const feedSection = await screen.findByRole("region", {
      name: "Opportunity feed readiness",
    });
    expect(feedSection).toHaveAttribute("data-highlighted", "true");
    await waitFor(() => expect(feedSection).toHaveTextContent(/Provider warmup/));
  });

  it("gates apply-update behind availability and an explicit confirm", async () => {
    stubFetch({
      lifecycle: { ...LIFECYCLE_READY, update: { status: "AVAILABLE", detail: "2 commits behind." } },
    });
    renderControl("DEMO");

    const apply = await screen.findByRole("button", { name: "Apply fast-forward update" });
    await waitFor(() => expect(apply).toBeEnabled());
    fireEvent.click(apply);
    const confirm = await screen.findByRole("button", { name: "Confirm apply and restart" });
    fireEvent.click(confirm);
    await waitFor(() =>
      expect(screen.getByText(/apply update queued/i)).toBeInTheDocument(),
    );
  });

  it("keeps apply-update disabled when no update is available", async () => {
    stubFetch();
    renderControl("DEMO");
    const apply = await screen.findByRole("button", { name: "Apply fast-forward update" });
    expect(apply).toBeDisabled();
  });

  it("flags a missing paper session in Paper mode only", async () => {
    const noSession = { ...PAPER_PORTFOLIO };
    delete (noSession as Record<string, unknown>).session;
    stubFetch({ context: PAPER_CONTEXT, portfolio: noSession });
    renderControl("PAPER");

    expect(await screen.findByText("No paper session open")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Portfolio" })).toHaveAttribute(
      "href",
      "/portfolio",
    );
  });

  it("renders an unrecognized feed state honestly instead of as healthy", async () => {
    stubFetch({ feed: { ...FEED_READY, feed_status: "SOME_FUTURE_STATE", items: [] } });
    renderControl("DEMO");

    expect(await screen.findByText(/unrecognized state/)).toBeInTheDocument();
    expect(screen.queryByText("Radar ready")).not.toBeInTheDocument();
  });

  it("renders readiness BLOCKED as critical with the failing check as work", async () => {
    stubFetch({
      readiness: {
        status: "BLOCKED",
        checks: [
          {
            id: "python",
            label: "Python 3.11",
            status: "FAIL",
            detail: "Detected Python 3.10.",
            required: true,
            next_action: "Install CPython 3.11 and run setup again.",
          },
        ],
        providers: [],
      },
    });
    renderControl("DEMO");

    const hero = await screen.findByRole("region", { name: "Platform status" });
    await waitFor(() => expect(hero).toHaveTextContent("Blocked"));
    // The readiness fact renders the blocked state, never a healthy label.
    const readinessFact = within(hero).getByText("Setup readiness").parentElement;
    expect(readinessFact).toHaveTextContent("Blocked");
    expect(readinessFact).not.toHaveTextContent("Ready");
    const attention = await screen.findByRole("region", { name: "Needs your attention" });
    expect(attention).toHaveTextContent("Python 3.11");
    expect(attention).toHaveTextContent(/Install CPython 3.11/);
  });

  it("links to diagnostics and settings as router navigation", async () => {
    stubFetch();
    renderControl("DEMO");

    expect(
      await screen.findByRole("link", { name: "View provider diagnostics" }),
    ).toHaveAttribute("href", "/diagnostics/provider");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("link", { name: "Open Radar" })).toHaveAttribute("href", "/radar");
  });

  it("shows Item 9 2/3 as calendar IDLE in system status with Live OFF and calibration forbidden", async () => {
    stubFetch();
    renderControl("DEMO");

    const systemStatus = document.getElementById(CONTROL_SECTIONS.systemStatus);
    expect(systemStatus).toBeTruthy();
    await waitFor(() =>
      expect(systemStatus).toHaveTextContent(/2\/3 · NOT CALIBRATED · CALIBRATION FORBIDDEN/),
    );
    expect(systemStatus).toHaveTextContent(/Live OFF/);
    const corpusRow = within(systemStatus as HTMLElement)
      .getByText("Distinct admitted RTH dates")
      .closest("li");
    expect(corpusRow).toHaveAttribute("data-truth", "IDLE");
    expect(corpusRow).toHaveAttribute("data-kind", "waiting");
    expect(corpusRow).not.toHaveAttribute("data-truth", "DEGRADED");
    expect(corpusRow).toHaveTextContent(/still needs more distinct regular-trading-hours dates/);
    const liveRow = within(systemStatus as HTMLElement)
      .getByText("Live real-money execution")
      .closest("li");
    expect(liveRow).toHaveAttribute("data-truth", "POLICY");
    expect(liveRow).toHaveAttribute("data-kind", "policy");
    expect(liveRow).not.toHaveAttribute("data-truth", "BLOCKED");
    expect(liveRow).toHaveTextContent(/Intentional safety lock/);
    expect(liveRow).not.toHaveTextContent(/gate is cleared/);
    expect(systemStatus).toHaveTextContent(/Waiting on the trading calendar/);
    expect(systemStatus).toHaveTextContent(/NOT CALIBRATED/);
    expect(systemStatus).toHaveTextContent(/CALIBRATION FORBIDDEN/);
  });

  it("consumes operator_truth Item 9 IDLE when present and keeps Live OFF as POLICY", async () => {
    stubFetch({
      operatorTruth: {
        schema_version: "operator-truth/1.0.0",
        by_id: {
          "item9-corpus": "IDLE",
          "item9-preflight": "IDLE",
          "live-execution": "BLOCKED",
        },
      },
    });
    renderControl("DEMO");

    const systemStatus = document.getElementById(CONTROL_SECTIONS.systemStatus);
    expect(systemStatus).toBeTruthy();
    await waitFor(() =>
      expect(systemStatus).toHaveTextContent(/2\/3 · NOT CALIBRATED · CALIBRATION FORBIDDEN/),
    );
    const corpusRow = within(systemStatus as HTMLElement)
      .getByText("Distinct admitted RTH dates")
      .closest("li");
    expect(corpusRow).toHaveAttribute("data-truth", "IDLE");
    expect(corpusRow).not.toHaveAttribute("data-truth", "DEGRADED");
    const liveRow = within(systemStatus as HTMLElement)
      .getByText("Live real-money execution")
      .closest("li");
    expect(liveRow).toHaveAttribute("data-truth", "POLICY");
    expect(liveRow).toHaveTextContent(/Live OFF/);
    expect(liveRow).not.toHaveAttribute("data-truth", "BLOCKED");
  });
});

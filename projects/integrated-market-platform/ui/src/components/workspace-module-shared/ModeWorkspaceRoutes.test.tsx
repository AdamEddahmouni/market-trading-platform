import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ComponentType } from "react";
import { describe, expect, it, vi } from "vitest";
import type { Mode } from "../mode-session/types";
import { ModeCatalystWorkspaceRoute } from "../catalyst/ModeCatalystWorkspaceRoute";
import { ModeDisclosureWorkspaceRoute } from "../disclosure/ModeDisclosureWorkspaceRoute";
import { ModeFundEtfWorkspaceRoute } from "../fundetf/ModeFundEtfWorkspaceRoute";
import { ModeFuturesWorkspaceRoute } from "../futures/ModeFuturesWorkspaceRoute";
import { ModeInstitutionalFlowWorkspaceRoute } from "../institutional/ModeInstitutionalFlowWorkspaceRoute";
import { ModeLargeTransactionsWorkspaceRoute } from "../largetransactions/ModeLargeTransactionsWorkspaceRoute";
import { ModeOptionsWorkspaceRoute } from "../options/ModeOptionsWorkspaceRoute";
import { ModeOrderBookWorkspaceRoute } from "../orderbook/ModeOrderBookWorkspaceRoute";
import { ModeOrderFlowWorkspaceRoute } from "../orderflow/ModeOrderFlowWorkspaceRoute";
import { ModeSqueezeWorkspaceRoute } from "../squeeze/ModeSqueezeWorkspaceRoute";

vi.mock("./LiveLaneOperationalStrip", () => ({
  LiveLaneOperationalStrip: () => <div data-testid="live-operational-strip">Live operational context</div>,
}));

vi.mock("../../api/hooks", () => ({
  useWorkspaceSqueezeQuery: () => ({
    isLoading: false,
    data: {
      available: true,
      symbol: "BIYA",
      source: "donor",
      bridge_mode: "READ_ONLY",
      replay_chart_available: false,
      ignition_state: "WATCH",
      freshness: "FROZEN",
      rules: [],
    },
  }),
  useWorkspaceOrderFlowQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceOrderBookQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceFuturesQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceCatalystQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceFundEtfQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceOptionsQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceLargeTransactionsQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceDisclosureQuery: () => ({ isLoading: false, data: { available: false } }),
  useWorkspaceInstitutionalFlowQuery: () => ({
    isLoading: false,
    data: {
      symbol: "BIYA",
      family_count: 2,
      available_family_count: 1,
      families: [
        {
          family_id: "whale-a",
          label: "Whale A",
          entitled_symbol: "BIYA",
          route_path: "/workspace/BIYA/institutional-flow",
          available: true,
          explanation_ref: "explain:whale-a",
        },
      ],
    },
  }),
}));

type RouteCase = {
  label: string;
  path: string;
  Component: ComponentType<{ mode: Mode }>;
  heading: RegExp;
  paperHint?: RegExp;
  liveHint?: RegExp;
};

const routeCases: RouteCase[] = [
  {
    label: "squeeze",
    path: "/workspace/BIYA/squeeze",
    Component: ModeSqueezeWorkspaceRoute,
    heading: /BIYA — Short Squeeze Workspace/i,
    paperHint: /Preview squeeze ignition/i,
    liveHint: /broker-observed squeeze signals/i,
  },
  {
    label: "order-flow",
    path: "/workspace/NVDA/order-flow",
    Component: ModeOrderFlowWorkspaceRoute,
    heading: /NVDA — Order Flow Workspace/i,
    paperHint: /CVD evidence to inform paper order sizing/i,
    liveHint: /broker-reported order flow/i,
  },
  {
    label: "order-book",
    path: "/workspace/NVDA/order-book",
    Component: ModeOrderBookWorkspaceRoute,
    heading: /NVDA — Order Book Workspace/i,
    paperHint: /depth imbalance before paper order preview/i,
    liveHint: /Visible liquidity is broker-observed/i,
  },
  {
    label: "futures",
    path: "/workspace/ES/futures",
    Component: ModeFuturesWorkspaceRoute,
    heading: /ES — Futures Workspace/i,
    paperHint: /macro backdrop into paper simulation/i,
    liveHint: /ES depth is observational/i,
  },
  {
    label: "catalyst",
    path: "/workspace/BOXL/catalyst",
    Component: ModeCatalystWorkspaceRoute,
    heading: /BOXL — Catalyst Workspace/i,
    paperHint: /catalyst events into paper thesis/i,
    liveHint: /Public catalyst bridge is read-only/i,
  },
  {
    label: "fund-etf",
    path: "/workspace/NVDA/fund-etf",
    Component: ModeFundEtfWorkspaceRoute,
    heading: /NVDA — Fund \/ ETF Workspace/i,
    paperHint: /ETF flow proxies for cross-asset paper context/i,
    liveHint: /Fund-flow proxies are observational/i,
  },
  {
    label: "options",
    path: "/workspace/BIYA/options",
    Component: ModeOptionsWorkspaceRoute,
    heading: /BIYA — Options Workspace/i,
    paperHint: /unusual activity to inform paper sizing/i,
    liveHint: /Options activity is broker-observed/i,
  },
  {
    label: "large-transactions",
    path: "/workspace/NVDA/large-transactions",
    Component: ModeLargeTransactionsWorkspaceRoute,
    heading: /NVDA — Large Transactions Workspace/i,
    paperHint: /size prints for paper context/i,
    liveHint: /Large prints are observational/i,
  },
  {
    label: "disclosure",
    path: "/workspace/BIYA/disclosure",
    Component: ModeDisclosureWorkspaceRoute,
    heading: /BIYA — Disclosure Workspace/i,
    paperHint: /filing events for paper research/i,
    liveHint: /Delayed filings remain read-only/i,
  },
  {
    label: "institutional-flow",
    path: "/workspace/BIYA/institutional-flow",
    Component: ModeInstitutionalFlowWorkspaceRoute,
    heading: /BIYA — Institutional Flow/i,
    paperHint: /whale evidence for paper thesis/i,
    liveHint: /Institutional flow is observational/i,
  },
];

function renderRouteCase({ path, Component }: RouteCase, mode: Mode) {
  const routePath = path.replace(/\/workspace\/[^/]+/, "/workspace/:symbol");
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={<Component mode={mode} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Mode workspace routes", () => {
  it.each(routeCases)("renders Demo $label module chrome", ({ heading, ...routeCase }) => {
    renderRouteCase(routeCase, "DEMO");
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByText(/Demo is exploration only/i)).toBeInTheDocument();
    expect(screen.getByText(/Demo lane context/i)).toBeInTheDocument();
  });

  it.each(routeCases)(
    "renders Paper $label module with draft shortcut and hints",
    ({ path, heading, paperHint, ...routeCase }) => {
      renderRouteCase({ path, heading, paperHint, ...routeCase }, "PAPER");
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
      if (paperHint) expect(screen.getByText(paperHint)).toBeInTheDocument();
      const overviewHref = path.replace(/\/[^/]+$/, "");
      expect(screen.getByRole("link", { name: "Draft paper order from lane" })).toHaveAttribute(
        "href",
        overviewHref,
      );
      expect(screen.getByRole("link", { name: "Open workspace overview" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Open paper portfolio" })).toHaveAttribute(
        "href",
        "/portfolio",
      );
      expect(screen.getByText(/Paper lane context/i)).toBeInTheDocument();
      expect(screen.getByText(/Placeholder draft uses BUY × 1 MARKET/i)).toBeInTheDocument();
    },
  );

  it.each(routeCases)(
    "renders Live $label module with canary link and hints",
    ({ heading, liveHint, ...routeCase }) => {
      renderRouteCase(routeCase, "LIVE");
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
      if (liveHint) expect(screen.getAllByText(liveHint).length).toBeGreaterThan(0);
      expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
        "href",
        "/live-canary",
      );
      expect(screen.getByText(/Live lane context/i)).toBeInTheDocument();
    },
  );
});

describe("Priority lane product differentiation", () => {
  it("shows distinct squeeze lane headlines across modes", () => {
    const squeezeCase = routeCases.find((row) => row.label === "squeeze")!;
    renderRouteCase(squeezeCase, "DEMO");
    expect(screen.getByRole("heading", { name: /Squeeze replay/i })).toBeInTheDocument();
    cleanup();

    renderRouteCase(squeezeCase, "PAPER");
    expect(screen.getByRole("heading", { name: /Squeeze simulation readiness/i })).toBeInTheDocument();
    cleanup();

    renderRouteCase(squeezeCase, "LIVE");
    expect(screen.getByRole("heading", { name: /Live squeeze observational/i })).toBeInTheDocument();
  });
});

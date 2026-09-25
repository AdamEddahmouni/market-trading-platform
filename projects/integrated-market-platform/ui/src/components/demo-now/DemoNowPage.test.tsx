import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import demoNowCss from "../../styles/demo-now.css?raw";
import { DemoNowPage, type DemoNowPageProps } from "./DemoNowPage";

vi.mock("../../api/opportunityClient", () => ({
  useOpportunitiesSummaryQuery: () => ({
    data: { items: [], feed_status: "EMPTY" },
    isLoading: false,
    isError: false,
  }),
}));

const attention: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Replay signal requires review",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "REPLAY_SIGNAL", label: "Signal entered at this event" }],
};

const portfolio = {
  account: { cash_display: "$100,000.00", realized_pnl_display: "$0.00" },
  pnl: { total_display: "+$25.00" },
  exposure: { gross_shares: 100 },
  risk: { open_order_count: 0 },
} as PaperPortfolioResponse;

function props(overrides: Partial<DemoNowPageProps> = {}): DemoNowPageProps {
  return {
    items: [attention],
    attentionState: "ready",
    replayState: "ready",
    cursorIndex: 0,
    eventCount: 4,
    scrubState: "idle",
    portfolioState: "ready",
    portfolio,
    onScrub: vi.fn(),
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
    ...overrides,
  };
}

function renderPage(overrides: Partial<DemoNowPageProps> = {}) {
  return render(
    <MemoryRouter>
      <DemoNowPage {...props(overrides)} />
    </MemoryRouter>,
  );
}

describe("DemoNowPage", () => {
  it("composes one page heading and four named operational regions", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 1, name: "See the market unfold" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Decision metrics" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Primary review queue" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Replay overview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Simulated portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Inspect next" })).toBeInTheDocument();
  });

  it("preserves attention callbacks and supplies the confirmed next cursor", () => {
    const value = props({ cursorIndex: 1 });
    render(
      <MemoryRouter>
        <DemoNowPage {...value} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Attention (1)" }));
    fireEvent.click(screen.getByRole("button", { name: "Why here?" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Explain" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(value.onWhy).toHaveBeenCalledWith(attention);
    expect(value.onExplain).toHaveBeenCalledWith(attention);
    expect(value.onInspect).toHaveBeenCalledWith(attention);
    expect(value.onOpenWorkspace).toHaveBeenCalledWith(attention);
    expect(value.onScrub).toHaveBeenCalledWith(2);
  });

  it("degrades attention and portfolio independently while replay remains usable", () => {
    renderPage({ attentionState: "error", portfolioState: "error", portfolio: undefined });
    // Errored feeds carry no count on the tab.
    fireEvent.click(screen.getByRole("tab", { name: "Attention" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable.");
    expect(screen.getByText(/Simulated portfolio unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next event" })).toBeEnabled();
  });

  it("renders no execution or session mutation controls", () => {
    renderPage();
    for (const name of [/order ticket/i, /paper session/i, /kill switch/i, /authorization/i, /execute/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});

describe("Demo Now layout structure", () => {
  it("exposes the balanced command grid and panel hierarchy", () => {
    renderPage();
    expect(document.querySelector(".demo-now-page")).toBeTruthy();
    expect(document.querySelector(".demo-now-grid-top")).toBeTruthy();
    expect(document.querySelector(".demo-now-grid-bottom")).toBeTruthy();
    expect(document.querySelector(".demo-replay-panel")).toBeTruthy();
    expect(document.querySelector(".demo-portfolio-panel")).toBeTruthy();
    expect(document.querySelector(".imp-overview-primary-queue")).toBeTruthy();
    expect(document.querySelector(".demo-inspect-panel")).toBeTruthy();
  });
});

describe("Demo Now visual accessibility contract", () => {
  it("keeps targets, focus, responsive, reduced-motion, and forced-color rules explicit", () => {
    expect(demoNowCss).toContain("min-height: 44px");
    expect(demoNowCss).toContain(":focus-visible");
    expect(demoNowCss).toContain("@media (max-width: 1024px)");
    expect(demoNowCss).toContain("@media (max-width: 720px)");
    expect(demoNowCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(demoNowCss).toContain("@media (forced-colors: active)");
  });
});

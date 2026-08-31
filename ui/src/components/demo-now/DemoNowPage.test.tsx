import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { DemoNowPage, type DemoNowPageProps } from "./DemoNowPage";

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
    onOpenTimeline: vi.fn(),
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
    ...overrides,
  };
}

describe("DemoNowPage", () => {
  it("composes one page heading and four named operational regions", () => {
    render(<DemoNowPage {...props()} />);
    expect(screen.getByRole("heading", { level: 1, name: "See the market unfold" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Replay overview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Simulated portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "What matters now" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Inspect next" })).toBeInTheDocument();
  });

  it("preserves attention callbacks and supplies the confirmed next cursor", () => {
    const value = props({ cursorIndex: 1 });
    render(<DemoNowPage {...value} />);
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
    render(
      <DemoNowPage
        {...props({ attentionState: "error", portfolioState: "error", portfolio: undefined })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");
    expect(screen.getByText(/Simulated portfolio unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next event" })).toBeEnabled();
  });

  it("renders no execution or session mutation controls", () => {
    render(<DemoNowPage {...props()} />);
    for (const name of [/order ticket/i, /paper session/i, /kill switch/i, /authorization/i, /execute/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});

describe("Demo Now layout structure", () => {
  it("exposes the balanced command grid and panel hierarchy", () => {
    render(<DemoNowPage {...props()} />);
    expect(document.querySelector(".demo-now-page")).toBeTruthy();
    expect(document.querySelector(".demo-now-grid-top")).toBeTruthy();
    expect(document.querySelector(".demo-now-grid-bottom")).toBeTruthy();
    expect(document.querySelector(".demo-replay-panel")).toBeTruthy();
    expect(document.querySelector(".demo-portfolio-panel")).toBeTruthy();
    expect(document.querySelector(".demo-attention-panel")).toBeTruthy();
    expect(document.querySelector(".demo-inspect-panel")).toBeTruthy();
  });
});

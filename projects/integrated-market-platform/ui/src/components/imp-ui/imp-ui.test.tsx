import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AttentionBanner } from "./AttentionBanner";
import { ConfidenceIndicator, confidenceBand } from "./ConfidenceIndicator";
import { CopyableIdentifier, truncateMiddle } from "./CopyableIdentifier";
import { EmptyState, ErrorState } from "./FeedbackStates";
import { FreshnessIndicator, formatRelativeAge, freshnessBand, parseAsOfMs } from "./FreshnessIndicator";
import { LinkTabs } from "./LinkTabs";
import { StatePill } from "./StatePill";

describe("StatePill", () => {
  it("pairs tone with icon and text, never color alone", () => {
    render(<StatePill tone="caution" label="Stale" raw="STALE" />);
    const pill = screen.getByTestId("imp-ui-state-pill");
    expect(pill).toHaveAttribute("data-tone", "caution");
    expect(pill).toHaveTextContent("Stale");
    expect(pill.querySelector(".imp-ui-state-pill-icon")).toHaveTextContent("▲");
    expect(pill).toHaveAttribute("title", "STALE");
  });
});

describe("AttentionBanner", () => {
  it("uses role=alert only for critical tone", () => {
    const { rerender } = render(
      <MemoryRouter>
        <AttentionBanner tone="critical">Trading is blocked.</AttentionBanner>
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Trading is blocked.");
    rerender(
      <MemoryRouter>
        <AttentionBanner tone="caution">Data is stale.</AttentionBanner>
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Data is stale.");
  });

  it("renders the 3-question slots", () => {
    render(
      <MemoryRouter>
        <AttentionBanner
          tone="caution"
          affects="Ranked opportunities may be incomplete."
          action={{ label: "Check Providers", href: "/diagnostics/provider" }}
        >
          Market data is partially degraded.
        </AttentionBanner>
      </MemoryRouter>,
    );
    const banner = screen.getByTestId("imp-ui-attention-banner");
    expect(banner).toHaveTextContent("Market data is partially degraded.");
    expect(banner).toHaveTextContent("Ranked opportunities may be incomplete.");
    expect(screen.getByRole("link", { name: "Check Providers" })).toHaveAttribute(
      "href",
      "/diagnostics/provider",
    );
  });
});

describe("FreshnessIndicator", () => {
  it("lets the backend word win when present", () => {
    render(<FreshnessIndicator backendLabel="STALE" />);
    expect(screen.getByTestId("imp-ui-freshness")).toHaveAttribute("data-tone", "caution");
    expect(screen.getByTestId("imp-ui-freshness")).toHaveTextContent("stale");
  });

  it("renders relative age with a stale consequence", () => {
    const old = Date.now() - 10 * 60 * 1000;
    render(<FreshnessIndicator asOf={old} cadenceSeconds={5} />);
    const indicator = screen.getByTestId("imp-ui-freshness");
    expect(indicator).toHaveAttribute("data-tone", "caution");
    expect(indicator).toHaveTextContent("updated 10m ago");
    expect(indicator).toHaveTextContent("may be delayed");
  });

  it("renders unknown when no inputs exist", () => {
    render(<FreshnessIndicator />);
    expect(screen.getByTestId("imp-ui-freshness")).toHaveTextContent("Freshness unknown");
  });

  it("parses epoch nanoseconds and ISO strings", () => {
    const ms = Date.parse("2026-08-30T12:00:00Z");
    expect(parseAsOfMs(ms * 1_000_000)).toBe(ms);
    expect(parseAsOfMs("2026-08-30T12:00:00Z")).toBe(ms);
    expect(parseAsOfMs("not-a-date")).toBeNull();
    expect(parseAsOfMs(-5)).toBeNull();
  });

  it("formats relative ages", () => {
    const now = 1_000_000_000_000;
    expect(formatRelativeAge(now - 3000, now)).toBe("just now");
    expect(formatRelativeAge(now - 30_000, now)).toBe("30s ago");
    expect(formatRelativeAge(now - 5 * 60_000, now)).toBe("5m ago");
    expect(formatRelativeAge(now - 3 * 3_600_000, now)).toBe("3h ago");
    expect(formatRelativeAge(now - 2 * 86_400_000, now)).toBe("2d ago");
  });

  it("bands freshness by cadence", () => {
    expect(freshnessBand(1000, 5)).toBe("fresh");
    expect(freshnessBand(30_000, 5)).toBe("lagging");
    expect(freshnessBand(120_000, 5)).toBe("stale");
  });
});

describe("ConfidenceIndicator", () => {
  it("bands values instead of showing false precision", () => {
    expect(confidenceBand(0.1)).toBe("low");
    expect(confidenceBand(0.5)).toBe("medium");
    expect(confidenceBand(0.9)).toBe("high");
  });

  it("renders nothing when confidence is missing", () => {
    const { container } = render(<ConfidenceIndicator value={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the band with the numeric value in the tooltip", () => {
    render(<ConfidenceIndicator value={0.82} />);
    const indicator = screen.getByTestId("imp-ui-confidence");
    expect(indicator).toHaveTextContent("High confidence");
    expect(indicator).toHaveAttribute("title", "Confidence 82%");
  });
});

describe("EmptyState", () => {
  it("requires and renders the why-empty reason", () => {
    render(
      <MemoryRouter>
        <EmptyState
          title="No opportunities right now"
          reason="Nothing has been minted for the current coverage."
          action={{ label: "Open Screeners", href: "/radar/screeners" }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "No opportunities right now" })).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been minted/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Screeners" })).toHaveAttribute(
      "href",
      "/radar/screeners",
    );
  });
});

describe("ErrorState", () => {
  it("renders humanized failure with retry and raw detail disclosure", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        title="Opportunity ranking is unavailable."
        affects="The ranked queue cannot be loaded."
        rawDetail="PROVIDER_UNAVAILABLE: OPEND_DOWN"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Opportunity ranking is unavailable.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.getByText("PROVIDER_UNAVAILABLE: OPEND_DOWN")).toBeInTheDocument();
  });
});

describe("CopyableIdentifier", () => {
  it("truncates long identifiers in the middle", () => {
    expect(truncateMiddle("7CBA5536EED17C4A6246327EE7ABF223C58")).toBe("7CBA…3C58");
    expect(truncateMiddle("short")).toBe("short");
  });

  it("renders the truncated value with the full value reachable", () => {
    render(<CopyableIdentifier value="7CBA5536EED17C4A6246327EE7ABF223C58" prefix="Acct" />);
    const id = screen.getByTestId("imp-ui-copyable-id");
    expect(id).toHaveTextContent("Acct 7CBA…3C58");
    expect(id).toHaveAttribute("title", "7CBA5536EED17C4A6246327EE7ABF223C58");
    expect(screen.getByRole("button", { name: /Copy full identifier/ })).toBeInTheDocument();
  });
});

describe("LinkTabs", () => {  it("marks the active tab with aria-current", () => {
    render(
      <MemoryRouter initialEntries={["/radar/screeners"]}>
        <LinkTabs
          label="Radar sections"
          items={[
            { to: "/radar", label: "Opportunities", end: true },
            { to: "/radar/screeners", label: "Screeners" },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Screeners" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Opportunities" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});

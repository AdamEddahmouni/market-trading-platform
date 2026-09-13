import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../../api/client";
import liveNowCss from "../../styles/live-now.css?raw";
import { LiveNowPage, type LiveNowPageProps } from "./LiveNowPage";
import { canarySnapshot, providerHealth } from "./liveNowTestFixtures";

vi.mock("../../api/hooks", () => ({
  useSymbolSearchQuery: () => ({ data: { results: [] }, isLoading: false }),
  useInstrumentCapabilitiesQuery: () => ({ data: { capabilities: [] }, isLoading: false }),
  useSubscribeMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

const attention: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "AAPL",
  headline: "Live feed requires review",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "LIVE_SIGNAL", label: "Signal entered in live feed" }],
};

function pageProps(overrides: Partial<LiveNowPageProps> = {}): LiveNowPageProps {
  return {
    items: [attention],
    attentionState: "ready",
    dataMode: "LIVE_OBSERVATIONAL",
    executionAuthority: "BLOCKED",
    providerHealth: providerHealth(),
    providerState: "ready",
    canarySnapshot: canarySnapshot(),
    safetyState: "ready",
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
    ...overrides,
  };
}

describe("LiveNowPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("composes one Live Watch heading and four named operational regions", () => {
    render(
      <MemoryRouter>
        <LiveNowPage {...pageProps()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Live Watch" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Connection summary" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Operational safety" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Symbol lookup" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "What matters now" })).toBeInTheDocument();
  });

  it("preserves attention callbacks and links to deeper live surfaces", () => {
    const props = pageProps();
    render(
      <MemoryRouter>
        <LiveNowPage {...props} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Why here?" }));
    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(props.onWhy).toHaveBeenCalledWith(attention);
    expect(props.onExplain).toHaveBeenCalledWith(attention);
    expect(props.onInspect).toHaveBeenCalledWith(attention);
    expect(props.onOpenWorkspace).toHaveBeenCalledWith(attention);
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute("href", "/live-canary");
    expect(screen.getByRole("link", { name: "Provider diagnostics" })).toHaveAttribute(
      "href",
      "/diagnostics/provider",
    );
  });

  it("degrades provider and safety regions independently", () => {
    render(
      <MemoryRouter>
        <LiveNowPage
          {...pageProps({
            providerState: "error",
            providerHealth: undefined,
            safetyState: "ready",
          })}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Provider health unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Live execution blocked")).toBeInTheDocument();
    expect(screen.getByText("Live feed requires review")).toBeInTheDocument();
  });

  it("contains no execution, session, or order mutation controls", () => {
    render(
      <MemoryRouter>
        <LiveNowPage {...pageProps()} />
      </MemoryRouter>,
    );
    for (const name of [
      "Submit",
      "Cancel order",
      "Open session",
      "Close session",
      "Archive session",
      "New Paper Session",
      "Preview",
    ]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("locks the live stylesheet accessibility contract", () => {
    expect(liveNowCss).toContain(".live-now-page");
    expect(liveNowCss).toContain("min-height: 44px");
    expect(liveNowCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(liveNowCss).toContain("@media (forced-colors: active)");
    expect(liveNowCss).toContain("@media (max-width: 720px)");
  });
});

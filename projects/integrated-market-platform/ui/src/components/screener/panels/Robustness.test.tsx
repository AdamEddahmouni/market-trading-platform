import { Suspense, useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { fetchJson, SchemaMismatchError } from "../../../api/fetchJson";
import { badgeSummary, badgeTone } from "../news/NewsBadge";
import { Age, ErrorDetail, PanelErrorBoundary, reloadableLazy, ScreenerErrorBoundary, SpecialistContext, type SpecialistSelection } from "./shared";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

function Boom({ when }: { when: boolean }) {
  if (when) throw new Error("schema drift");
  return <p>panel body</p>;
}

describe("Live data age", () => {
  it("keeps counting between fetches and dims once past its limit", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-30T12:00:00Z"));
    render(<Age iso="2026-09-30T11:59:50Z" staleMs={30_000} />);
    const age = screen.getByText("10s");
    expect(age.tagName).toBe("TIME");
    expect(age).not.toHaveClass("stale");
    act(() => { vi.advanceTimersByTime(25_000); });
    expect(screen.getByText("35s")).toHaveClass("stale");
    // Past a minute it ticks every 15 s at minute resolution.
    act(() => { vi.advanceTimersByTime(3 * 60_000); });
    expect(screen.getByText("4m")).toBeInTheDocument();
  });

  it("renders nothing without a timestamp", () => {
    const { container } = render(<Age iso={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Contained failures", () => {
  it("keeps a render failure inside its boundary and clears it when the selection changes", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Harness() {
      const [key, setKey] = useState("AAPL");
      const [broken, setBroken] = useState(true);
      return <>
        <button type="button" onClick={() => { setBroken(false); setKey("NVDA"); }}>select NVDA</button>
        <ScreenerErrorBoundary label="Charts" resetKey={key}><Boom when={broken} /></ScreenerErrorBoundary>
        <p>sibling panel</p>
      </>;
    }
    render(<Harness />);
    expect(screen.getByRole("alert")).toHaveTextContent("Charts failed to render.");
    expect(screen.getByText("sibling panel")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "select NVDA" }));
    expect(screen.getByText("panel body")).toBeInTheDocument();
  });

  it("Retry resets the panel's inactive screener queries before remounting it", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const client = new QueryClient();
    client.setQueryData(["screener-chart", "US_EQUITIES", "AAPL"], { bad: true });
    client.setQueryData(["main-screener-config"], { keep: true });
    let broken = true;
    function Flaky() { return <Boom when={broken} />; }
    const selection = { settledId: "AAPL", universe: "US_EQUITIES" } as SpecialistSelection;
    render(<QueryClientProvider client={client}><SpecialistContext.Provider value={selection}>
      <PanelErrorBoundary id="charts"><Flaky /></PanelErrorBoundary></SpecialistContext.Provider></QueryClientProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent("Charts failed to render.");
    broken = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByText("panel body")).toBeInTheDocument();
    expect(client.getQueryData(["screener-chart", "US_EQUITIES", "AAPL"])).toBeUndefined();
    expect(client.getQueryData(["main-screener-config"])).toEqual({ keep: true });
  });

  it("retries a code chunk that failed to load instead of re-throwing the cached failure", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    let attempts = 0;
    const Lazy = reloadableLazy(async () => {
      attempts += 1;
      if (attempts === 1) throw new TypeError("Failed to fetch dynamically imported module: /assets/NewsView.js");
      return { default: () => <p>news view</p> };
    });
    render(<ScreenerErrorBoundary label="The News view"><Suspense fallback={<p>loading</p>}><Lazy /></Suspense></ScreenerErrorBoundary>);
    expect(await screen.findByRole("alert")).toHaveTextContent("The News view could not load its code");
    // A failed load is not re-imported on its own (no loop while offline); only Retry tries again.
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    expect(attempts).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("news view")).toBeInTheDocument();
    expect(attempts).toBe(2);
  });

  it("names a UI/API schema mismatch instead of reporting a provider outage", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ state: 7 }), { status: 200 })));
    const error = await fetchJson("/screener/panels/cvd?instrument=AAPL", z.object({ state: z.string() })).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(SchemaMismatchError);
    expect((error as SchemaMismatchError).issues[0].path).toEqual(["state"]);
    render(<p>CVD request failed.<ErrorDetail error={error} /></p>);
    expect(screen.getByText("/screener/panels/cvd")).toBeInTheDocument(); // the query string is not echoed
    expect(screen.getByText(/did not match the format this build expects/)).toBeInTheDocument();
    const { container } = render(<ErrorDetail error={new Error("Request failed")} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Grid news badge tone", () => {
  const row = (positive: number, neutral: number, negative: number, unscored = 0) =>
    ({ count: positive + neutral + negative + unscored, unscored, latest_at: null, tone: { positive, neutral, negative } });
  it("summarizes headline tone without inventing one for unscored stories", () => {
    expect(badgeTone(row(2, 1, 0))).toBe("positive");
    expect(badgeTone(row(0, 1, 3))).toBe("negative");
    expect(badgeTone(row(2, 0, 2))).toBe("mixed");
    expect(badgeTone(row(1, 4, 1))).toBe("neutral");
    expect(badgeTone(row(0, 0, 0, 3))).toBe("unscored");
    expect(badgeSummary(row(1, 0, 0))).toBe("1 story in 24h · 1 positive");
    expect(badgeSummary(row(0, 0, 0, 2))).toBe("2 stories in 24h · 2 unscored");
  });
});

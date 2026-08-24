import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoverPage } from "./DiscoverPage";

const mixedPayload = {
  available: true,
  mode: "SEMI_LIVE",
  candidate_role: "INVESTIGATE",
  execution_authority: "NONE",
  generated_at: "2026-08-24T15:00:00Z",
  discovery_as_of: "2026-08-24T14:59:00Z",
  refresh_in_progress: false,
  refresh_interval_seconds: 120,
  poll_interval_seconds: 3,
  provider_health: [
    { provider: "FINVIZ_ELITE", connection: "HEALTHY", role: "DISCOVERY", reason: null },
    { provider: "MOOMOO", connection: "CONNECTED", reason: null, subscribed_candidates: 1 },
  ],
  lane_counts: { MOMENTUM: 1, SQUEEZE: 1, CATALYST: 0, SWING: 0 },
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
      available_time_ns: 1,
      quality: "PASS",
      provenance: [{ provider: "FINVIZ_ELITE", screen_id: "UNUSUAL_VOLUME_DISCOVERY" }],
      attention_score: 74.5,
      attention_components: {
        setup_strength: 31,
        freshness: 18.5,
        liquidity_marketability: 15,
        live_confirmation: 10,
        quality_penalty: 0,
      },
      ranking_reasons: ["RVOL_3.10", "FRESH_L1_QUOTE"],
      market: {
        provider: "MOOMOO",
        status: "LIVE",
        as_of_ns: 2,
        freshness_ms: 480,
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
      available_time_ns: 1,
      quality: "PASS",
      provenance: [{ provider: "FINVIZ_ELITE", screen_id: "SHORT_SQUEEZE_DISCOVERY" }],
      attention_score: 48,
      attention_components: { setup_strength: 20, freshness: 18, liquidity_marketability: 10, live_confirmation: 0, quality_penalty: 0 },
      ranking_reasons: ["SHORT_FLOAT_22.4_PCT"],
      market: { provider: "FINVIZ_ELITE", status: "SNAPSHOT", last_price: 24.1, quality: "PASS", reason: "NOT_SUBSCRIBED" },
      data_status: "SNAPSHOT",
      freshness_label: "SNAPSHOT",
      queue_rank: 2,
    },
  ],
};

function jsonResponse(payload: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/discover"]}>
      <Routes>
        <Route path="/discover" element={<DiscoverPage />} />
        <Route path="/workspace/:instrumentId" element={<div>Workspace opened</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DiscoverPage mixed live mode", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse(mixedPayload)));
  });

  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    vi.unstubAllGlobals();
  });

  it("defaults to the ranked mixed queue with explicit market-data status", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Mixed live screener" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mixed Live" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("INVESTIGATE — no order authority")).toBeInTheDocument();
    expect(screen.getByText("Candidates are INVESTIGATE, not trade signals.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AAPL" })).toBeInTheDocument();
    expect(screen.getAllByText("MOMENTUM").length).toBeGreaterThan(0);
    expect(screen.getByText("LIVE · 480 ms")).toBeInTheDocument();
    expect(screen.getAllByText("FINVIZ SNAPSHOT").length).toBeGreaterThan(0);
    expect(screen.getByText("MOOMOO LIVE")).toBeInTheDocument();
    expect(screen.getByText("SNAPSHOT")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/discover/mixed/refresh",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("filters lanes and keeps inspectable ranking evidence", async () => {
    renderPage();
    await screen.findByRole("link", { name: "AAPL" });

    fireEvent.click(screen.getByRole("button", { name: "SQUEEZE" }));

    expect(screen.queryByRole("link", { name: "AAPL" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GME" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("Evidence"));
    expect(screen.getByText(/SHORT_FLOAT_22.4_PCT/)).toBeInTheDocument();
    expect(screen.getByText(/SHORT_SQUEEZE_DISCOVERY/)).toBeInTheDocument();
  });

  it("uses the read-only projection for three-second polling", async () => {
    vi.useFakeTimers();
    renderPage();

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

    await act(async () => {
      vi.advanceTimersByTime(117_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    const refreshCalls = vi.mocked(fetch).mock.calls.filter(
      ([url]) => url === "/discover/mixed/refresh",
    );
    expect(refreshCalls).toHaveLength(2);

    const callsBeforeHidden = vi.mocked(fetch).mock.calls.length;
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => {
      vi.advanceTimersByTime(120_000);
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledTimes(callsBeforeHidden);

    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(vi.mocked(fetch).mock.calls.length).toBe(callsBeforeHidden + 2);
  });

  it("keeps the single-screen diagnostic available", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Mixed live screener" });

    fireEvent.click(screen.getByRole("button", { name: "Single Screen" }));

    expect(screen.getByLabelText("Screen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh screen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Single Screen" })).toHaveAttribute("aria-pressed", "true");
  });

  it("promotes only after an explicit workspace action", async () => {
    renderPage();
    await screen.findByRole("link", { name: "AAPL" });

    fireEvent.click(screen.getAllByRole("button", { name: "Open Workspace" })[0]);

    expect(await screen.findByText("Workspace opened")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/discover/promote-to-live-analysis",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ instrument_id: "AAPL" }) }),
    );
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoDiscoverPage } from "./DemoDiscoverPage";

const mixedPayload = {
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

function renderPage() {
  return render(
    <MemoryRouter>
      <DemoDiscoverPage />
    </MemoryRouter>,
  );
}

describe("DemoDiscoverPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string | URL | Request) => {
        const path = typeof url === "string" ? url : url.toString();
        if (path.includes("/discover/mixed/release")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ released_symbols: 0 }) } as Response);
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mixedPayload) } as Response);
      }),
    );
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it("renders read-only demo discover without refresh or promote mutations", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Workspace" })).toHaveAttribute("href", "/workspace/AAPL");

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/discover/mixed", expect.objectContaining({ method: "GET" }));
    });
    expect(fetch).not.toHaveBeenCalledWith(
      "/discover/mixed/refresh",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

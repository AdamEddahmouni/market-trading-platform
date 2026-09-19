import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoverObservability } from "./DiscoverObservability";

const mixedPayload = {
  available: true,
  mode: "SEMI_LIVE",
  candidate_role: "INVESTIGATE",
  execution_authority: "NONE",
  market_session: "REGULAR",
  generated_at: "2026-08-24T15:00:00Z",
  discovery_as_of: "2026-08-24T14:59:00Z",
  candidate_count: 1,
  live_subscription_summary: { active: 1, cap: 12 },
  refresh_in_progress: false,
  refresh_interval_seconds: 120,
  poll_interval_seconds: 3,
  provider_health: [{ provider: "FINVIZ_ELITE", connection: "HEALTHY", role: "DISCOVERY" }],
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
      attention_components: { setup_strength: 31 },
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

function jsonResponse(payload: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);
}

function renderDiscover(allowMutations = false) {
  return render(
    <MemoryRouter>
      <DiscoverObservability allowMutations={allowMutations} autoRefreshOnMount={allowMutations} />
    </MemoryRouter>,
  );
}

describe("DiscoverObservability investigation boundary", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string | URL | Request) => {
        const path = typeof url === "string" ? url : url.toString();
        if (path.includes("/discover/mixed/release")) {
          return jsonResponse({ released_symbols: 0 });
        }
        if (path.includes("/discover/promote-to-live-analysis")) {
          return jsonResponse({ ok: true });
        }
        if (path.includes("/discover/mixed/refresh")) {
          return jsonResponse(mixedPayload);
        }
        if (path.includes("/discover/mixed")) {
          return jsonResponse(mixedPayload);
        }
        return jsonResponse({});
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("states investigation-only copy and keeps Live mutations off", async () => {
    renderDiscover(false);
    expect(screen.getByTestId("discover-investigation-boundary")).toHaveTextContent(
      /read-only: refresh, live-analysis promotion, and mixed-screener release stay off/i,
    );
    expect(screen.getByText("EXEC NONE · INVESTIGATE only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Workspace" })).toHaveAttribute(
      "href",
      expect.stringContaining("/workspace"),
    );
    expect(screen.queryByRole("button", { name: "Open Workspace" })).not.toBeInTheDocument();
  });

  it("does not POST mixed/release when read-only unmounts", async () => {
    const { unmount } = renderDiscover(false);
    await screen.findByText("AAPL");
    unmount();
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("/discover/mixed/release"))).toBe(
      false,
    );
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("/discover/mixed/refresh"))).toBe(
      false,
    );
  });

  it("releases mixed subscriptions only when mutations are permitted", async () => {
    const { unmount } = renderDiscover(true);
    await screen.findByText("AAPL");
    unmount();
    await waitFor(() => {
      expect(
        vi.mocked(fetch).mock.calls.some(
          ([url, init]) =>
            String(url).includes("/discover/mixed/release") &&
            typeof init === "object" &&
            init !== null &&
            "method" in init &&
            init.method === "POST",
        ),
      ).toBe(true);
    });
  });

  it("promotes to workspace analysis only from an explicit Paper action", async () => {
    renderDiscover(true);
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: "Open Workspace" }));
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/discover/promote-to-live-analysis",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ instrument_id: "AAPL" }) }),
      );
    });
  });

  it("explains an empty snapshot without inventing actionability", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string | URL | Request) => {
        const path = typeof url === "string" ? url : url.toString();
        if (path.includes("/discover/mixed") && !path.includes("release") && !path.includes("refresh")) {
          return jsonResponse({ ...mixedPayload, available: false, candidate_count: 0, candidates: [] });
        }
        return jsonResponse({ released_symbols: 0 });
      }),
    );
    renderDiscover(false);
    expect(await screen.findByTestId("imp-ui-empty-state")).toHaveTextContent(
      /not an empty ranked opportunity queue and not a signal to trade/i,
    );
    expect(screen.queryByRole("link", { name: /trade|buy|sell|submit/i })).not.toBeInTheDocument();
  });
});

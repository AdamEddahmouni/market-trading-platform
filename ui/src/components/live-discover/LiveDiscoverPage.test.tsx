import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveDiscoverPage } from "./LiveDiscoverPage";

const mixedPayload = {
  available: true,
  mode: "SEMI_LIVE",
  candidate_role: "INVESTIGATE",
  execution_authority: "NONE",
  candidate_count: 0,
  refresh_in_progress: false,
  refresh_interval_seconds: 120,
  poll_interval_seconds: 3,
  provider_health: [],
  lane_counts: {},
  screen_outcomes: [],
  candidates: [],
  generated_at: "2026-08-24T15:00:00Z",
  discovery_as_of: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <LiveDiscoverPage />
    </MemoryRouter>,
  );
}

describe("LiveDiscoverPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(mixedPayload) } as Response),
      ),
    );
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it("renders read-only live discover with canary link and no refresh control", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
    expect(screen.queryByRole("button", { name: "Refresh all screens" })).not.toBeInTheDocument();
  });
});

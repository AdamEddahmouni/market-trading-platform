import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { canarySnapshot } from "../live-now/liveNowTestFixtures";
import { LivePortfolioPage } from "./LivePortfolioPage";

describe("LivePortfolioPage", () => {
  it("renders broker-observed portfolio read-only", () => {
    render(
      <MemoryRouter>
        <LivePortfolioPage
          state="ready"
          snapshot={canarySnapshot({
            live_positions: [{ instrument_id: "AAPL", quantity: 3, side: "LONG" }],
            open_broker_orders: [{ order_id: "ord-42" }],
            block_reasons: ["HUMAN_CONFIRMATION_REQUIRED"],
          })}
          reconciliation={{
            reconciliation_health: "CLEAN",
            local_open_orders: ["local-1"],
            ambiguous_states: [],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Live Portfolio" })).toBeInTheDocument();
    expect(screen.getAllByText("AAPL").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ord-42").length).toBeGreaterThan(0);
    expect(screen.getByText(/Live blocked: Human confirmation required/i)).toBeInTheDocument();
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open live canary" })[0]).toHaveAttribute(
      "href",
      "/live-canary",
    );
  });

  it("degrades independently when snapshot is unavailable", () => {
    render(
      <MemoryRouter>
        <LivePortfolioPage state="error" />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Broker portfolio snapshot unavailable/i)).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ContextResponse } from "../../api/client";
import { StatusBar } from "./StatusBar";

const baseContext: ContextResponse = {
  as_of_context: {
    mode: "REPLAY",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "NONE",
    execution_authority: "BLOCKED",
    as_of_time: "2026-08-30T12:00:00Z",
    timezone: "America/New_York",
  },
  capability_states: [],
  quality_summary: { state: "PASS" },
  scope_symbols: ["BIYA"],
};

function renderBar(
  props: Partial<React.ComponentProps<typeof StatusBar>> = {},
  context: ContextResponse | undefined = baseContext,
) {
  return render(
    <MemoryRouter>
      <StatusBar mode="DEMO" context={context} contextState="ready" {...props} />
    </MemoryRouter>,
  );
}

describe("StatusBar", () => {
  it("renders the mode as a human sentence in the session environment region", () => {
    renderBar();
    const region = screen.getByRole("region", { name: "Session environment" });
    expect(region).toHaveTextContent("Demo replay — trading disabled");
    expect(region).toHaveTextContent("No trading authority");
  });

  it("renders data health and scope in human terms", () => {
    renderBar();
    expect(screen.getByTestId("imp-status-bar-health")).toHaveTextContent("Mark data current");
    expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("BIYA");
  });

  it("keeps raw enums behind the technical details disclosure", () => {
    renderBar();
    const details = screen.getByText("Technical details");
    expect(details).toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Session environment" });
    expect(region).toHaveTextContent("FIXTURE_REPLAY");
    expect(region).toHaveTextContent("2026-08-30T12:00:00Z");
  });

  it("carries the instrument scope in the details popover so narrow layouts lose nothing", () => {
    renderBar();
    const details = screen.getByText("Technical details").closest("details");
    expect(details).toHaveTextContent("Scope");
    expect(details).toHaveTextContent("BIYA");
  });

  it("warns with a caution banner when backend context is unavailable", () => {
    render(
      <MemoryRouter>
        <StatusBar mode="PAPER" context={undefined} contextState="error" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/Backend context unavailable/);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute(
      "href",
      "/control#control-authority",
    );
  });

  it("alerts critically when UI mode and backend context disagree", () => {
    render(
      <MemoryRouter>
        <StatusBar mode="LIVE" context={baseContext} contextState="ready" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/UI mode selection does not change/);
  });

  it("shows a verifying note while context loads", () => {
    render(
      <MemoryRouter>
        <StatusBar mode="DEMO" context={undefined} contextState="loading" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/Verifying backend context/);
  });

  it("renders live data mode with provider", () => {
    renderBar(
      { mode: "LIVE" },
      {
        ...baseContext,
        as_of_context: {
          ...baseContext.as_of_context,
          mode: "LIVE",
          data_mode: "LIVE_OBSERVATIONAL",
          data_provider: "MOOMOO",
        },
      },
    );
    const region = screen.getByRole("region", { name: "Session environment" });
    expect(region).toHaveTextContent("Live market data — read-only, execution locked.");
    expect(region).toHaveTextContent("Live market data · MOOMOO");
  });

  it("shows CONTROLLED REPLAY banner when backend marks controlled_replay", () => {
    renderBar(
      {},
      {
        ...baseContext,
        controlled_replay: true,
        not_live_market_data: true,
        as_of_context: {
          ...baseContext.as_of_context,
          controlled_replay: true,
          evidence_class: "CONTROLLED_REPLAY",
          not_live_market_data: true,
        },
      },
    );
    expect(screen.getByText(/CONTROLLED REPLAY/)).toBeInTheDocument();
    expect(screen.getByText(/NOT LIVE MARKET DATA/)).toBeInTheDocument();
    expect(screen.getByTestId("imp-status-bar")).toHaveAttribute("data-controlled-replay", "true");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { OpportunitySnapshot } from "../../api/schemas";
import { OpportunityFusionBlock } from "./OpportunityFusionBlock";

const rankedSnapshot: OpportunitySnapshot = {
  available: true,
  status: "RANKED",
  outcome: "RANKED",
  symbol: "NVDA",
  as_of_time: "2026-07-21T19:45:00.000000000Z",
  fused_net_ev: 309.648336,
  fusion: {
    fused_net_ev: 309.648336,
    occurrence_weight: 0.999983,
    liquidity_factor: 1.0,
    gross_ev_before_weights: 309.6536,
    template: "long_call_atm",
    squeeze_aligned: true,
  },
  probability: {
    available: true,
    squeeze_occurrence_probability: 0.658361,
    squeeze_hazard_probability: 0.999983,
    squeeze_state: "ACTIVE_SQUEEZE",
    source_ref: "cross_lane:probability",
  },
  payoff: {
    available: true,
    expected_pnl: 326.3,
    net_expected_pnl: 309.6536,
    template: "long_call_atm",
    source_ref: "options:strategy",
  },
  costs: {
    available: true,
    friction_cost: 16.6464,
    source_ref: "options:payoff",
  },
  liquidity: {
    available: true,
    gates_passed: true,
    cvd_confidence: 0.85,
    source_ref: "cross_lane:liquidity",
  },
  model_version: "shared_opportunity_v1",
  method: "CROSS_LANE_FUSION_V1",
  replay_hash: "345a3dec7a82c6345f52523f265b57c4e935d4ed41a0b7f46fb349decde89d7e",
  disclaimer: "Cross-lane EV fusion — research decomposition, not a trade recommendation.",
};

const noEdgeSnapshot: OpportunitySnapshot = {
  available: true,
  status: "NO_ACTIONABLE_EDGE",
  outcome: "NO_ACTIONABLE_EDGE",
  reason: "FUSED_NET_EV_NOT_POSITIVE",
  fused_net_ev: -12.5,
  fusion: {
    fused_net_ev: -12.5,
    occurrence_weight: 1.0,
    liquidity_factor: 1.0,
    gross_ev_before_weights: -12.5,
    template: "long_put_atm",
    squeeze_aligned: false,
  },
  probability: { available: true, source_ref: "cross_lane:probability" },
  payoff: { available: true, source_ref: "options:strategy" },
  costs: { available: true, source_ref: "options:payoff" },
  liquidity: { available: true, gates_passed: true, source_ref: "cross_lane:liquidity" },
};

const unavailableSnapshot: OpportunitySnapshot = {
  available: false,
  status: "UNAVAILABLE",
  outcome: "UNAVAILABLE",
  reason: "PAYOFF_UNAVAILABLE",
};

describe("OpportunityFusionBlock", () => {
  it("renders nothing when snapshot is missing", () => {
    const { container } = render(<OpportunityFusionBlock snapshot={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows ranked fusion decomposition", () => {
    render(<OpportunityFusionBlock snapshot={rankedSnapshot} />);
    expect(screen.getByText("Cross-lane opportunity fusion (SHARED P4)")).toBeInTheDocument();
    expect(screen.getByText("RANKED")).toBeInTheDocument();
    expect(screen.getAllByText("309.648336").length).toBeGreaterThan(0);
    expect(screen.getAllByText("long_call_atm").length).toBeGreaterThan(0);
    expect(screen.getByText(/research decomposition/i)).toBeInTheDocument();
  });

  it("shows no actionable edge outcome", () => {
    render(<OpportunityFusionBlock snapshot={noEdgeSnapshot} />);
    expect(screen.getByText("NO_ACTIONABLE_EDGE")).toBeInTheDocument();
    expect(screen.getAllByText("-12.5").length).toBeGreaterThan(0);
  });

  it("shows unavailable state", () => {
    render(<OpportunityFusionBlock snapshot={unavailableSnapshot} />);
    expect(screen.getByText("UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("PAYOFF_UNAVAILABLE")).toBeInTheDocument();
  });

  it("wires trace buttons to onExplain", () => {
    const onExplain = vi.fn();
    render(<OpportunityFusionBlock snapshot={rankedSnapshot} onExplain={onExplain} />);
    fireEvent.click(screen.getByRole("button", { name: "Trace probability" }));
    expect(onExplain).toHaveBeenCalledWith("cross_lane:probability");
  });
});

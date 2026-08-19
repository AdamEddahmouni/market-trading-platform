import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StateTransitionBlock } from "./StateTransitionBlock";
import { frozenSqueezeFixture } from "./fixtures";

describe("StateTransitionBlock", () => {
  it("renders transition log when transitions are present", () => {
    render(<StateTransitionBlock squeeze={frozenSqueezeFixture} />);
    expect(screen.getByText("Snapshot log")).toBeInTheDocument();
    expect(screen.getByText("INITIAL → WATCH")).toBeInTheDocument();
    expect(screen.getByText("at FROZEN")).toBeInTheDocument();
    expect(screen.getByText("FROZEN_DEMO aggregate load")).toBeInTheDocument();
    expect(screen.getByText("frozen_snapshot")).toBeInTheDocument();
  });

  it("renders causal transition stream with changed_at", () => {
    render(<StateTransitionBlock squeeze={frozenSqueezeFixture} />);
    expect(screen.getByText("Causal state transitions")).toBeInTheDocument();
    expect(screen.getByText("IGNITION_WATCH → LIVE_CONFIRMATION")).toBeInTheDocument();
    expect(screen.getByText("live_order_flow_confirmation")).toBeInTheDocument();
    expect(screen.getByText("at 2026-08-18T14:10:00.000000000Z")).toBeInTheDocument();
  });

  it("hides causal log when state_transitions is empty", () => {
    const squeeze = {
      ...frozenSqueezeFixture,
      state_machine: {
        ...frozenSqueezeFixture.state_machine!,
        state_transitions: [],
        transition_count: 0,
      },
    };
    render(<StateTransitionBlock squeeze={squeeze} />);
    expect(screen.queryByText("Causal state transitions")).not.toBeInTheDocument();
  });

  it("falls back to banner when state_machine is missing", () => {
    const squeeze = { ...frozenSqueezeFixture, state_machine: undefined, ignition_state: "UNKNOWN" };
    render(<StateTransitionBlock squeeze={squeeze} />);
    expect(screen.getByText("STATE: UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("Freshness: FROZEN")).toBeInTheDocument();
    expect(screen.queryByText("Snapshot log")).not.toBeInTheDocument();
  });
});

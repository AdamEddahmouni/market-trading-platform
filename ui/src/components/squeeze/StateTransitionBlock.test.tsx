import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StateTransitionBlock } from "./StateTransitionBlock";
import { frozenSqueezeFixture } from "./fixtures";

describe("StateTransitionBlock", () => {
  it("renders transition log when transitions are present", () => {
    render(<StateTransitionBlock squeeze={frozenSqueezeFixture} />);
    expect(screen.getByText("Transition log")).toBeInTheDocument();
    expect(screen.getByText("INITIAL → WATCH")).toBeInTheDocument();
    expect(screen.getByText("at FROZEN")).toBeInTheDocument();
    expect(screen.getByText("FROZEN_DEMO aggregate load")).toBeInTheDocument();
    expect(screen.getByText("frozen_snapshot")).toBeInTheDocument();
  });

  it("falls back to banner when state_machine is missing", () => {
    const squeeze = { ...frozenSqueezeFixture, state_machine: undefined, ignition_state: "UNKNOWN" };
    render(<StateTransitionBlock squeeze={squeeze} />);
    expect(screen.getByText("STATE: UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("Freshness: FROZEN")).toBeInTheDocument();
    expect(screen.queryByText("Transition log")).not.toBeInTheDocument();
  });
});

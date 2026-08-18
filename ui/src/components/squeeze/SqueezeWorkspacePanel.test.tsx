import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SqueezeWorkspacePanel } from "./SqueezeWorkspacePanel";
import { frozenSqueezeFixture } from "./fixtures";

describe("SqueezeWorkspacePanel", () => {
  it("shows loading state", () => {
    render(<SqueezeWorkspacePanel instrumentId="AVTX" squeeze={null} loading />);
    expect(screen.getByText("Loading squeeze evidence…")).toBeInTheDocument();
  });

  it("shows unavailable reason when donor bridge is down", () => {
    render(
      <SqueezeWorkspacePanel
        instrumentId="AVTX"
        squeeze={{
          ...frozenSqueezeFixture,
          available: false,
          reason: "Donor squeeze bridge unavailable.",
        }}
      />,
    );
    expect(screen.getByText("Donor squeeze bridge unavailable.")).toBeInTheDocument();
  });

  it("renders rules table and ignition cards when available", () => {
    render(<SqueezeWorkspacePanel instrumentId="AVTX" squeeze={frozenSqueezeFixture} />);
    expect(screen.getByText("Phase 3A rules (1)")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Rule" })).toBeInTheDocument();
    expect(screen.getAllByText("FLOAT_MAXIMUM").length).toBeGreaterThan(0);
    expect(screen.getByText("SI / Float")).toBeInTheDocument();
    expect(screen.getByText("Options")).toBeInTheDocument();
  });

  it("wires explain and inspect actions", () => {
    const onExplain = vi.fn();
    const onInspect = vi.fn();
    render(
      <SqueezeWorkspacePanel
        instrumentId="AVTX"
        squeeze={frozenSqueezeFixture}
        onExplain={onExplain}
        onInspect={onInspect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Explain state" }));
    expect(onExplain).toHaveBeenCalledWith("explain:squeeze:AVTX");
    fireEvent.click(screen.getByRole("button", { name: "Open Inspector" }));
    expect(onInspect).toHaveBeenCalledWith("inspect:squeeze:AVTX");
  });
});

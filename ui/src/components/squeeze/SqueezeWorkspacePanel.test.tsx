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

  it("renders catalyst attention block when ss p2 fields present", () => {
    render(
      <SqueezeWorkspacePanel
        instrumentId="BOXL"
        squeeze={{
          ...frozenSqueezeFixture,
          symbol: "BOXL",
          catalyst_strength: {
            symbol: "BOXL",
            catalyst_id: "catalyst:boxl:1",
            strength: 72,
            catalyst_type: "earnings_beat",
            publication_state: "PUBLISHED",
          },
          attention_feature: {
            symbol: "BOXL",
            attention_score: 37.5,
            attention_acceleration: 8.5,
            publication_state: "PUBLISHED",
          },
          information_value: 78.38,
          reflexive_impact: 0,
        }}
      />,
    );
    expect(screen.getByText("Catalyst & attention")).toBeInTheDocument();
    expect(screen.getByText(/earnings_beat/)).toBeInTheDocument();
  });

  it("renders author influence and accuracy as separate fields", () => {
    render(
      <SqueezeWorkspacePanel
        instrumentId="BOXL"
        squeeze={{
          ...frozenSqueezeFixture,
          symbol: "BOXL",
          catalyst_strength: {
            symbol: "BOXL",
            catalyst_id: "catalyst:boxl:1",
            strength: 72,
            catalyst_type: "earnings_beat",
            publication_state: "PUBLISHED",
          },
          author_intelligence_available: true,
          author_handle: "boxl_hype",
          author_influence_score: 1,
          author_accuracy_score: 0,
        }}
      />,
    );
    expect(screen.getByText("Author influence")).toBeInTheDocument();
    expect(screen.getByText("Author accuracy")).toBeInTheDocument();
    expect(screen.getByText(/@boxl_hype/)).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});

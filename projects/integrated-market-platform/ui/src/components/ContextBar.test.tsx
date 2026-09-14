import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContextBar } from "./ContextBar";

const baseContext = {
  as_of_context: {
    mode: "PAPER" as const,
    data_mode: "FIXTURE_REPLAY" as const,
    execution_mode: "INTERNAL_SIMULATION" as const,
    execution_authority: "PAPER_ONLY" as const,
    as_of_time: "2024-01-02T15:00:00Z",
    timezone: "America/New_York",
  },
  capability_states: [],
  quality_summary: { state: "PASS" },
  scope_symbols: ["BIYA"],
};

describe("ContextBar", () => {
  it("renders quality segment", () => {
    render(<ContextBar context={baseContext} />);
    expect(screen.getByText("QUALITY")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
  });
});

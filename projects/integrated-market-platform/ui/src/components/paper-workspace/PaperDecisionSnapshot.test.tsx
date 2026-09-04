import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildPaperDecisionSnapshot } from "./buildPaperDecisionSnapshot";
import { PaperDecisionSnapshotPanel } from "./PaperDecisionSnapshot";

describe("PaperDecisionSnapshotPanel", () => {
  it("renders supports, contradicts, unclear, and gaps", () => {
    const snapshot = buildPaperDecisionSnapshot(
      {
        instrument: "BIYA",
        as_of_context: {
          mode: "REPLAY",
          data_mode: "FIXTURE_REPLAY",
          execution_mode: "INTERNAL_SIMULATION",
          execution_authority: "PAPER_ONLY",
          as_of_time: "2026-08-31T12:00:00Z",
          timezone: "America/New_York",
        },
        lanes: [
          {
            instrument: "BIYA",
            lane: "SHORT_SQUEEZE",
            evidence_type: "TEST",
            quality: "PASS",
            relevance: "HIGH",
            direction: "POSITIVE",
            summary: "Supportive squeeze evidence",
            freshness_label: "CURRENT",
          },
          {
            instrument: "BIYA",
            lane: "ORDER_FLOW",
            evidence_type: "TEST",
            quality: "PASS",
            relevance: "HIGH",
            direction: "NEGATIVE",
            summary: "Contradictory flow",
            freshness_label: "CURRENT",
          },
        ],
        what_matters_now: [],
        evidence_mix_summary: "MIXED",
        research_context_execution_authority: "RESEARCH_ONLY",
      },
      "ready",
      "squeeze",
    );
    render(<PaperDecisionSnapshotPanel snapshot={snapshot} />);
    expect(screen.getByRole("heading", { name: "Decision snapshot" })).toBeInTheDocument();
    expect(screen.getByText(/Origin:/i)).toBeInTheDocument();
    expect(screen.getByText(/Supportive squeeze evidence/)).toBeInTheDocument();
    expect(screen.getByText(/Contradictory flow/)).toBeInTheDocument();
  });

  it("shows insufficient overall evidence message", () => {
    const snapshot = buildPaperDecisionSnapshot(undefined, "empty", null);
    render(<PaperDecisionSnapshotPanel snapshot={snapshot} />);
    expect(screen.getByText(/insufficient for a directional conclusion/i)).toBeInTheDocument();
  });
});

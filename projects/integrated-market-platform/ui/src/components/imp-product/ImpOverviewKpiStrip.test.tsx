import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImpOverviewKpiStrip } from "./ImpOverviewKpiStrip";
import type { OverviewKpiCell } from "./impOverviewMetrics";

const cells: OverviewKpiCell[] = [
  { id: "queue-data", label: "Opportunity feed", value: "Ready", tone: "live" },
  { id: "actionable", label: "Actionable now", value: "2", detail: "of 3 ranked", tone: "live" },
  { id: "attention", label: "Needs review", value: "1", detail: "1 urgent — act now", tone: "caution" },
  { id: "degraded", label: "Stale or degraded", value: "0" },
];

describe("ImpOverviewKpiStrip", () => {
  it("renders semantic tones with icon + text, never color alone", () => {
    render(<ImpOverviewKpiStrip cells={cells} />);
    const region = screen.getByRole("region", { name: "Decision metrics" });
    const cards = region.querySelectorAll(".imp-overview-kpi-card");
    expect(cards).toHaveLength(4);
    expect(cards[0]).toHaveAttribute("data-tone", "live");
    expect(cards[2]).toHaveAttribute("data-tone", "caution");
    // Neutral default when no tone is provided.
    expect(cards[3]).toHaveAttribute("data-tone", "neutral");
    // Every card pairs its tone with an icon glyph and text value.
    for (const card of cards) {
      expect(card.querySelector(".imp-overview-kpi-icon")).not.toBeNull();
      expect(card.querySelector(".imp-overview-kpi-value")?.textContent).toBeTruthy();
    }
    expect(cards[1]).toHaveTextContent("of 3 ranked");
  });

  it("keeps cells non-interactive (orientation, not actions)", () => {
    render(<ImpOverviewKpiStrip cells={cells} />);
    const region = screen.getByRole("region", { name: "Decision metrics" });
    expect(region.querySelector("button")).toBeNull();
    expect(region.querySelector("a")).toBeNull();
  });
});

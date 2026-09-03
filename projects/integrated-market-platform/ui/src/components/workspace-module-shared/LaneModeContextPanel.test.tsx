import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LaneModeContextPanel } from "./LaneModeContextPanel";

describe("LaneModeContextPanel", () => {
  it("renders paper decision hint and sections", () => {
    render(
      <MemoryRouter>
        <LaneModeContextPanel
          mode="PAPER"
          moduleId="squeeze"
          instrumentId="BIYA"
          queryState={{ phase: "ready" }}
          content={{
            headline: "Squeeze simulation readiness",
            summary: "Ignition WATCH",
            decisionHint: "neutral",
            sections: [
              { title: "Decision readiness", body: "Mixed evidence", bullets: ["Confirm manually"] },
            ],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Squeeze simulation readiness" })).toBeInTheDocument();
    expect(screen.getByText(/Simulation hint: Mixed/i)).toBeInTheDocument();
    expect(screen.getByText("Confirm manually")).toBeInTheDocument();
  });
});

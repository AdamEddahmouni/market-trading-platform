import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscoverMixedScreenerSection, DiscoverRankedQueueSection } from "./DiscoverPageSections";

describe("DiscoverPageSections", () => {
  it("labels ranked queue as opportunity contract", () => {
    render(
      <DiscoverRankedQueueSection>
        <p>queue</p>
      </DiscoverRankedQueueSection>,
    );
    expect(screen.getByRole("heading", { name: "Ranked opportunity queue" })).toBeInTheDocument();
    expect(screen.getAllByText("Opportunity contract").length).toBeGreaterThanOrEqual(1);
  });

  it("labels mixed screener as investigation-only boundary", () => {
    render(
      <DiscoverMixedScreenerSection>
        <p>screener</p>
      </DiscoverMixedScreenerSection>,
    );
    expect(screen.getByRole("heading", { name: "Mixed discovery desk" })).toBeInTheDocument();
    expect(screen.getByText("Investigation only")).toBeInTheDocument();
    expect(screen.getByText(/not ranked opportunity summaries/i)).toBeInTheDocument();
  });
});

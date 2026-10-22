import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PaperPortfolioResponseSchema } from "../../api/schemas";
import { experimentPortfolio } from "../paper-portfolio/paperExperimentFixture";
import { PaperExperimentContextStrip } from "./PaperExperimentContextStrip";

describe("PaperExperimentContextStrip", () => {
  it("shows which experiment account the ticket would touch before submit", () => {
    render(
      <PaperExperimentContextStrip
        portfolio={PaperPortfolioResponseSchema.parse(experimentPortfolio())}
        instrumentId="AAPL"
      />,
    );
    const strip = screen.getByTestId("experiment-context");
    expect(strip).toHaveTextContent("Experiment: OCT1-09 Paper experiment · simulated capital");
    expect(strip).toHaveTextContent("Initial$100,000.00");
    expect(strip).toHaveTextContent("Cash$79,200.00");
    expect(strip).toHaveTextContent("Buying power$79,200.00");
    expect(strip).toHaveTextContent("Current positionLONG 60 sh of AAPL");
    expect(strip).toHaveTextContent("Live capital: No");
    expect(strip).toHaveTextContent("SIMULATED PAPER EXECUTION");
  });

  it("reports a flat instrument and a closed experiment", () => {
    const payload = experimentPortfolio();
    payload.experiment.status = "CLOSED";
    render(
      <PaperExperimentContextStrip portfolio={PaperPortfolioResponseSchema.parse(payload)} instrumentId="MSFT" />,
    );
    expect(screen.getByTestId("experiment-context")).toHaveTextContent("Flat in MSFT");
    expect(screen.getByRole("status")).toHaveTextContent("This experiment is closed. New orders are refused.");
  });

  it("says when no experiment is active so the operator knows which account is used", () => {
    const payload = { ...experimentPortfolio(), experiment: null };
    render(
      <PaperExperimentContextStrip portfolio={PaperPortfolioResponseSchema.parse(payload)} instrumentId="AAPL" />,
    );
    expect(screen.getByTestId("experiment-context-none")).toHaveTextContent("No active Paper experiment.");
  });
});

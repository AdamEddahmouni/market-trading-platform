import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildPaperHandoffModel } from "./buildPaperHandoffModel";
import { PaperHandoffPanel } from "./PaperHandoffPanel";

describe("PaperHandoffPanel", () => {
  it("renders lane handoff with placeholder warning", () => {
    const handoff = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "lane:squeeze",
      },
      "BIYA",
    );
    render(<PaperHandoffPanel handoff={handoff} evidenceAsOf="2026-08-31T12:00:00Z" />);
    expect(screen.getByRole("heading", { name: /Handoff from Short Squeeze/i })).toBeInTheDocument();
    expect(screen.getByText(/placeholder, not a recommendation/i)).toBeInTheDocument();
    expect(screen.getByText(/lane:squeeze/)).toBeInTheDocument();
  });

  it("renders attention handoff with source context", () => {
    const handoff = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "attention-biya",
        sourceContext: {
          headline: "BIYA setup",
          tier: 1,
          reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
          source_time: 1_700_000_000_000,
        },
      },
      "BIYA",
    );
    render(<PaperHandoffPanel handoff={handoff} />);
    expect(screen.getByRole("heading", { name: "Attention handoff" })).toBeInTheDocument();
    expect(screen.getByText("BIYA setup")).toBeInTheDocument();
    expect(screen.getByText(/PRICE_VOLUME/)).toBeInTheDocument();
    expect(screen.getByText(/Attention surfaced:/)).toBeInTheDocument();
    expect(screen.getAllByText(/attention-biya/).length).toBeGreaterThan(0);
  });

  it("renders unknown lane state", () => {
    const handoff = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "lane:unknown",
      },
      "BIYA",
    );
    render(<PaperHandoffPanel handoff={handoff} />);
    expect(screen.getByRole("heading", { name: /Unknown lane handoff/i })).toBeInTheDocument();
  });

  it("renders nothing without handoff", () => {
    const handoff = buildPaperHandoffModel(undefined, "BIYA");
    const { container } = render(<PaperHandoffPanel handoff={handoff} />);
    expect(container).toBeEmptyDOMElement();
  });
});

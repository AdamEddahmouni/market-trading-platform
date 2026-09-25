import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PaperOrderAcknowledgementPanel } from "./PaperOrderAcknowledgementPanel";
import type { PaperOrderAcknowledgement } from "./paperOrderAcknowledgement";

const baseAck: PaperOrderAcknowledgement = {
  orderId: "order-abc-123456",
  intentId: "intent-xyz-789012",
  fillId: null,
  duplicate: false,
  decision: "ALLOW",
  orderState: "WORKING",
  side: "BUY",
  quantity: 1,
  instrumentId: "AAPL",
  orderLabel: "BUY × 1 MARKET",
  correlationId: "opportunity:opp-1",
  opportunityId: "opp-1",
  provenanceLabel: "Watched opportunity opp-1",
  orderHistoryHref: "/portfolio#portfolio-order-history",
  hasDurableOrder: true,
  fillObserved: false,
};

describe("PaperOrderAcknowledgementPanel", () => {
  it("links to Order history and preserves opportunity provenance", () => {
    render(
      <MemoryRouter>
        <PaperOrderAcknowledgementPanel model={baseAck} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("paper-order-acknowledgement")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Paper order accepted" })).toBeInTheDocument();
    expect(screen.getByTestId("paper-order-ack-provenance")).toHaveTextContent(/Watched opportunity/i);
    expect(screen.getByTestId("paper-order-ack-opportunity")).toBeInTheDocument();
    const history = screen.getByTestId("paper-order-ack-history-link");
    expect(history).toHaveAttribute("href", "/portfolio#portfolio-order-history");
    expect(screen.getByText(/Not observed on this acknowledgement/i)).toBeInTheDocument();
  });

  it("exposes execution-trace action when ids are present", () => {
    const onViewTrace = vi.fn();
    render(
      <MemoryRouter>
        <PaperOrderAcknowledgementPanel model={baseAck} onViewTrace={onViewTrace} />
      </MemoryRouter>,
    );
    screen.getByRole("button", { name: /View execution trace/i }).click();
    expect(onViewTrace).toHaveBeenCalledTimes(1);
  });

  it("reports a rejected ledger order without implying acceptance or a working fill", () => {
    render(
      <MemoryRouter>
        <PaperOrderAcknowledgementPanel model={{ ...baseAck, orderState: "REJECTED" }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Paper order rejected" })).toBeInTheDocument();
    expect(screen.getByText(/Submission was recorded by the Paper ledger, but the order was rejected/)).toBeInTheDocument();
    expect(screen.getByText(/No fill was recorded/)).toBeInTheDocument();
  });
});

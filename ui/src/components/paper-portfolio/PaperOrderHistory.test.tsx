import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { paperPortfolio } from "../paper-now/paperNowTestFixtures";
import { PaperOrderHistory } from "./PaperOrderHistory";

const historyOrders = [
  {
    order_id: "order-attention",
    intent_id: "intent-attention",
    client_order_id: "client-attention",
    correlation_id: "attention-biya",
    decision_source_snapshot: {
      source_type: "paper_command_attention",
      source_id: "attention-biya",
      headline: "Short interest elevated into catalyst window",
      tier: 1,
      reasons: [{ code: "SI", label: "Short interest elevated" }],
      source_time: 1_700_000_000_000,
    },
    side: "BUY",
    desired_quantity: 2,
    order_type: "MARKET",
    state: "FILLED",
    symbol: "BIYA",
    submitted_sequence: 3,
  },
  {
    order_id: "order-lane",
    intent_id: "intent-lane",
    client_order_id: "client-lane",
    correlation_id: "lane:order-flow",
    side: "SELL",
    desired_quantity: 1,
    order_type: "MARKET",
    state: "REJECTED",
    reason_codes: ["RISK_MAX_ORDER"],
    symbol: "NVDA",
    submitted_sequence: 2,
  },
];

let mockHistoryOrders = historyOrders;

vi.mock("../../api/hooks", async () => {
  const actual = await vi.importActual<typeof import("../../api/hooks")>("../../api/hooks");
  return {
    ...actual,
    usePaperOrderHistoryInfiniteQuery: () => ({
      data: {
        pages: [
          {
            orders: mockHistoryOrders,
            fills: [],
            next_cursor: null,
            total_count: mockHistoryOrders.length,
            page_size: 25,
          },
        ],
      },
      isLoading: false,
      isError: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    }),
  };
});

describe("PaperOrderHistory", () => {
  it("renders provenance badges, status, trace action, and rejection reason", () => {
    mockHistoryOrders = historyOrders;
    const onViewTrace = vi.fn();
    const data = paperPortfolio({ orders: historyOrders });

    render(<PaperOrderHistory data={data} onViewTrace={onViewTrace} />);

    expect(screen.getByText("PAPER COMMAND")).toBeInTheDocument();
    expect(screen.getByText("ORDER FLOW")).toBeInTheDocument();
    expect(screen.getByText("Short interest elevated into catalyst window")).toBeInTheDocument();
    expect(screen.getByText("order-flow")).toBeInTheDocument();
    expect(screen.getByText("Rejected", { selector: ".paper-order-status" })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /View trace for/i })[0]!);
    expect(onViewTrace).toHaveBeenCalledWith("intent-attention", "order-attention");

    fireEvent.click(screen.getAllByRole("button", { name: "Details" })[0]!);
    expect(screen.getAllByText("attention-biya").length).toBeGreaterThan(0);
    expect(screen.getByText("Source context at decision handoff")).toBeInTheDocument();
    expect(screen.getByText("Attention surfaced")).toBeInTheDocument();
    expect(
      screen.getByText("Historical source-time context — not current market or workspace evidence."),
    ).toBeInTheDocument();
    expect(screen.getByText("SI")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Details" }));
    expect(screen.getByText("RISK_MAX_ORDER")).toBeInTheDocument();
  });

  it("shows empty state when no orders exist", () => {
    mockHistoryOrders = [];
    render(<PaperOrderHistory data={paperPortfolio({ orders: [] })} />);
    expect(screen.getByText(/No simulated orders yet/i)).toBeInTheDocument();
  });
});

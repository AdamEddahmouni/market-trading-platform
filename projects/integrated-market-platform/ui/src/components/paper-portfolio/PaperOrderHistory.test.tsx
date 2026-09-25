import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
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

function renderHistory(node: ReactElement) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperOrderHistory", () => {
  it("renders status in the table and keeps provenance behind row selection and detail", () => {
    mockHistoryOrders = historyOrders;
    const onViewTrace = vi.fn();
    const data = paperPortfolio({ orders: historyOrders });

    renderHistory(<PaperOrderHistory data={data} onViewTrace={onViewTrace} />);

    // Default table answers "what happened", not "why".
    expect(screen.getByText("Filled", { selector: ".paper-order-status" })).toBeInTheDocument();
    expect(screen.getByText("Rejected", { selector: ".paper-order-status" })).toBeInTheDocument();
    expect(screen.queryByText("PAPER COMMAND")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /View trace/ })).not.toBeInTheDocument();

    // Selecting a row exposes its legitimate next actions and provenance.
    fireEvent.click(screen.getAllByRole("rowheader")[0]!);
    expect(screen.getByText("PAPER COMMAND")).toBeInTheDocument();
    expect(screen.getByText("Short interest elevated into catalyst window")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View trace" }));
    expect(onViewTrace).toHaveBeenCalledWith("intent-attention", "order-attention");

    // Full decision provenance stays in the disclosure.
    fireEvent.click(screen.getAllByRole("button", { name: "Details" })[0]!);
    expect(screen.getAllByText("attention-biya").length).toBeGreaterThan(0);
    expect(screen.getByText("Source context at decision handoff")).toBeInTheDocument();
    expect(screen.getByText("Attention surfaced")).toBeInTheDocument();
    expect(
      screen.getByText(/Historical source-time context/),
    ).toBeInTheDocument();
    expect(screen.getByText("SI")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Details" })[1]!);
    expect(screen.getByText("RISK_MAX_ORDER")).toBeInTheDocument();
  });

  it("hands each order's own instrument to Workspace", () => {
    mockHistoryOrders = historyOrders;
    renderHistory(<PaperOrderHistory data={paperPortfolio({ orders: historyOrders })} />);
    expect(screen.getByRole("link", { name: "Open BIYA Workspace" })).toHaveAttribute(
      "href",
      "/workspace/BIYA",
    );
    expect(screen.getByRole("link", { name: "Open NVDA Workspace" })).toHaveAttribute(
      "href",
      "/workspace/NVDA",
    );
  });

  it("shows empty state when no orders exist", () => {
    mockHistoryOrders = [];
    renderHistory(<PaperOrderHistory data={paperPortfolio({ orders: [] })} />);
    expect(screen.getByText(/No simulated orders yet/i)).toBeInTheDocument();
  });
});

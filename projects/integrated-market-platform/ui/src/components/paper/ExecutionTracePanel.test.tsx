import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExecutionTracePanel } from "./ExecutionTracePanel";

let traceSteps: Array<Record<string, unknown>> = [];

vi.mock("../../api/hooks", () => ({
  usePaperTraceQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      trace: {
        correlation: { intent_id: "intent-1", order_id: "order-1", fill_id: null },
        steps: traceSteps,
        execution_provider: "INTERNAL",
        execution_mode: "INTERNAL_SIMULATION",
        execution_authority: "PAPER_ONLY",
        market_data_provider: "INTERNAL",
        broker_order_submitted: false,
        broker_order_id: null,
      },
    },
  }),
}));

function renderPanel(intentId = "intent-1") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ExecutionTracePanel intentId={intentId} onClose={() => undefined} />
    </QueryClientProvider>,
  );
}

describe("ExecutionTracePanel", () => {
  beforeEach(() => {
    traceSteps = [
      {
        stage: "ORDER_INTENT",
        sequence: 1,
        summary: "BUY 1 BIYA",
        metadata: {
          correlation_id: "attention-biya",
          client_order_id: "client-1",
          decision_source_snapshot: {
            source_type: "paper_command_attention",
            source_id: "attention-biya",
            headline: "Short interest elevated into catalyst window",
            tier: 1,
            reasons: [{ code: "SI", label: "Short interest elevated" }],
          },
        },
      },
    ];
  });

  it("shows decision provenance and persisted source context once", () => {
    renderPanel();
    expect(screen.getByText("Decision provenance")).toBeInTheDocument();
    expect(screen.getByText("Paper Command attention attention-biya")).toBeInTheDocument();
    expect(screen.getByText("Decision correlation")).toBeInTheDocument();
    expect(screen.getAllByText("attention-biya").length).toBeGreaterThan(0);
    expect(screen.getByText("Source context at decision handoff")).toBeInTheDocument();
    expect(screen.getAllByText("Short interest elevated into catalyst window").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Source context at decision handoff")).toHaveLength(1);
  });

  it("hides decision provenance for manual client-order correlation", () => {
    traceSteps = [
      {
        stage: "ORDER_INTENT",
        sequence: 1,
        summary: "BUY 1 BIYA",
        metadata: {
          intent: {
            correlation_id: "client-manual",
            client_order_id: "client-manual",
          },
        },
      },
    ];
    renderPanel("intent-manual");
    expect(screen.queryByText("Decision provenance")).not.toBeInTheDocument();
    expect(screen.getAllByText("client-manual").length).toBeGreaterThan(0);
  });
});

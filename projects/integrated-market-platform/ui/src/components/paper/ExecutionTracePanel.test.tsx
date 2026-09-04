import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExecutionTracePanel } from "./ExecutionTracePanel";

let traceSteps: Array<Record<string, unknown>> = [];
let traceStages: Array<Record<string, unknown>> | undefined;

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
        stages: traceStages,
        settlement: traceStages
          ? { portfolio: "SETTLED", prediction: "PENDING" }
          : undefined,
        completeness: traceStages
          ? { state: "COMPLETE", missing_stages: [] }
          : undefined,
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
    traceStages = undefined;
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

  it("renders the complete unified strategy lifecycle", () => {
    traceStages = [
      { stage: "OPPORTUNITY", status: "AVAILABLE", ids: { opportunity_id: "opp-1" } },
      { stage: "ALLOCATION", status: "SELECTED", ids: { allocation_decision_id: "alloc-1" } },
      { stage: "RISK_DECISION", status: "APPROVE", ids: { risk_decision_id: "risk-1" } },
      { stage: "ORDER_READY", status: "READY", ids: { order_ready_id: "ready-1" } },
      { stage: "PAPER_FILL", status: "FILLED", ids: { fill_id: "fill-1" } },
      { stage: "PORTFOLIO_SETTLEMENT", status: "SETTLED", ids: { event_id: "event-1" } },
      { stage: "PREDICTION_SETTLEMENT", status: "PENDING", ids: { prediction_ledger_entry_id: "pred-1" } },
      { stage: "ATTRIBUTION", status: "MATERIALIZED", ids: { attribution_id: "attr-1" } },
    ];
    renderPanel();
    expect(screen.getByText("Trace completeness")).toBeInTheDocument();
    expect(screen.getByText("Portfolio settlement")).toBeInTheDocument();
    expect(screen.getByText("ORDER_READY: READY (ready-1)")).toBeInTheDocument();
    expect(screen.getByText("ATTRIBUTION: MATERIALIZED (attr-1)")).toBeInTheDocument();
  });
});

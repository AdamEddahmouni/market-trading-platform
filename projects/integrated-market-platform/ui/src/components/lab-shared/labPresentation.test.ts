import { describe, expect, it } from "vitest";
import {
  buildLabWorkflowCards,
  costFillAssumptionFacts,
  datasetProvenanceFacts,
  experimentStatusFacts,
  labHasRunnableBackendWorkflow,
  strategyIdentityFacts,
} from "./labPresentation";

const models = {
  authority_boundary: "READ_ONLY_RESEARCH",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: { model_family: "naive_last_value.v1", alignment_type: "FORECAST_MOMENTUM" },
  strategy_spec: {},
  dataset_manifest: {},
  preregistration: {},
  interpretation_summary: { abstention_count: 1, signal_count: 2, total_at_cutoff: 3 },
  interpretations: [],
};

const simulation = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  epistemic_class: "SIMULATION_PROJECTION",
  ledger_summary: { cash_minor: 1, position_shares: 0, realized_pnl_minor: 0, entry_count: 4 },
  risk_decisions: [{}],
  fills: [{}, {}],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
};

describe("labPresentation", () => {
  it("marks every backend workflow as not runnable", () => {
    expect(labHasRunnableBackendWorkflow()).toBe(false);
    const cards = buildLabWorkflowCards({ models, simulation });
    expect(cards.filter((card) => card.availability !== "unsupported").every((card) => !card.runnable)).toBe(
      true,
    );
  });

  it("presents validation and simulation as inspectable with Research handoff", () => {
    const cards = buildLabWorkflowCards({ models, simulation });
    const validation = cards.find((card) => card.id === "validation");
    const sim = cards.find((card) => card.id === "simulation");
    expect(validation?.availabilityLabel).toBe("Read-only");
    expect(validation?.researchHref).toBe("/research/validation");
    expect(validation?.statusDetail).toMatch(/2 signals \/ 1 abstention/);
    expect(sim?.limitation).toMatch(/not forward-test evidence/i);
    expect(sim?.researchHref).toBe("/research/simulation");
  });

  it("keeps FTEP, hypotheses, and benchmark comparison as explicit UNKNOWN gaps", () => {
    const cards = buildLabWorkflowCards({});
    const ftep = cards.find((card) => card.id === "ftep");
    const hypothesis = cards.find((card) => card.id === "hypothesis");
    const benchmark = cards.find((card) => card.id === "benchmark");
    expect(ftep?.availability).toBe("unsupported");
    expect(ftep?.availabilityLabel).toBe("Not yet available");
    expect(ftep?.statusLabel).toBe("UNKNOWN");
    expect(ftep?.statusDetail).toMatch(/forward-tests/);
    expect(hypothesis?.availability).toBe("unsupported");
    expect(benchmark?.availability).toBe("unsupported");
    expect(benchmark?.statusLabel).toBe("UNKNOWN");
    expect(benchmark?.limitation).toMatch(/Do not infer a benchmark/i);
  });

  it("does not invent a run ledger when payloads are missing", () => {
    const cards = buildLabWorkflowCards({ modelsError: true, simulationError: true });
    expect(cards.find((card) => card.id === "validation")?.statusLabel).toBe("UNAVAILABLE");
    expect(cards.find((card) => card.id === "simulation")?.statusLabel).toBe("UNAVAILABLE");
    expect(cards.some((card) => /queued|running|progress/i.test(card.statusLabel))).toBe(false);
  });

  it("keeps experiment IDs, benchmarks, and missing provenance as UNKNOWN", () => {
    const status = experimentStatusFacts({ models, simulation });
    expect(status.find((row) => row.label === "Experiment ID")?.value).toBe("UNKNOWN");
    expect(status.find((row) => row.label === "Benchmark comparison")?.value).toBe("UNKNOWN");
    expect(status.find((row) => row.label === "Validation experiment status")?.value).toBe(
      "Snapshot at cutoff",
    );

    const identity = strategyIdentityFacts(models as never);
    expect(identity.find((row) => row.label === "Strategy identity hash")?.value).toBe("UNKNOWN");

    const provenance = datasetProvenanceFacts(models as never);
    expect(provenance.find((row) => row.label === "Instrument")?.value).toBe("UNKNOWN");

    const costs = costFillAssumptionFacts(simulation as never);
    expect(costs.find((row) => row.label === "Slippage assumption")?.value).toBe("UNKNOWN");
    expect(costs.find((row) => row.label === "Fill-price realism metric")?.value).toBe("UNKNOWN");
  });
});

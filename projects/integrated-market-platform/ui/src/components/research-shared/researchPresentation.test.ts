import { describe, expect, it } from "vitest";
import type {
  ResearchAnalyticsResponse,
  ResearchModelsResponse,
  ResearchSimulationResponse,
} from "../../api/schemas";
import {
  buildEvidenceAvailability,
  buildResearchSynthesis,
  countConflictingInterpretations,
  formatResearchTime,
  interpretationHasConflict,
  listFindingSources,
  presentAbstentionReason,
  presentCheckStatus,
  presentFindingAvailability,
  presentPreregistration,
  RESEARCH_FINDINGS,
  buildClaimNavigation,
  claimHopsForFinding,
  sectionClaimHops,
  researchPanel,
} from "./researchPresentation";

const analyticsFixture = {
  as_of_context: { mode: "REPLAY", as_of_time: "2026-09-15T13:30:00Z", timezone: "UTC" },
  authority_boundary: "READ_ONLY_RESEARCH_VISUALIZATION",
  disclaimer: "Research only.",
  epistemic_class: "RESEARCH_PROJECTION",
  panels: {
    attention_tiers: {
      available: true,
      provenance: { source: "replay attention feed" },
      series: [{ label: "1", count: 4 }],
    },
    squeeze_outcomes: {
      available: false,
      reason: "donor bridge unavailable",
      provenance: { source: "short-squeeze-project" },
      series: [],
    },
    squeeze_historical_cohort: {
      available: true,
      provenance: { source: "cohort fixture" },
      series: [],
    },
    strategy_outcomes: {
      available: true,
      provenance: { source: "phase 5R walk-forward + phase 6 strategy" },
      series: [
        { label: "signal", count: 12 },
        { label: "abstention", count: 3 },
      ],
      signal_timeline: [{ observation_index: 1, cumulative_signals: 1, outcome: "signal" }],
    },
    risk_decisions: {
      available: true,
      provenance: { source: "phase 7 risk simulation" },
      series: [{ label: "APPROVE", count: 9 }],
    },
  },
} as unknown as ResearchAnalyticsResponse;

const modelsFixture = {
  authority_boundary: "READ_ONLY_RESEARCH",
  epistemic_class: "RESEARCH_PROJECTION",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: { model_family: "naive_last_value.v1" },
  strategy_spec: {},
  dataset_manifest: {},
  preregistration: {},
  interpretation_summary: { abstention_count: 3, signal_count: 12, total_at_cutoff: 15 },
  interpretations: [],
} as unknown as ResearchModelsResponse;

const simulationFixture = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  epistemic_class: "SIMULATION_PROJECTION",
  ledger_summary: { cash_minor: 100000, position_shares: 0, realized_pnl_minor: 0, entry_count: 7 },
  risk_decisions: [{ decision: "APPROVE" }],
  fills: [],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
} as unknown as ResearchSimulationResponse;

describe("researchPresentation findings", () => {
  it("describes all five analytics panels as distinct findings", () => {
    expect(RESEARCH_FINDINGS).toHaveLength(5);
    const keys = RESEARCH_FINDINGS.map((finding) => finding.key);
    expect(new Set(keys).size).toBe(5);
    for (const finding of RESEARCH_FINDINGS) {
      expect(finding.claim.length).toBeGreaterThan(0);
      expect(finding.whyItMatters.length).toBeGreaterThan(0);
      expect(finding.evidenceClass.length).toBeGreaterThan(0);
      expect(finding.anchor).toMatch(/^research-finding-/);
    }
  });

  it("reads panels defensively", () => {
    expect(researchPanel(analyticsFixture, "strategy_outcomes")?.available).toBe(true);
    expect(researchPanel(undefined, "strategy_outcomes")).toBeUndefined();
  });

  it("presents availability honestly: unavailable with reason, empty, available", () => {
    const unavailable = presentFindingAvailability(
      researchPanel(analyticsFixture, "squeeze_outcomes"),
    );
    expect(unavailable.label).toBe("Unavailable");
    expect(unavailable.tone).toBe("caution");
    expect(unavailable.detail).toContain("donor bridge unavailable");

    const empty = presentFindingAvailability(
      researchPanel(analyticsFixture, "squeeze_historical_cohort"),
    );
    expect(empty.label).toBe("Empty");
    expect(empty.tone).toBe("neutral");

    const available = presentFindingAvailability(
      researchPanel(analyticsFixture, "strategy_outcomes"),
    );
    expect(available.label).toBe("Available");
    expect(available.tone).toBe("research");

    const missing = presentFindingAvailability(undefined);
    expect(missing.label).toBe("Unavailable");
  });
});

describe("researchPresentation vocabulary", () => {
  it("humanizes abstention reason codes including conflicting evidence", () => {
    expect(presentAbstentionReason("ABSTAIN_CONFLICTING_EVIDENCE").label).toBe(
      "Conflicting evidence",
    );
    expect(presentAbstentionReason("ABSTAIN_NO_PREREGISTRATION").label).toBe("No preregistration");
    const unknown = presentAbstentionReason("ABSTAIN_SOMETHING_NEW");
    expect(unknown.label).toBe("Abstain something new");
    expect(unknown.raw).toBe("ABSTAIN_SOMETHING_NEW");
  });

  it("presents preregistration states", () => {
    expect(presentPreregistration("PASS")).toMatchObject({ tone: "live", label: "Preregistered" });
    expect(presentPreregistration("FAIL")).toMatchObject({
      tone: "critical",
      label: "Preregistration failed",
    });
    expect(presentPreregistration("ABSENT")).toMatchObject({
      tone: "neutral",
      label: "Not preregistered",
    });
    expect(presentPreregistration(undefined)).toMatchObject({
      tone: "neutral",
      label: "Not reported",
    });
  });

  it("presents check statuses without overloading preregistration labels", () => {
    expect(presentCheckStatus("PASS")).toMatchObject({ tone: "live", label: "Pass" });
    expect(presentCheckStatus("FAIL")).toMatchObject({ tone: "critical", label: "Failed" });
    expect(presentCheckStatus(null)).toMatchObject({ tone: "neutral", label: "Not reported" });
  });

  it("formats research epoch timestamps and rejects garbage", () => {
    // Epoch nanoseconds (≈1.7e18) resolve to a human absolute time.
    expect(formatResearchTime(1_757_500_000_000_000_000)).toMatch(/Sep \d+/);
    expect(formatResearchTime("2026-09-15T13:30:00Z")).toMatch(/Sep/);
    expect(formatResearchTime("not-a-time")).toBeNull();
    expect(formatResearchTime(undefined)).toBeNull();
  });
});

describe("buildResearchSynthesis", () => {
  it("derives sentences only from payload fields", () => {
    const lines = buildResearchSynthesis({
      analytics: analyticsFixture,
      models: modelsFixture,
      simulation: simulationFixture,
    });
    const text = lines.map((line) => line.text).join("\n");
    expect(text).toContain("12 signals and 3 abstentions across 15 observations");
    expect(text).toContain("5 walk-forward folds");
    expect(text).toContain("4 of 5 evidence findings have data");
    expect(text).toContain("Squeeze donor bridge unavailable: donor bridge unavailable");
    expect(text).toContain("7 ledger entries");
    expect(text).toContain("reconciliation pass");
  });

  it("omits lines for missing sources instead of guessing", () => {
    expect(buildResearchSynthesis({})).toHaveLength(0);
    const lines = buildResearchSynthesis({ models: modelsFixture });
    expect(lines).toHaveLength(1);
    expect(lines[0].id).toBe("validation");
  });

  it("reports contract-backed conflicting-evidence abstentions only", () => {
    const withConflict = {
      ...modelsFixture,
      interpretations: [
        { abstention_reason_codes: ["ABSTAIN_CONFLICTING_EVIDENCE"] },
        { abstention_reason_codes: ["ABSTAIN_NO_PREREGISTRATION"] },
      ],
    } as unknown as ResearchModelsResponse;
    const text = buildResearchSynthesis({ models: withConflict })
      .map((line) => line.text)
      .join("\n");
    expect(text).toContain("1 observation abstained because the backend reported conflicting evidence");
    expect(countConflictingInterpretations(withConflict)).toBe(1);
    expect(interpretationHasConflict({ abstention_reason_codes: ["ABSTAIN_NO_PREREGISTRATION"] })).toBe(
      false,
    );
  });
});

describe("buildEvidenceAvailability", () => {
  it("maps findings plus validation and simulation rows with deep links", () => {
    const rows = buildEvidenceAvailability({
      analytics: analyticsFixture,
      models: modelsFixture,
      simulation: simulationFixture,
    });
    expect(rows).toHaveLength(7);
    const squeeze = rows.find((row) => row.id === "squeeze_outcomes");
    expect(squeeze).toMatchObject({ stateLabel: "Unavailable", tone: "caution" });
    expect(squeeze?.href).toBe("/research/evidence?panel=squeeze_outcomes");
    const validation = rows.find((row) => row.id === "validation");
    expect(validation?.detail).toContain("5 walk-forward folds");
    expect(validation?.detail).toContain("Preregistered");
    const simulation = rows.find((row) => row.id === "simulation");
    expect(simulation?.stateLabel).toBe("Available");
  });

  it("marks validation and simulation unavailable when payloads are missing", () => {
    const rows = buildEvidenceAvailability({ analytics: analyticsFixture });
    expect(rows.find((row) => row.id === "validation")?.stateLabel).toBe("Unavailable");
    expect(rows.find((row) => row.id === "simulation")?.stateLabel).toBe("Unavailable");
  });
});

describe("listFindingSources", () => {
  it("groups provenance sources without inventing a catalog", () => {
    const rows = listFindingSources(analyticsFixture);
    expect(rows.some((row) => row.source === "short-squeeze-project")).toBe(true);
    expect(rows.find((row) => row.source === "short-squeeze-project")?.findings).toContain(
      "Squeeze screener outcomes",
    );
  });
});

describe("buildClaimNavigation", () => {
  it("exposes eight hops and does not invent hypothesis or FTEP objects", () => {
    const nodes = buildClaimNavigation(
      {
        analytics: analyticsFixture,
        models: modelsFixture,
        simulation: simulationFixture,
      },
      "DEMO",
    );
    expect(nodes.map((node) => node.key)).toEqual([
      "source",
      "hypothesis",
      "strategy",
      "experiment",
      "evidence",
      "contradiction",
      "implementation",
      "forward-test",
    ]);
    const hypothesis = nodes.find((node) => node.key === "hypothesis");
    expect(hypothesis?.statusLabel).toBe("NOT_EXPOSED");
    expect(hypothesis?.href).toBe("/research/validation#research-interpretations-heading");
    const forward = nodes.find((node) => node.key === "forward-test");
    expect(forward?.statusLabel).toBe("NOT_EXPOSED");
    expect(forward?.href).toBeNull();
    const experiment = nodes.find((node) => node.key === "experiment");
    expect(experiment?.evidenceClass).toMatch(/not prospective forward-test/i);
    expect(experiment?.href).toBe("/research/simulation");
  });

  it("links Paper forward-test to Workspace without fetching campaign state", () => {
    const nodes = buildClaimNavigation({ models: modelsFixture }, "PAPER");
    const forward = nodes.find((node) => node.key === "forward-test");
    expect(forward?.href).toBe("/workspace");
    expect(forward?.destinationKind).toBe("related");
    expect(forward?.detail).toMatch(/not a forward test/i);
  });

  it("reports only contract-backed conflicts", () => {
    const withConflict = {
      ...modelsFixture,
      interpretations: [{ abstention_reason_codes: ["ABSTAIN_CONFLICTING_EVIDENCE"] }],
    } as unknown as ResearchModelsResponse;
    const nodes = buildClaimNavigation({ models: withConflict }, "DEMO");
    const contradiction = nodes.find((node) => node.key === "contradiction");
    expect(contradiction?.href).toBe("/research/validation?conflict=1");
    expect(contradiction?.statusLabel).toMatch(/1 contract-backed conflict/);
  });
});

describe("claim hops", () => {
  it("keeps finding hops static so Evidence does not extra-fetch", () => {
    const hops = claimHopsForFinding("strategy_outcomes", "DEMO");
    expect(hops.map((hop) => hop.key)).toEqual([
      "strategy",
      "contradiction",
      "experiment",
      "implementation",
      "forward-test",
    ]);
    expect(hops.find((hop) => hop.key === "forward-test")?.href).toBeNull();
  });

  it("routes simulation hops away from treating the run as a forward test", () => {
    const hops = sectionClaimHops("simulation", "PAPER");
    expect(hops.find((hop) => hop.key === "forward-test")?.note).toMatch(/not a prospective forward test/i);
    expect(hops.find((hop) => hop.key === "forward-test")?.href).toBe("/workspace");
  });
});

/**
 * Lab workbench presentation model (UIR-01H).
 *
 * Lab answers how we test or investigate a claim. Research answers what the
 * evidence means. This module only translates existing GET contracts
 * (`/research/models`, `/research/simulation`) and the local Chart Lab into
 * operator language. No run IDs, progress, or mutations are invented.
 * Contract authority: docs/ui-redesign-v2/lab-contract-map.md.
 */
import type {
  AsOfContext,
  OperatorDiagnostics,
  ResearchModelsResponse,
  ResearchSimulationResponse,
} from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { preferItem9OperatorTruth } from "../control/consumeOperatorTruth";
import {
  diagnosticsGovernance,
  diagnosticsRuntimeSection,
  formatItem9CorpusProgress,
  mapItem9CorpusProgressTruth,
} from "../control/operatorDiagnosticsPresentation";
import { presentCheckStatus, presentPreregistration } from "../research-shared/researchPresentation";

export type LabSectionKey = "overview" | "validation" | "simulation" | "chart-lab";

export const LAB_UNKNOWN = "UNKNOWN";
export const LAB_UNAVAILABLE = "UNAVAILABLE";

export const LAB_SECTION_TABS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/lab", label: "Overview", end: true },
  { to: "/lab/validation", label: "Validation" },
  { to: "/lab/simulation", label: "Simulation" },
  { to: "/lab/chart-lab", label: "Chart Lab" },
];

export type WorkflowAvailability = "inspectable" | "local-tooling" | "unsupported";

export type LabWorkflowCard = {
  id: "validation" | "simulation" | "chart-lab" | "ftep" | "hypothesis" | "benchmark";
  title: string;
  purpose: string;
  tests: string;
  availability: WorkflowAvailability;
  availabilityLabel: string;
  runnable: boolean;
  runnableDetail: string;
  statusLabel: string;
  statusTone: SemanticTone;
  statusDetail: string;
  inputs: string;
  evidence: string;
  researchHref: string | null;
  labHref: string | null;
  limitation: string;
};

export type LabFact = {
  label: string;
  value: string;
  copyable?: boolean;
  note?: string;
};

export type LabEvidenceClassRow = {
  workflow: string;
  evidenceClass: string;
  notThis: string;
};

export function recordField(
  record: Record<string, unknown> | undefined,
  key: string,
): string | null {
  if (!record) return null;
  const value = record[key];
  if (value == null) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

export function recordedOrUnknown(value: string | null | undefined): string {
  if (value == null || value === "") return LAB_UNKNOWN;
  return value;
}

export function modelFamily(models?: ResearchModelsResponse | null): string {
  return recordedOrUnknown(recordField(models?.model_summary, "model_family"));
}

export function modelAlignment(models?: ResearchModelsResponse | null): string {
  return recordedOrUnknown(
    recordField(models?.model_summary, "alignment_type") ??
      recordField(models?.strategy_spec, "alignment_type"),
  );
}

export function strategyIdentityHash(models?: ResearchModelsResponse | null): string | null {
  return (
    recordField(models?.model_summary, "strategy_identity_hash") ??
    recordField(models?.strategy_spec, "strategy_identity_hash")
  );
}

export function datasetFingerprint(models?: ResearchModelsResponse | null): string | null {
  return (
    recordField(models?.model_summary, "dataset_fingerprint") ??
    recordField(models?.dataset_manifest, "dataset_fingerprint")
  );
}

export function validationResultSummary(models?: ResearchModelsResponse | null): string {
  if (!models) return "Validation result is UNAVAILABLE.";
  const summary = models.interpretation_summary;
  return (
    `${summary.signal_count} ${summary.signal_count === 1 ? "signal" : "signals"} / ` +
    `${summary.abstention_count} ${summary.abstention_count === 1 ? "abstention" : "abstentions"} ` +
    `across ${summary.total_at_cutoff} ${summary.total_at_cutoff === 1 ? "observation" : "observations"} ` +
    `at cutoff · ${models.walk_forward_fold_count} walk-forward ` +
    `${models.walk_forward_fold_count === 1 ? "fold" : "folds"}.`
  );
}

export function simulationResultSummary(simulation?: ResearchSimulationResponse | null): string {
  if (!simulation) return "Simulation result is UNAVAILABLE.";
  const ledger = simulation.ledger_summary;
  const reconciliation = presentCheckStatus(simulation.reconciliation?.status as string | undefined);
  return (
    `${ledger.entry_count} ledger ${ledger.entry_count === 1 ? "entry" : "entries"} · ` +
    `${simulation.risk_decisions.length} risk ` +
    `${simulation.risk_decisions.length === 1 ? "decision" : "decisions"} · ` +
    `${simulation.fills.length} ${simulation.fills.length === 1 ? "fill" : "fills"} · ` +
    `reconciliation ${reconciliation.label.toLowerCase()}.`
  );
}

function asOfFacts(asOf?: AsOfContext): LabFact[] {
  return [
    { label: "As-of time", value: recordedOrUnknown(asOf?.as_of_time) },
    { label: "As-of provenance", value: recordedOrUnknown(asOf?.as_of_provenance) },
    {
      label: "Replay session",
      value: recordedOrUnknown(asOf?.replay_session_id),
      copyable: Boolean(asOf?.replay_session_id),
    },
    { label: "Context mode", value: recordedOrUnknown(asOf?.mode) },
    { label: "Data mode", value: recordedOrUnknown(asOf?.data_mode) },
    { label: "Data provider", value: recordedOrUnknown(asOf?.data_provider) },
    {
      label: "Execution authority (context)",
      value: recordedOrUnknown(asOf?.execution_authority),
      note: "as_of_context only. Lab does not grant Paper or Live execution.",
    },
  ];
}

export function experimentStatusFacts(input: {
  models?: ResearchModelsResponse | null;
  modelsError?: boolean;
  simulation?: ResearchSimulationResponse | null;
  simulationError?: boolean;
}): LabFact[] {
  const validationStatus = input.modelsError
    ? LAB_UNAVAILABLE
    : input.models
      ? "Snapshot at cutoff"
      : "No snapshot loaded";
  const simulationStatus = input.simulationError
    ? LAB_UNAVAILABLE
    : input.simulation
      ? "Snapshot at cutoff"
      : "No snapshot loaded";
  return [
    {
      label: "Experiment ID",
      value: LAB_UNKNOWN,
      note: "No experiment resource exists on the UI API. Lab will not mint one.",
    },
    {
      label: "Run ID / queue / progress",
      value: LAB_UNKNOWN,
      note: "GET projections are a single current snapshot, not a run ledger.",
    },
    { label: "Validation experiment status", value: validationStatus },
    { label: "Simulation experiment status", value: simulationStatus },
    {
      label: "Benchmark comparison",
      value: LAB_UNKNOWN,
      note: "Not present on GET /research/models or GET /research/simulation.",
    },
  ];
}

export function labAuthorityHonestyFacts(input: {
  diagnostics?: OperatorDiagnostics | null;
  diagnosticsError?: boolean;
}): LabFact[] {
  const full30: LabFact = {
    label: "Full30 / IBP campaign",
    value: "Not a Lab workflow",
    note: "Lab does not execute Full30, calibration fitting, or Live orders.",
  };

  if (input.diagnosticsError) {
    return [
      { label: "Item 9 distinct admitted RTH dates", value: LAB_UNAVAILABLE },
      { label: "Item 9 date-gate truth class", value: LAB_UNAVAILABLE },
      { label: "Item 9 calibration", value: LAB_UNAVAILABLE },
      { label: "Live real-money execution", value: LAB_UNAVAILABLE },
      full30,
    ];
  }

  if (!input.diagnostics) {
    return [
      {
        label: "Item 9 distinct admitted RTH dates",
        value: LAB_UNKNOWN,
        note: "GET /operator/diagnostics is not loaded on this snapshot.",
      },
      { label: "Item 9 date-gate truth class", value: LAB_UNKNOWN },
      { label: "Item 9 calibration", value: LAB_UNKNOWN },
      { label: "Live real-money execution", value: LAB_UNKNOWN },
      full30,
    ];
  }

  const runtime = diagnosticsRuntimeSection(input.diagnostics);
  const governance = diagnosticsGovernance(input.diagnostics);
  const corpus = formatItem9CorpusProgress(runtime?.item9_corpus_status);
  const localTruth = mapItem9CorpusProgressTruth(
    runtime?.item9_corpus_status,
    corpus.distinctRthDates,
  );
  const corpusTruth = preferItem9OperatorTruth(input.diagnostics, "item9-corpus", localTruth);
  const liveLabel = !governance
    ? LAB_UNKNOWN
    : governance.live_execution_env
      ? "Live execution env flag is on — still governed."
      : "Live OFF";

  return [
    {
      label: "Item 9 distinct admitted RTH dates",
      value: recordedOrUnknown(corpus.distinctRthDates),
      note: corpus.receiptScopeNote,
    },
    {
      label: "Item 9 date-gate truth class",
      value: corpusTruth,
      note:
        corpusTruth === "IDLE"
          ? "Incomplete admitted dates are IDLE, not DEGRADED, and not a Lab defect to fix."
          : "Canonical operator_truth / local Item 9 mapping. Lab does not upgrade this class.",
    },
    {
      label: "Item 9 calibration",
      value: recordedOrUnknown(corpus.calibrationLabel),
      note: `${corpus.calibrationForbidden}. Walk-forward and simulation snapshots are not calibration.`,
    },
    {
      label: "Live real-money execution",
      value: liveLabel,
      note: "Observational Live data mode is not Live experiment authority and does not place broker orders.",
    },
    full30,
  ];
}

export function labAuthorityHonestyWarnings(input: {
  diagnostics?: OperatorDiagnostics | null;
  diagnosticsError?: boolean;
}): string[] {
  const facts = labAuthorityHonestyFacts(input);
  const dates = facts.find((row) => row.label === "Item 9 distinct admitted RTH dates")?.value;
  const calibration = facts.find((row) => row.label === "Item 9 calibration")?.value;
  return [
    "Lab is controlled research/validation inspection. It does not grant trade authority or production readiness.",
    `Item 9 fill-calibration corpus is ${dates ?? LAB_UNKNOWN} and ${calibration ?? LAB_UNKNOWN}. Simulated fills on this page are not calibrated Paper fills.`,
    "Incomplete Item 9 dates stay IDLE — not DEGRADED and not a reason to invent a Run or Calibrate control.",
    "Full30 is not a Lab action. Do not treat the absence of a run button as a campaign result.",
  ];
}

export function strategyIdentityFacts(models?: ResearchModelsResponse | null): LabFact[] {
  const hash = strategyIdentityHash(models);
  return [
    { label: "Model family", value: modelFamily(models) },
    { label: "Alignment", value: modelAlignment(models) },
    {
      label: "Strategy identity hash",
      value: recordedOrUnknown(hash),
      copyable: Boolean(hash),
    },
    {
      label: "Walk-forward folds",
      value: models ? String(models.walk_forward_fold_count) : LAB_UNKNOWN,
    },
    {
      label: "Preregistration",
      value: recordedOrUnknown(models?.preregistration_status),
    },
  ];
}

export function datasetProvenanceFacts(models?: ResearchModelsResponse | null): LabFact[] {
  const manifest = models?.dataset_manifest;
  const summary = models?.model_summary;
  const fingerprint = datasetFingerprint(models);
  return [
    {
      label: "Dataset fingerprint",
      value: recordedOrUnknown(fingerprint),
      copyable: Boolean(fingerprint),
    },
    {
      label: "Horizon (ns)",
      value: recordedOrUnknown(
        recordField(manifest, "horizon_ns") ?? recordField(summary, "target_horizon_ns"),
      ),
    },
    {
      label: "Instrument",
      value: recordedOrUnknown(
        recordField(manifest, "instrument_id") ?? recordField(manifest, "symbol"),
      ),
    },
    {
      label: "Source / provider",
      value: recordedOrUnknown(
        recordField(manifest, "source") ?? recordField(manifest, "provider_id"),
      ),
    },
    {
      label: "Corpus / dataset ID",
      value: recordedOrUnknown(
        recordField(manifest, "corpus_id") ?? recordField(manifest, "dataset_id"),
      ),
    },
  ];
}

const HIDDEN_PARAMETER_KEYS = new Set(["strategy_identity_hash", "dataset_fingerprint"]);

export function recordedParameterFacts(models?: ResearchModelsResponse | null): LabFact[] {
  const spec = models?.strategy_spec ?? {};
  const facts: LabFact[] = [];
  for (const [key, value] of Object.entries(spec)) {
    if (HIDDEN_PARAMETER_KEYS.has(key)) continue;
    if (value == null || value === "") {
      facts.push({ label: key, value: LAB_UNKNOWN });
      continue;
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      facts.push({ label: key, value: String(value) });
    }
  }
  if (facts.length === 0) {
    facts.push({
      label: "Recorded parameters",
      value: LAB_UNKNOWN,
      note: "No scalar strategy_spec fields are on this snapshot. Lab has no parameter editor.",
    });
  }
  return facts;
}

export function evidenceLineageFacts(payload?: {
  epistemic_class?: string;
  authority_boundary: string;
  as_of_context?: AsOfContext;
  disclaimer?: string;
}): LabFact[] {
  if (!payload) {
    return [{ label: "Evidence lineage", value: LAB_UNAVAILABLE }];
  }
  return [
    { label: "Epistemic class", value: recordedOrUnknown(payload.epistemic_class) },
    { label: "Authority boundary", value: recordedOrUnknown(payload.authority_boundary) },
    ...asOfFacts(payload.as_of_context),
  ];
}

export function capabilityStateFacts(
  states?: ReadonlyArray<{ capability_id: string; state: string; reason?: string }>,
): LabFact[] {
  if (!states || states.length === 0) {
    return [
      {
        label: "Capability states",
        value: LAB_UNKNOWN,
        note: "None were projected on this payload.",
      },
    ];
  }
  return states.map((row) => ({
    label: row.capability_id,
    value: row.state,
    note: row.reason,
  }));
}

export function reproducibilityFacts(input: {
  models?: ResearchModelsResponse | null;
  simulation?: ResearchSimulationResponse | null;
}): LabFact[] {
  const asOf = input.models?.as_of_context ?? input.simulation?.as_of_context;
  const hash = strategyIdentityHash(input.models);
  const fingerprint = datasetFingerprint(input.models);
  return [
    ...asOfFacts(asOf),
    {
      label: "Strategy identity hash",
      value: recordedOrUnknown(hash),
      copyable: Boolean(hash),
    },
    {
      label: "Dataset fingerprint",
      value: recordedOrUnknown(fingerprint),
      copyable: Boolean(fingerprint),
    },
    {
      label: "Risk policy",
      value: recordedOrUnknown(input.simulation?.risk_policy_id ?? null),
      copyable: Boolean(input.simulation?.risk_policy_id),
    },
    {
      label: "Re-run from Lab",
      value: "Not supported",
      note: "Refreshing re-reads the same projection. There is no POST that reproduces a different cutoff.",
    },
  ];
}

export function costFillAssumptionFacts(simulation?: ResearchSimulationResponse | null): LabFact[] {
  if (!simulation) {
    return [{ label: "Cost / fill assumptions", value: LAB_UNAVAILABLE }];
  }
  const fillAudit = simulation.fill_audit;
  const ledger = simulation.ledger_summary as Record<string, unknown>;
  const cost =
    recordField(fillAudit, "cost_sensitivity_status") ??
    recordField(fillAudit, "cost_sensitivity_v4_status");
  const realism =
    recordField(fillAudit, "fill_price_realism_status") ??
    recordField(fillAudit, "fill_realism_status") ??
    recordField(fillAudit, "fill_price_realism");
  return [
    {
      label: "Fill model",
      value: simulation.disclaimer?.toLowerCase().includes("bar-conservative")
        ? "Bar-conservative (disclaimer)"
        : LAB_UNKNOWN,
      note: "Taken from the projection disclaimer. Not a calibrated live fill model.",
    },
    {
      label: "Fill-price realism metric",
      value: recordedOrUnknown(realism),
      note: "fill_audit.status is an audit check, not this metric.",
    },
    {
      label: "Slippage assumption",
      value: recordedOrUnknown(
        recordField(fillAudit, "slippage") ?? recordField(ledger, "slippage"),
      ),
    },
    {
      label: "Commission / fees",
      value: recordedOrUnknown(
        recordField(fillAudit, "commission") ??
          recordField(fillAudit, "fees") ??
          recordField(ledger, "commission"),
      ),
    },
    {
      label: "Cost sensitivity",
      value: recordedOrUnknown(cost),
    },
    {
      label: "Fill audit status",
      value: recordedOrUnknown(recordField(fillAudit, "status")),
      note: "Pass/fail of the fill audit — not proof of market-realistic fills.",
    },
  ];
}

export function labEvidenceClassRows(): LabEvidenceClassRow[] {
  return [
    {
      workflow: "Model validation",
      evidenceClass: "RESEARCH_PROJECTION (retrospective walk-forward)",
      notThis: "Not FTEP, not Paper, not Live, not production readiness.",
    },
    {
      workflow: "Deterministic simulation",
      evidenceClass: "SIMULATION_PROJECTION (bar-conservative replay)",
      notThis: "Not a forward test, not Paper fills, not Live orders.",
    },
    {
      workflow: "Chart Lab",
      evidenceClass: LAB_UNKNOWN,
      notThis: "Local adapter tooling. Not an experiment result.",
    },
    {
      workflow: "FTEP / prospective forward test",
      evidenceClass: LAB_UNKNOWN,
      notThis: "No Lab campaign contract. Do not relabel simulation.",
    },
    {
      workflow: "Benchmark comparison",
      evidenceClass: LAB_UNKNOWN,
      notThis: "No benchmark payload on the current Lab GETs.",
    },
  ];
}

export function validationMethodWarnings(models?: ResearchModelsResponse | null): string[] {
  const warnings = [
    "This is retrospective walk-forward on an admitted fixture. It is not a prospective forward test (FTEP).",
    "This workflow cannot be started, cancelled, or retried from Lab. There is no live run state — only the current projection at cutoff.",
    "A passing walk-forward does not make this an active production strategy or grant execution authority.",
    "Benchmark comparison is UNKNOWN — it is not on this contract.",
  ];
  const status = models?.preregistration_status;
  if (status === "ABSENT") {
    warnings.push("Preregistration is ABSENT.");
  }
  if (status === "FAIL") {
    warnings.push("Preregistration is FAIL.");
  }
  if (models && models.interpretations.length === 0) {
    warnings.push("No interpretation rows fall inside the current replay window.");
  }
  if (models?.as_of_context?.mode === "LIVE") {
    warnings.push(
      "as_of_context.mode is LIVE data context, not Live experiment authority.",
    );
  }
  return warnings;
}

export function simulationMethodWarnings(simulation?: ResearchSimulationResponse | null): string[] {
  const warnings = [
    "Simulation is not forward-test evidence and not production readiness. This is a deterministic bar-conservative snapshot, not a governed FTEP campaign, and it never places Paper or Live orders.",
    "There is no run-history list — only the current result. Lab cannot start or retry a simulation.",
    "Ledger amounts stay in minor units. Currency is UNKNOWN unless a contract field appears.",
    "Cost, slippage, and fill-realism metrics stay UNKNOWN unless projected on fill_audit.",
    "Do not treat simulated fills as broker fills or as a governed forward test.",
  ];
  if (simulation?.as_of_context?.mode === "LIVE") {
    warnings.push(
      "as_of_context.mode is LIVE data context, not Live experiment authority.",
    );
  }
  return warnings;
}

export function buildLabWorkflowCards(input: {
  models?: ResearchModelsResponse | null;
  modelsError?: boolean;
  simulation?: ResearchSimulationResponse | null;
  simulationError?: boolean;
}): LabWorkflowCard[] {
  const models = input.models;
  const simulation = input.simulation;
  const preregistration = presentPreregistration(models?.preregistration_status);
  const reconciliation = presentCheckStatus(
    simulation?.reconciliation?.status as string | undefined,
  );

  const validationStatus = input.modelsError
    ? {
        statusLabel: LAB_UNAVAILABLE,
        statusTone: "caution" as const,
        statusDetail: "The research models endpoint did not return a usable payload.",
      }
    : models
      ? {
          statusLabel: "Snapshot at cutoff",
          statusTone: "research" as const,
          statusDetail: `${preregistration.label}. ${validationResultSummary(models)}`,
        }
      : {
          statusLabel: "No snapshot loaded",
          statusTone: "neutral" as const,
          statusDetail: "No validation snapshot is loaded for this cutoff.",
        };

  const simulationStatus = input.simulationError
    ? {
        statusLabel: LAB_UNAVAILABLE,
        statusTone: "caution" as const,
        statusDetail: "The research simulation endpoint did not return a usable payload.",
      }
    : simulation
      ? {
          statusLabel: "Snapshot at cutoff",
          statusTone: "paper" as const,
          statusDetail: `${reconciliation.label} reconciliation. ${simulationResultSummary(simulation)}`,
        }
      : {
          statusLabel: "No snapshot loaded",
          statusTone: "neutral" as const,
          statusDetail: "No simulation snapshot is loaded for this cutoff.",
        };

  return [
    {
      id: "validation",
      title: "Model validation",
      purpose: "Inspect the walk-forward validation workflow for the admitted strategy/model.",
      tests: "Whether the frozen strategy produces signals or abstentions on historical observations.",
      availability: "inspectable",
      availabilityLabel: "Read-only",
      runnable: false,
      runnableDetail: "No UI mutation starts validation. The payload is a replay-store projection.",
      ...validationStatus,
      inputs: "Recorded model family, alignment, preregistration, and dataset identity — not operator-editable here.",
      evidence: "Walk-forward interpretation counts and per-observation outcomes (RESEARCH_PROJECTION).",
      researchHref: "/research/validation",
      labHref: "/lab/validation",
      limitation:
        "Retrospective walk-forward on an admitted fixture. Not FTEP, not production readiness, not trade authority.",
    },
    {
      id: "simulation",
      title: "Deterministic simulation",
      purpose: "Inspect the bar-conservative simulation workflow and its current ledger snapshot.",
      tests: "How the risk policy and simulator treated signals inside the replay window.",
      availability: "inspectable",
      availabilityLabel: "Read-only",
      runnable: false,
      runnableDetail: "No UI mutation starts, cancels, or retries a simulation run.",
      ...simulationStatus,
      inputs: "Recorded evaluation ledger, risk policy identity, and disclaimer — no request body is accepted.",
      evidence: "Ledger summary, risk decisions, fills, reconciliation (SIMULATION_PROJECTION).",
      researchHref: "/research/simulation",
      labHref: "/lab/simulation",
      limitation:
        "Simulation is not forward-test evidence and not production readiness. There is no run history list — only the current snapshot.",
    },
    {
      id: "chart-lab",
      title: "Chart adapter playground",
      purpose: "Exercise the Vela chart adapter on a governed synthetic feed.",
      tests: "Adapter rendering and local tick/backfill behavior — not a research claim.",
      availability: "local-tooling",
      availabilityLabel: "Local tooling",
      runnable: false,
      runnableDetail:
        "Tick-sim and backfill change local React state only. They do not create research evidence or call the backend.",
      statusLabel: "Available locally",
      statusTone: "neutral",
      statusDetail: "No backend contract. Results never become Research findings.",
      inputs: "Local synthetic bars and timeframe chosen in the page.",
      evidence: "None. This is tooling, not an experiment result.",
      researchHref: null,
      labHref: "/lab/chart-lab",
      limitation: "Does not produce evidence, validation, simulation, or FTEP output.",
    },
    {
      id: "ftep",
      title: "FTEP campaign",
      purpose: "Govern a prospective forward-test protocol/campaign.",
      tests: "Would test a strategy forward in a governed window — if an operator contract existed.",
      availability: "unsupported",
      availabilityLabel: "Not yet available",
      runnable: false,
      runnableDetail: "No Lab/operator FTEP management contract exists on the UI API.",
      statusLabel: LAB_UNKNOWN,
      statusTone: "neutral",
      statusDetail:
        "Paper `/paper/forward-tests` is account-bound Workspace context, not a Lab campaign manager.",
      inputs: "No Lab inputs.",
      evidence: "None on this surface.",
      researchHref: "/research",
      labHref: null,
      limitation:
        "Do not treat the deterministic simulation snapshot as a forward test.",
    },
    {
      id: "benchmark",
      title: "Benchmark comparison",
      purpose: "Compare the admitted strategy against a declared benchmark.",
      tests: "Would show relative performance only if a benchmark payload existed.",
      availability: "unsupported",
      availabilityLabel: "Not yet available",
      runnable: false,
      runnableDetail: "No benchmark comparison contract is on the Lab UI API.",
      statusLabel: LAB_UNKNOWN,
      statusTone: "neutral",
      statusDetail:
        "Walk-forward counts and simulated P&L are not a benchmark. Lab will not invent a ranking.",
      inputs: "No Lab inputs.",
      evidence: "None on this surface.",
      researchHref: "/research",
      labHref: null,
      limitation: "Do not infer a benchmark from validation counts or simulated ledger P&L.",
    },
    {
      id: "hypothesis",
      title: "Hypothesis objects",
      purpose: "Track a proposed claim through a lifecycle.",
      tests: "Would identify what is proposed, separately from the strategy under test.",
      availability: "unsupported",
      availabilityLabel: "Not yet available",
      runnable: false,
      runnableDetail: "No hypothesis resource exists on the UI API.",
      statusLabel: LAB_UNKNOWN,
      statusTone: "neutral",
      statusDetail: "Closest truth is per-observation interpretation outcomes on validation.",
      inputs: "No Lab inputs.",
      evidence: "None as a first-class object.",
      researchHref: "/research/validation",
      labHref: "/lab/validation",
      limitation: "Lab will not mint fake hypothesis IDs.",
    },
  ];
}

export function labHasRunnableBackendWorkflow(): boolean {
  return false;
}

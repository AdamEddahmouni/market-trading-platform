/**
 * Lab workbench presentation model (UIR-01H).
 *
 * Lab answers how we test or investigate a claim. Research answers what the
 * evidence means. This module only translates existing GET contracts
 * (`/research/models`, `/research/simulation`) and the local Chart Lab into
 * operator language. No run IDs, progress, or mutations are invented.
 * Contract authority: docs/ui-redesign-v2/lab-contract-map.md.
 */
import type { ResearchModelsResponse, ResearchSimulationResponse } from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { presentCheckStatus, presentPreregistration } from "../research-shared/researchPresentation";

export type LabSectionKey = "overview" | "validation" | "simulation" | "chart-lab";

export const LAB_SECTION_TABS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/lab", label: "Overview", end: true },
  { to: "/lab/validation", label: "Validation" },
  { to: "/lab/simulation", label: "Simulation" },
  { to: "/lab/chart-lab", label: "Chart Lab" },
];

export type WorkflowAvailability = "inspectable" | "local-tooling" | "unsupported";

export type LabWorkflowCard = {
  id: "validation" | "simulation" | "chart-lab" | "ftep" | "hypothesis";
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

export function modelFamily(models?: ResearchModelsResponse | null): string {
  return recordField(models?.model_summary, "model_family") ?? "Unavailable";
}

export function modelAlignment(models?: ResearchModelsResponse | null): string {
  return (
    recordField(models?.model_summary, "alignment_type") ??
    recordField(models?.strategy_spec, "alignment_type") ??
    "Unavailable"
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
  if (!models) return "Validation result is unavailable.";
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
  if (!simulation) return "Simulation result is unavailable.";
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
        statusLabel: "Unavailable",
        statusTone: "caution" as const,
        statusDetail: "The research models endpoint did not return a usable payload.",
      }
    : models
      ? {
          statusLabel: "Current result available",
          statusTone: "research" as const,
          statusDetail: `${preregistration.label}. ${validationResultSummary(models)}`,
        }
      : {
          statusLabel: "No result yet",
          statusTone: "neutral" as const,
          statusDetail: "No validation snapshot is loaded for this cutoff.",
        };

  const simulationStatus = input.simulationError
    ? {
        statusLabel: "Unavailable",
        statusTone: "caution" as const,
        statusDetail: "The research simulation endpoint did not return a usable payload.",
      }
    : simulation
      ? {
          statusLabel: "Current snapshot available",
          statusTone: "paper" as const,
          statusDetail: `${reconciliation.label} reconciliation. ${simulationResultSummary(simulation)}`,
        }
      : {
          statusLabel: "No result yet",
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
      statusLabel: "Planned / absent",
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
      id: "hypothesis",
      title: "Hypothesis objects",
      purpose: "Track a proposed claim through a lifecycle.",
      tests: "Would identify what is proposed, separately from the strategy under test.",
      availability: "unsupported",
      availabilityLabel: "Not yet available",
      runnable: false,
      runnableDetail: "No hypothesis resource exists on the UI API.",
      statusLabel: "Planned / absent",
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

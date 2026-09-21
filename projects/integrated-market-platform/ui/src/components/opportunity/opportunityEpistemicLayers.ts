import type { OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";
import {
  collectOpportunityConflicts,
  collectOpportunityProviderLabels,
  collectOpportunityUnknowns,
  readOpportunityFreshnessView,
} from "./opportunityOperatorBrief";

export type EpistemicLayerKey =
  | "observed"
  | "derived"
  | "model_research"
  | "hypothesis"
  | "unknown"
  | "contradiction";

export type EpistemicLayerItem = {
  label: string;
  value: string;
  /** When true, render with model styling — not grounded market fact. */
  nonFactual?: boolean;
};

export type OpportunityEpistemicLayers = Record<EpistemicLayerKey, EpistemicLayerItem[]>;

const LAYER_LABELS: Record<EpistemicLayerKey, string> = {
  observed: "Observed facts",
  derived: "Derived signals",
  model_research: "Model & research outputs",
  hypothesis: "Hypotheses",
  unknown: "Unknowns",
  contradiction: "Contradictions",
};

export function epistemicLayerTitle(key: EpistemicLayerKey): string {
  return LAYER_LABELS[key];
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

function agentEnrichmentMeta(row: OpportunityReviewRow): Record<string, unknown> | undefined {
  const metadata = row.metadata;
  if (!metadata || typeof metadata !== "object") return undefined;
  const agent = (metadata as Record<string, unknown>).agent_enrichment;
  return agent && typeof agent === "object" ? (agent as Record<string, unknown>) : undefined;
}

function collectGroundedFactLines(row: OpportunityReviewRow, evidence?: OpportunityEvidenceResponse | null): EpistemicLayerItem[] {
  const lines: EpistemicLayerItem[] = [];
  const metadata = row.metadata;
  if (metadata && typeof metadata === "object") {
    const record = metadata as Record<string, unknown>;
    const grounded = record.grounded_fact_extraction ?? record.grounded_facts;
    if (grounded && typeof grounded === "object") {
      const g = grounded as Record<string, unknown>;
      if (g.disposition) {
        lines.push({ label: "Grounded fact disposition", value: display(g.disposition) });
      }
      if (g.answer) {
        lines.push({ label: "Grounded fact answer", value: display(g.answer) });
      }
      if (g.grounded_fact_extraction_version) {
        lines.push({
          label: "Extraction version",
          value: display(g.grounded_fact_extraction_version),
        });
      }
    }
  }
  const authority = evidence?.research_artifact_evidence?.authority_class;
  if (authority) {
    lines.push({ label: "Research artifact authority", value: display(authority), nonFactual: true });
  }
  return lines;
}

/**
 * Progressive disclosure layers for opportunity detail. Backend fields only;
 * uncertain model output is never styled as observed fact.
 */
export function buildOpportunityEpistemicLayers(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OpportunityEpistemicLayers {
  const quality = (row.data_quality ?? {}) as Record<string, unknown>;
  const agent = agentEnrichmentMeta(row);

  const providers = collectOpportunityProviderLabels(row, evidence);
  const observed: EpistemicLayerItem[] = [
    { label: "Instrument", value: display(row.instrument_id) },
    { label: "Evidence class", value: display(evidence?.evidence_class ?? row.evidence_class) },
    { label: "Source", value: display(quality.source) },
    {
      label: "Supporting providers",
      value: providers.length ? providers.join(", ") : "UNKNOWN — no provider or source identifiers attached",
    },
    { label: "Primary source status", value: display(quality.status) },
    ...collectGroundedFactLines(row, evidence),
  ];

  const freshness = readOpportunityFreshnessView(row, evidence);
  const derived: EpistemicLayerItem[] = [
    // Headline is IMP summary language — never an observed market fact.
    { label: "Surfaced headline", value: display(row.headline) },
    // Eligibility is platform evaluation/gate state — not a raw observation.
    { label: "Eligibility evaluation", value: display(row.eligibility_state) },
    { label: "Data freshness", value: freshness.operatorAnswer },
    {
      label: "Ranking basis",
      value: display(
        evidence?.ranking_basis ??
          (row as { ranking_basis?: unknown }).ranking_basis ??
          row.ranking_vector?.basis,
      ),
    },
    { label: "Family admission", value: display(evidence?.family_admission_status ?? row.family_admission_status) },
    { label: "Promotion reason", value: display(evidence?.evidence_promotion_reason ?? row.evidence_promotion_reason) },
  ];

  const modelResearch: EpistemicLayerItem[] = [];
  if (agent) {
    modelResearch.push({
      label: "Agent enrichment",
      value: `${display(agent.status)} · count ${display(agent.count)}`,
      nonFactual: true,
    });
  }
  const edge = row.edge_stats_artifact;
  if (edge && typeof edge === "object") {
    const artifact = edge as Record<string, unknown>;
    modelResearch.push({
      label: "Edge stats artifact",
      value: display(artifact.artifact_type ?? artifact.estimate),
      nonFactual: true,
    });
  }
  if (evidence?.research_artifact_evidence?.readiness) {
    modelResearch.push({
      label: "Research artifact readiness",
      value: display(evidence.research_artifact_evidence.readiness),
      nonFactual: true,
    });
  }

  const hypothesis: EpistemicLayerItem[] = [];
  if (row.explanation_ref) {
    hypothesis.push({ label: "Explain ref", value: display(row.explanation_ref), nonFactual: true });
  }

  const unknown: EpistemicLayerItem[] = collectOpportunityUnknowns(row, evidence).map((field) => ({
    label: "Unavailable field",
    value: display(field),
  }));
  if (!unknown.length) {
    unknown.push({
      label: "Contract gaps",
      value: "UNKNOWN — no unavailable_fields or missing ranking inputs attached",
    });
  }

  const contradiction: EpistemicLayerItem[] = collectOpportunityConflicts(row, evidence).map((line) => ({
    label: "Conflict",
    value: line,
  }));
  if (!contradiction.length) {
    contradiction.push({
      label: "Conflicts",
      value: "UNKNOWN — no conflict or supersession fields attached",
    });
  }

  return {
    observed,
    derived,
    model_research: modelResearch,
    hypothesis,
    unknown,
    contradiction,
  };
}

export function hasNonFactualResearchOutput(layers: OpportunityEpistemicLayers): boolean {
  return layers.model_research.some((item) => item.nonFactual) || layers.hypothesis.length > 0;
}

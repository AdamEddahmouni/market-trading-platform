import type { OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";
import {
  projectResearchArtifactEvidenceLines,
  researchArtifactEvidenceFromEvidence,
} from "./researchArtifactEvidenceProjection";

export type ProgressivePresentationState =
  | "DETECTED"
  | "PROVISIONAL"
  | "VERIFYING"
  | "VERIFIED"
  | "CONTRADICTED"
  | "EXPIRED";

export type ProgressiveOpportunitySections = {
  presentationState: ProgressivePresentationState;
  stableKey: string;
  instrumentLabel: string;
  entityLabel: string;
  eventType: string;
  ageLabel: string;
  freshnessLabel: string;
  expiryLabel: string;
  urgencyLabel: string;
  surfacedWhy: string;
  deterministicEvidence: Array<{ label: string; value: string }>;
  verification: Array<{ label: string; value: string }>;
  contradictions: Array<{ label: string; value: string }>;
  historicalContext: {
    status: "UNAVAILABLE" | "PARTIAL";
    lines: string[];
  };
  riskLiquidity: Array<{ label: string; value: string }>;
  actionReadiness: {
    canWatch: boolean;
    canDismiss: boolean;
    canPreviewWorkspace: boolean;
    canRevalidate: boolean;
    paperActions: boolean;
    nextSafeAction: string;
    blockedReason?: string;
  };
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

function formatAgeFromNs(createdAtNs: unknown): string {
  if (createdAtNs == null || createdAtNs === "") return "UNAVAILABLE";
  const ns = Number(createdAtNs);
  if (!Number.isFinite(ns) || ns <= 0) return "UNAVAILABLE";
  const ms = ns / 1_000_000;
  const iso = new Date(ms).toISOString();
  return iso;
}

export function stableOpportunityKey(row: OpportunityReviewRow): string {
  return row.opportunity_id ?? row.summary_id;
}

function agentEnrichmentMeta(row: OpportunityReviewRow): Record<string, unknown> | undefined {
  const metadata = row.metadata;
  if (!metadata || typeof metadata !== "object") return undefined;
  const agent = (metadata as Record<string, unknown>).agent_enrichment;
  return agent && typeof agent === "object" ? (agent as Record<string, unknown>) : undefined;
}

export function derivePresentationState(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): ProgressivePresentationState {
  const lifecycle = String(row.lifecycle_state ?? "").toUpperCase();
  if (lifecycle.includes("EXPIRED")) return "EXPIRED";

  const evidenceClass = String(evidence?.evidence_class ?? row.evidence_class ?? "").toUpperCase();
  const supersession = displayValue(evidence?.supersession_reason ?? row.supersession_reason);
  const duplicates = evidence?.duplicates?.length ?? (Array.isArray(row.duplicates) ? row.duplicates.length : 0);
  const agent = agentEnrichmentMeta(row);
  const agentStatus = String(agent?.status ?? "").toUpperCase();

  if (supersession !== "UNAVAILABLE" || duplicates > 0 || agentStatus === "CONTRADICTED") {
    return "CONTRADICTED";
  }
  if (evidenceClass.includes("VERIFIED")) return "VERIFIED";
  if (agentStatus === "PENDING" || agentStatus === "INGESTING") return "VERIFYING";

  const basis = row.ranking_vector?.basis;
  const provisional =
    row.identity_kind !== "OPPORTUNITY_V1" || Boolean(basis && basis !== "COMPARATOR_LEXICOGRAPHIC");
  if (provisional) return "PROVISIONAL";
  return "DETECTED";
}

export function buildProgressiveOpportunitySections(
  row: OpportunityReviewRow,
  options: {
    evidence?: OpportunityEvidenceResponse | null;
    paperActions?: boolean;
    readOnly?: boolean;
  } = {},
): ProgressiveOpportunitySections {
  const { evidence, paperActions = false, readOnly = false } = options;
  const quality = (row.data_quality ?? {}) as Record<string, unknown>;
  const overlay = row.decision_support ?? {};
  const ineligible = row.eligibility_state === "INELIGIBLE" || row.next_safe_action === "STOP";
  const canOpen = Boolean(row.instrument_id && row.next_safe_action === "OPEN_WORKSPACE" && !ineligible);

  const deterministicEvidence: Array<{ label: string; value: string }> = [
    { label: "Source", value: displayValue(quality.source) },
    { label: "Catalyst / promotion", value: displayValue(evidence?.evidence_promotion_reason ?? row.evidence_promotion_reason) },
    { label: "Market behavior", value: displayValue(row.headline) },
    {
      label: "Identity",
      value:
        row.identity_kind === "OPPORTUNITY_V1"
          ? `OpportunityV1 · ${displayValue(row.opportunity_id)}`
          : displayValue(row.identity_kind),
    },
    { label: "Data freshness", value: displayValue(quality.freshness) },
    { label: "Evidence class", value: displayValue(evidence?.evidence_class ?? row.evidence_class) },
  ];

  const agent = agentEnrichmentMeta(row);
  const verification: Array<{ label: string; value: string }> = [
    { label: "Primary source status", value: displayValue(quality.status) },
    { label: "Family admission", value: displayValue(evidence?.family_admission_status ?? row.family_admission_status) },
    { label: "Deterministic checks", value: displayValue(row.family_admission_reason ?? evidence?.family_admission_reason) },
    {
      label: "Agent enrichment",
      value: agent
        ? `${displayValue(agent.status)} · count ${displayValue(agent.count)}`
        : displayValue(
            Array.isArray(row.agent_enrichment_records) && row.agent_enrichment_records.length
              ? "ATTACHED"
              : undefined,
          ),
    },
  ];

  const contradictions: Array<{ label: string; value: string }> = [];
  const supersession = displayValue(evidence?.supersession_reason ?? row.supersession_reason);
  if (supersession !== "UNAVAILABLE") contradictions.push({ label: "Supersession", value: supersession });
  const duplicateReason = displayValue(row.duplicate_reason);
  if (duplicateReason !== "UNAVAILABLE") contradictions.push({ label: "Duplicate", value: duplicateReason });
  if (!contradictions.length) contradictions.push({ label: "Conflicts", value: "None reported" });

  const historicalLines: string[] = [];
  const researchBlock = researchArtifactEvidenceFromEvidence(evidence);
  if (researchBlock) {
    historicalLines.push(...projectResearchArtifactEvidenceLines(researchBlock));
  } else {
    const edgeArtifact = row.edge_stats_artifact ?? row.historical_context;
    if (edgeArtifact && typeof edgeArtifact === "object") {
      const artifact = edgeArtifact as Record<string, unknown>;
      if (artifact.artifact_type) historicalLines.push(`Artifact ${displayValue(artifact.artifact_type)}`);
      const ci = artifact.ci;
      if (ci && typeof ci === "object") {
        const c = ci as Record<string, unknown>;
        historicalLines.push(
          `Sample N ${displayValue(c.sample_count)} · estimate ${displayValue(artifact.estimate)} · CI [${displayValue(c.ci_lower)}, ${displayValue(c.ci_upper)}]`,
        );
      }
    }
  }
  const historicalContext: ProgressiveOpportunitySections["historicalContext"] = {
    status: historicalLines.length ? "PARTIAL" : "UNAVAILABLE",
    lines: historicalLines.length
      ? historicalLines
      : [
          "Research artifact evidence (Edge Stats / options-flow replay) is not attached on this opportunity yet.",
        ],
  };

  const gross = (overlay as Record<string, unknown>).gross_exposure;
  const concentration = (overlay as Record<string, unknown>).concentration;
  const riskDecision = (overlay as Record<string, unknown>).risk_decision;
  const riskLiquidity: Array<{ label: string; value: string }> = [
    { label: "Spread / liquidity", value: "UNAVAILABLE" },
    {
      label: "Exposure",
      value:
        gross && typeof gross === "object"
          ? displayValue((gross as Record<string, unknown>).status)
          : "UNAVAILABLE",
    },
    {
      label: "Concentration",
      value:
        concentration && typeof concentration === "object"
          ? displayValue((concentration as Record<string, unknown>).status)
          : "UNAVAILABLE",
    },
    { label: "Risk readiness", value: displayValue(overlay.kill_switch) },
    {
      label: "Risk decision",
      value:
        riskDecision && typeof riskDecision === "object"
          ? displayValue((riskDecision as Record<string, unknown>).status)
          : "UNAVAILABLE",
    },
  ];

  const presentationState = derivePresentationState(row, evidence);

  return {
    presentationState,
    stableKey: stableOpportunityKey(row),
    instrumentLabel: displayValue(row.instrument_id ?? row.instrument_key),
    entityLabel: displayValue(row.instrument_key ?? row.instrument_id),
    eventType: displayValue(row.evidence_class ?? evidence?.evidence_class ?? row.identity_kind),
    ageLabel: formatAgeFromNs(evidence?.created_at_ns ?? row.created_at_ns),
    freshnessLabel: displayValue(quality.freshness),
    expiryLabel: displayValue(row.expires_at ?? row.expiry),
    urgencyLabel: displayValue(row.urgency ?? row.rank_order),
    surfacedWhy: displayValue(row.evidence_promotion_reason ?? row.headline),
    deterministicEvidence,
    verification,
    contradictions,
    historicalContext,
    riskLiquidity,
    actionReadiness: {
      canWatch: Boolean(paperActions && !readOnly && onAckAllowed(row)),
      canDismiss: Boolean(paperActions && !readOnly && onAckAllowed(row)),
      canPreviewWorkspace: canOpen,
      canRevalidate: canOpen,
      paperActions,
      nextSafeAction: ineligible ? "STOP" : displayValue(row.next_safe_action),
      blockedReason: ineligible ? "Eligibility gate failed" : undefined,
    },
  };
}

function onAckAllowed(row: OpportunityReviewRow): boolean {
  return row.next_safe_action !== "STOP" && row.eligibility_state !== "INELIGIBLE";
}

/** Replay helper: evidence refresh must not change stable identity key. */
export function assertStableIdentityAcrossEvidenceRefresh(
  before: OpportunityReviewRow,
  after: OpportunityReviewRow,
): void {
  if (stableOpportunityKey(before) !== stableOpportunityKey(after)) {
    throw new Error("PROGRESSIVE_OPPORTUNITY_IDENTITY_DRIFT");
  }
  if (before.summary_id !== after.summary_id) {
    throw new Error("PROGRESSIVE_OPPORTUNITY_SUMMARY_DRIFT");
  }
}

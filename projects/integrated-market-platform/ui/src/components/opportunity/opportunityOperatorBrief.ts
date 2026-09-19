/**
 * Radar operator brief: answers discovery questions from backend fields only.
 * Missing contract fields stay UNKNOWN / UNAVAILABLE — never inferred trades.
 */
import type {
  OpportunityEvidenceResponse,
  OpportunityReviewRow,
} from "../../api/opportunityClient";
import { humanizeEnum, resolveSemanticState } from "../../state/semanticState";
import {
  canOpenOpportunityWorkspace,
  evidenceInputsSentence,
  isOpportunityIneligible,
} from "./opportunityPresentation";

export type OperatorBriefHonesty = "OBSERVED" | "DERIVED" | "INFERRED" | "UNKNOWN";

export type OperatorBriefRow = {
  question: string;
  answer: string;
  honesty: OperatorBriefHonesty;
};

const NO_PROVIDER = "UNKNOWN — no provider or source identifiers attached";
const NO_CONFLICT = "UNKNOWN — no conflict or supersession fields attached";
const NO_INVALIDATION = "UNKNOWN — no invalidation criteria attached";

function isPresent(value: unknown): boolean {
  return value !== null && value !== undefined && value !== "";
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function pushNamed(target: Set<string>, value: unknown): void {
  if (typeof value === "string" && value.trim()) target.add(value.trim());
}

function collectNamesFromUnknown(target: Set<string>, value: unknown): void {
  if (!isPresent(value)) return;
  if (typeof value === "string") {
    pushNamed(target, value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectNamesFromUnknown(target, item);
    return;
  }
  const rec = asRecord(value);
  if (!rec) return;
  pushNamed(target, rec.provider ?? rec.provider_id ?? rec.source ?? rec.name);
}

export function collectOpportunityProviderLabels(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): string[] {
  const labels = new Set<string>();
  const quality = asRecord(row.data_quality) ?? asRecord(evidence?.data_quality) ?? {};
  collectNamesFromUnknown(labels, quality.source);
  collectNamesFromUnknown(labels, quality.provider);
  collectNamesFromUnknown(labels, quality.provider_id);
  collectNamesFromUnknown(labels, quality.providers);
  const lineages = [
    ...(Array.isArray(row.lineage_refs) ? row.lineage_refs : []),
    ...(Array.isArray(evidence?.lineage_refs) ? evidence.lineage_refs : []),
  ];
  collectNamesFromUnknown(labels, lineages);
  const items = Array.isArray(evidence?.items) ? evidence.items : [];
  collectNamesFromUnknown(labels, items);
  return [...labels];
}

export function collectOpportunityUnknowns(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): string[] {
  const fields = [
    ...(evidence?.unavailable_fields ?? []),
    ...(row.unavailable_fields ?? []),
  ];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const field of fields) {
    if (!field || seen.has(field)) continue;
    seen.add(field);
    out.push(field);
  }
  for (const dimension of row.ranking_vector?.dimensions ?? []) {
    const status = String(dimension.status ?? "").toUpperCase();
    if (!status || status === "PRESENT") continue;
    const reason = dimension.reason_code ? ` (${dimension.reason_code})` : "";
    out.push(`ranking.${dimension.name} ${status}${reason}`);
  }
  if (!row.instrument_id?.trim()) out.push("instrument_id");
  return out;
}

export function collectOpportunityConflicts(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): string[] {
  const lines: string[] = [];
  const supersession = evidence?.supersession_reason ?? row.supersession_reason;
  if (isPresent(supersession)) lines.push(`Supersession: ${String(supersession)}`);
  if (isPresent(row.duplicate_reason)) lines.push(`Duplicate: ${String(row.duplicate_reason)}`);
  const duplicates = evidence?.duplicates?.length ?? (Array.isArray(row.duplicates) ? row.duplicates.length : 0);
  if (duplicates > 0) lines.push(`${duplicates} duplicate record(s) attached`);
  const metadata = asRecord(row.metadata);
  const agent = asRecord(metadata?.agent_enrichment);
  if (String(agent?.status ?? "").toUpperCase() === "CONTRADICTED") {
    lines.push("Agent enrichment status CONTRADICTED");
  }
  return lines;
}

export function collectOpportunityInvalidationLines(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): string[] {
  const lines: string[] = [];
  if (isOpportunityIneligible(row)) {
    lines.push(
      `Eligibility already refused action (${row.eligibility_state ?? "UNAVAILABLE"} / ${row.next_safe_action ?? "UNAVAILABLE"}).`,
    );
  }
  const lifecycle = String(row.lifecycle_state ?? "").toUpperCase();
  if (lifecycle.includes("EXPIRED")) {
    lines.push("Lifecycle state is expired.");
  }
  const freshness = String(
    asRecord(row.data_quality)?.freshness ?? asRecord(evidence?.data_quality)?.freshness ?? "",
  ).toUpperCase();
  if (freshness === "STALE" || freshness === "DELAYED") {
    lines.push(`Attached freshness is ${freshness} — treat the row as lagged, not current.`);
  }
  for (const gap of collectOpportunityUnknowns(row, evidence)) {
    if (gap.startsWith("ranking.")) {
      lines.push(`${gap} — ranking coverage is incomplete.`);
    }
  }
  const supersession = evidence?.supersession_reason ?? row.supersession_reason;
  if (isPresent(supersession)) {
    lines.push(`A supersession reason is attached (${String(supersession)}).`);
  }
  return lines;
}

function inferenceVersusObservation(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OperatorBriefRow {
  const metadata = asRecord(row.metadata);
  const grounded = asRecord(metadata?.grounded_fact_extraction ?? metadata?.grounded_facts);
  const agent = asRecord(metadata?.agent_enrichment);
  const evidenceClass = String(evidence?.evidence_class ?? row.evidence_class ?? "");
  if (grounded?.disposition) {
    return {
      question: "Inference vs observation?",
      answer: `Grounded-fact disposition ${String(grounded.disposition)} is attached. Ranking and headlines remain derived unless that disposition says otherwise.`,
      honesty: "OBSERVED",
    };
  }
  if (agent?.status) {
    return {
      question: "Inference vs observation?",
      answer: `Agent enrichment ${String(agent.status)} is interpretive. Headline and rank are derived by IMP, not a provider observation.`,
      honesty: "INFERRED",
    };
  }
  if (evidenceClass) {
    return {
      question: "Inference vs observation?",
      answer: `Evidence class ${humanizeEnum(evidenceClass)} is attached. Observation vs inference beyond that class is UNKNOWN.`,
      honesty: "DERIVED",
    };
  }
  return {
    question: "Inference vs observation?",
    answer: "UNKNOWN — no grounded-fact disposition or evidence class attached",
    honesty: "UNKNOWN",
  };
}

export type OperatorBriefOptions = {
  readOnly?: boolean;
  paperActions?: boolean;
};

export function buildOpportunityOperatorBrief(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
  options: OperatorBriefOptions = {},
): OperatorBriefRow[] {
  const { readOnly = false, paperActions = false } = options;
  const instrument = row.instrument_id?.trim() || "UNKNOWN instrument";
  const providers = collectOpportunityProviderLabels(row, evidence);
  const unknowns = collectOpportunityUnknowns(row, evidence);
  const conflicts = collectOpportunityConflicts(row, evidence);
  const invalidation = collectOpportunityInvalidationLines(row, evidence);
  const quality = asRecord(row.data_quality) ?? {};
  const freshness = isPresent(quality.freshness)
    ? humanizeEnum(String(quality.freshness))
    : "UNKNOWN";
  const why =
    (isPresent(evidence?.evidence_promotion_reason) && String(evidence?.evidence_promotion_reason)) ||
    (isPresent(row.evidence_promotion_reason) && String(row.evidence_promotion_reason)) ||
    (row.ranking_vector?.basis
      ? `Ranked on ${humanizeEnum(row.ranking_vector.basis)}`
      : "UNKNOWN — no promotion reason attached");
  const next = resolveSemanticState(
    "research",
    isOpportunityIneligible(row) ? "STOP" : row.next_safe_action,
  );
  const canOpen = canOpenOpportunityWorkspace(row);
  const refusal: string[] = [];
  if (readOnly) refusal.push("This mode is read-only on Radar (no discovery mutations).");
  if (!paperActions) refusal.push("Paper ack actions are not permitted on this session.");
  if (isOpportunityIneligible(row)) refusal.push("Eligibility or next-safe-action is STOP/INELIGIBLE.");
  if (!row.instrument_id?.trim()) refusal.push("No instrument_id — workspace preview cannot be offered.");
  if (!canOpen && row.next_safe_action && row.next_safe_action !== "OPEN_WORKSPACE") {
    refusal.push(`Backend next safe action is ${next.label}, not workspace preview.`);
  }
  refusal.push("Radar never grants live execution. Visibility is not actionability.");

  let actionAnswer: string;
  if (readOnly) {
    actionAnswer = `Inspect and explain only. Next safe action on the row: ${next.label}.`;
  } else if (canOpen && paperActions) {
    actionAnswer = `${next.label} — paper workspace preview and watch/review/dismiss. Not a live order.`;
  } else if (canOpen) {
    actionAnswer = `${next.label} may be previewed, but paper acks are unavailable.`;
  } else {
    actionAnswer = `${next.label}. No workspace promote from this row.`;
  }

  return [
    {
      question: "What happened?",
      answer: `${instrument}: ${row.headline}${
        row.lifecycle_state ? ` · ${humanizeEnum(String(row.lifecycle_state))}` : ""
      }`,
      honesty: "OBSERVED",
    },
    {
      question: "Why is IMP showing this?",
      answer: `${why}. ${evidenceInputsSentence(row)}.`,
      honesty:
        isPresent(row.evidence_promotion_reason) ||
        isPresent(evidence?.evidence_promotion_reason) ||
        Boolean(row.ranking_vector?.basis)
          ? "DERIVED"
          : "UNKNOWN",
    },
    {
      question: "How fresh?",
      answer: freshness,
      honesty: isPresent(quality.freshness) ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "Which providers support it?",
      answer: providers.length ? providers.join(", ") : NO_PROVIDER,
      honesty: providers.length ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "Which facts conflict?",
      answer: conflicts.length ? conflicts.join(" · ") : NO_CONFLICT,
      honesty: conflicts.length ? "OBSERVED" : "UNKNOWN",
    },
    inferenceVersusObservation(row, evidence),
    {
      question: "What is unknown?",
      answer: unknowns.length ? unknowns.join(", ") : "UNKNOWN — no unavailable_fields or missing ranking inputs attached",
      honesty: unknowns.length ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "What would invalidate it?",
      answer: invalidation.length ? invalidation.join(" ") : NO_INVALIDATION,
      honesty: invalidation.length ? "DERIVED" : "UNKNOWN",
    },
    {
      question: "What action is available?",
      answer: actionAnswer,
      honesty: "DERIVED",
    },
    {
      question: "Why might action be refused?",
      answer: refusal.join(" "),
      honesty: "DERIVED",
    },
  ];
}

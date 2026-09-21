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
  explanationRefForRow,
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

function asIntNs(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function qualityRecord(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): Record<string, unknown> {
  return asRecord(row.data_quality) ?? asRecord(evidence?.data_quality) ?? {};
}

function pipelineClockRecord(
  evidence?: OpportunityEvidenceResponse | null,
): Record<string, unknown> | undefined {
  const envelope = evidence as Record<string, unknown> | undefined;
  return asRecord(envelope?.pipeline_clocks);
}

function eligibilityBlocksAction(row: OpportunityReviewRow): boolean {
  const state = String(row.eligibility_state ?? "").toUpperCase();
  return isOpportunityIneligible(row) || state === "UNAVAILABLE";
}

export type OpportunityFreshnessView = {
  status: string | null;
  reasonCode: string | null;
  source: string | null;
  asOfTimeNs: number | null;
  ageNs: number | null;
  /** True when an attached age is 0 — receive and event clocks are the same value. */
  sameClock: boolean;
  actionable: boolean | null;
  queueBackendLabel: string | null;
  operatorAnswer: string;
  honesty: OperatorBriefHonesty;
};

/**
 * Read attached freshness without promoting created_at or a zero lag into a live clock.
 * Backend `data_quality.freshness` is a word; `freshness_evaluation` is the structured record.
 */
export function readOpportunityFreshnessView(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OpportunityFreshnessView {
  const quality = qualityRecord(row, evidence);
  const pipeline = pipelineClockRecord(evidence);
  const evaluation = asRecord(quality.freshness_evaluation);
  const statusRaw =
    evaluation?.status ?? pipeline?.freshness_status ?? quality.freshness;
  const status = isPresent(statusRaw) ? String(statusRaw) : null;
  let reasonCode = isPresent(evaluation?.reason_code)
    ? String(evaluation?.reason_code)
    : isPresent(pipeline?.freshness_reason_code)
      ? String(pipeline?.freshness_reason_code)
      : null;
  const source = isPresent(evaluation?.source)
    ? String(evaluation?.source)
    : isPresent(quality.source)
      ? String(quality.source)
      : null;
  const asOfTimeNs = asIntNs(evaluation?.as_of_time_ns);
  const ageNs = asIntNs(evaluation?.age_ns);
  const sameClock = ageNs === 0 && asOfTimeNs != null;
  const actionable = typeof evaluation?.actionable === "boolean" ? evaluation.actionable : null;

  const parts: string[] = [];
  if (status) parts.push(humanizeEnum(status));
  const persistMinted = pipeline?.created_at_is_persist_minted === true;
  const liveReceiveMissing =
    pipeline?.live_receive_clock === null || pipeline?.live_receive_clock === undefined;
  if (reasonCode === "LIVE_AS_OF_UNAVAILABLE") {
    parts.push("live receive clock unavailable — created_at is not a live clock");
    if (persistMinted && liveReceiveMissing) {
      parts.push("persist-minted created_at is withheld from freshness clocks");
    }
  } else if (reasonCode === "HONESTY_SOURCE_NOT_LIVE_FRESHNESS") {
    parts.push("replay/fixture source does not claim live freshness");
  } else if (reasonCode === "MISSING_AS_OF") {
    parts.push("no as-of clock attached");
  } else if (reasonCode === "NO_EVENT" || reasonCode === "MISSING_SOURCE_TIME") {
    parts.push("event/source time not attached");
  } else if (reasonCode) {
    parts.push(humanizeEnum(reasonCode));
  }
  if (sameClock) {
    parts.push("event vs receive lag UNKNOWN — the same attached clock is used for both");
  } else if (ageNs != null && asOfTimeNs != null) {
    const ageMs = ageNs / 1_000_000;
    parts.push(`attached event-to-receive age ${ageMs >= 1000 ? `${Math.round(ageMs / 1000)}s` : `${Math.round(ageMs)}ms`}`);
  }
  if (actionable === false) {
    parts.push("freshness evaluation is not actionable");
  }

  let operatorAnswer: string;
  let honesty: OperatorBriefHonesty;
  if (!status && !reasonCode) {
    operatorAnswer = "UNKNOWN — no freshness word or freshness_evaluation attached";
    honesty = "UNKNOWN";
  } else {
    operatorAnswer = parts.join(" · ");
    honesty = evaluation ? "OBSERVED" : status ? "OBSERVED" : "UNKNOWN";
    if (sameClock) honesty = "DERIVED";
  }

  return {
    status,
    reasonCode,
    source,
    asOfTimeNs,
    ageNs,
    sameClock,
    actionable,
    queueBackendLabel: status ?? reasonCode,
    operatorAnswer,
    honesty,
  };
}

export function liveFeedClockHonesty(options: {
  unreadyReason?: string;
  withheldRankedCount?: number;
}): string | null {
  if (options.unreadyReason !== "LIVE_AS_OF_UNAVAILABLE") return null;
  const withheld =
    typeof options.withheldRankedCount === "number" && options.withheldRankedCount > 0
      ? ` IMP withheld ${options.withheldRankedCount} ranked row(s) because no live receive clock is attached.`
      : " Ranked live rows stay withheld until a live receive clock is attached.";
  return `${withheld} created_at is not that clock. This is not Item 9 calibration. Live execution stays OFF.`;
}

/**
 * Operator questions for a withheld live book. Ranked rows are not rendered, so
 * the per-row brief never appears — this is the only honest surface.
 */
export function buildLiveWithheldOperatorBrief(options: {
  unreadyReason?: string;
  withheldRankedCount?: number;
  bookHonesty?: string;
}): OperatorBriefRow[] | null {
  if (options.unreadyReason !== "LIVE_AS_OF_UNAVAILABLE") return null;
  const withheldCount =
    typeof options.withheldRankedCount === "number" ? options.withheldRankedCount : null;
  const bookHonesty = options.bookHonesty?.trim();
  const withheldParts: string[] = [];
  if (withheldCount != null && withheldCount > 0) {
    withheldParts.push(
      `IMP withheld ${withheldCount} ranked row(s) because no live receive clock is attached.`,
    );
  } else {
    withheldParts.push(
      "Ranked live rows stay withheld until a live receive clock is attached. withheld_ranked_count is not attached as a positive count.",
    );
  }
  withheldParts.push("created_at is not that clock.");
  if (bookHonesty) withheldParts.push(`Book honesty ${humanizeEnum(bookHonesty)}.`);

  return [
    {
      question: "How fresh?",
      answer:
        "NOT_APPLICABLE — live receive clock unavailable. created_at is not a live clock. Do not read this as FRESH live data.",
      honesty: "OBSERVED",
    },
    {
      question: "How many ranked rows were withheld?",
      answer: withheldParts.join(" "),
      honesty: withheldCount != null && withheldCount > 0 ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "What would invalidate it?",
      answer:
        "A missing live receive clock already withholds ranked presentation. Treating persist-minted created_at as current would be invalid. Restoring a live receive clock is required before ranked rows can be shown; it would not grant execution.",
      honesty: "DERIVED",
    },
    {
      question: "Why might action be refused?",
      answer:
        "Ranked live rows are withheld, not executable. Radar never grants live execution. Live execution stays OFF. Visibility is not actionability.",
      honesty: "DERIVED",
    },
  ];
}

export function opportunityFreshnessQueueLabel(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): string | null {
  return readOpportunityFreshnessView(row, evidence).queueBackendLabel;
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
  const freshness = readOpportunityFreshnessView(row, evidence);
  if (freshness.reasonCode === "LIVE_AS_OF_UNAVAILABLE") out.push("live_receive_clock");
  if (freshness.reasonCode === "MISSING_AS_OF" || freshness.reasonCode === "NO_EVENT") {
    out.push(freshness.reasonCode);
  }
  if (freshness.sameClock) out.push("event_vs_receive_lag");
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
  if (eligibilityBlocksAction(row)) {
    lines.push(
      `Eligibility already refused action (${row.eligibility_state ?? "UNAVAILABLE"} / ${row.next_safe_action ?? "UNAVAILABLE"}).`,
    );
  }
  const decisionSupport = asRecord(row.decision_support);
  const killSwitch = decisionSupport?.kill_switch;
  if (isPresent(killSwitch) && String(killSwitch).toUpperCase() !== "UNAVAILABLE") {
    lines.push(`Decision-support kill switch ${String(killSwitch)} is attached.`);
  }
  const reasonCodes = decisionSupport?.reason_codes;
  if (Array.isArray(reasonCodes) && reasonCodes.length) {
    lines.push(`Decision-support reason codes: ${reasonCodes.map(String).join(", ")}.`);
  }
  const lifecycle = String(row.lifecycle_state ?? "").toUpperCase();
  if (lifecycle.includes("EXPIRED")) {
    lines.push("Lifecycle state is expired.");
  }
  const freshness = readOpportunityFreshnessView(row, evidence);
  const status = (freshness.status ?? "").toUpperCase();
  if (status === "STALE" || status === "DELAYED") {
    lines.push(`Attached freshness is ${status} — treat the row as lagged, not current.`);
  }
  if (freshness.reasonCode === "LIVE_AS_OF_UNAVAILABLE") {
    lines.push("A missing live receive clock withholds or invalidates live queue presentation.");
  }
  if (freshness.actionable === false) {
    lines.push("Freshness evaluation is not actionable.");
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
  const expiry = row.expires_at ?? row.expiry;
  if (isPresent(expiry)) {
    lines.push(`Attached expiry ${String(expiry)} — treat the opportunity as time-bounded.`);
  }
  return lines;
}

/**
 * Operator-facing evidence navigation from attached refs only — no invented URLs
 * or live feeds.
 */
export function buildOpportunityEvidenceNavigation(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OperatorBriefRow {
  const parts: string[] = [];
  const explainRef = explanationRefForRow(row);
  parts.push(`Explain channel ${explainRef}`);
  parts.push("Inspect opens the evidence projection for this row");
  const itemCount = Array.isArray(evidence?.items) ? evidence.items.length : 0;
  const lineageCount = Array.isArray(evidence?.lineage_refs)
    ? evidence.lineage_refs.length
    : Array.isArray(row.lineage_refs)
      ? row.lineage_refs.length
      : 0;
  if (itemCount > 0) {
    parts.push(`${itemCount} evidence item(s) on the projection`);
  } else {
    parts.push("evidence items UNKNOWN until the projection loads");
  }
  if (lineageCount > 0) {
    parts.push(`${lineageCount} lineage ref(s) attached`);
  }
  const research = evidence?.research_artifact_evidence;
  if (research?.readiness) {
    parts.push(`research artifact readiness ${humanizeEnum(String(research.readiness))}`);
  }
  const attachments = research?.attachments?.length ?? 0;
  if (attachments > 0) {
    parts.push(
      `${attachments} research attachment(s) — open Research evidence for interpretation-first review`,
    );
  } else {
    parts.push("Research evidence (/research/evidence) holds interpretation-first attachments");
  }
  const honesty: OperatorBriefHonesty =
    itemCount > 0 || lineageCount > 0 || attachments > 0 ? "OBSERVED" : "DERIVED";
  return {
    question: "Where is the evidence?",
    answer: parts.join(" · "),
    honesty,
  };
}

function inferenceVersusObservation(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OperatorBriefRow {
  const metadata = asRecord(row.metadata);
  const grounded = asRecord(metadata?.grounded_fact_extraction ?? metadata?.grounded_facts);
  const agent = asRecord(metadata?.agent_enrichment);
  const evidenceClass = String(evidence?.evidence_class ?? row.evidence_class ?? "");
  const agentStatus = isPresent(agent?.status) ? String(agent?.status) : "";
  if (agentStatus.toUpperCase() === "CONTRADICTED") {
    return {
      question: "Inference vs observation?",
      answer: `Agent enrichment ${agentStatus} is interpretive. Headline and rank are derived by IMP, not a provider observation.`,
      honesty: "INFERRED",
    };
  }
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

function queueHappenedLine(row: OpportunityReviewRow): OperatorBriefRow {
  const instrument = row.instrument_id?.trim();
  const lifecycle = isPresent(row.lifecycle_state)
    ? humanizeEnum(String(row.lifecycle_state))
    : null;
  const parts: string[] = [];
  if (instrument) parts.push(instrument);
  if (lifecycle) parts.push(lifecycle);
  if (isPresent(row.eligibility_state)) {
    parts.push(`eligibility ${humanizeEnum(String(row.eligibility_state))}`);
  }
  return {
    question: "What happened?",
    answer: parts.length
      ? parts.join(" · ")
      : "UNKNOWN — no instrument or lifecycle attached",
    honesty: instrument ? "OBSERVED" : "UNKNOWN",
  };
}

function queueInferredLine(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OperatorBriefRow {
  const inference = inferenceVersusObservation(row, evidence);
  const headline = row.headline?.trim() || "UNKNOWN headline";
  return {
    question: "Inference vs observation?",
    answer: `${headline} — IMP ranking/headline language, not a provider observation. ${inference.answer}`,
    honesty: inference.honesty === "OBSERVED" ? "DERIVED" : inference.honesty,
  };
}

function queueRefusalLine(
  row: OpportunityReviewRow,
  options: { readOnly?: boolean; paperActions?: boolean } = {},
): OperatorBriefRow {
  const { readOnly = false, paperActions = false } = options;
  const nextRaw = row.next_safe_action?.trim() || "UNAVAILABLE";
  const refusal: string[] = [];
  if (readOnly) refusal.push("This Radar mode is read-only.");
  if (!paperActions) refusal.push("Paper ack actions are not permitted on this session.");
  if (eligibilityBlocksAction(row)) {
    refusal.push(
      `Eligibility or next_safe_action blocks action (${row.eligibility_state ?? "UNAVAILABLE"} / ${nextRaw}).`,
    );
  }
  if (!row.instrument_id?.trim()) {
    refusal.push("No instrument_id — workspace preview cannot be offered.");
  }
  const freshness = readOpportunityFreshnessView(row);
  if (freshness.reasonCode === "LIVE_AS_OF_UNAVAILABLE") {
    refusal.push(
      "LIVE_AS_OF_UNAVAILABLE is withheld-clock honesty, not a repair. Ranked live presentation is not executable.",
    );
  }
  refusal.push(
    `Backend next_safe_action ${nextRaw} is a research gate, not a live order. Radar never grants live execution. Visibility is not actionability.`,
  );
  return {
    question: "Why might action be refused?",
    answer: refusal.join(" "),
    honesty: "DERIVED",
  };
}

/**
 * Queue scan: the same operator questions as the detail brief, compact enough
 * to answer without opening a row. Headline stays inferred/derived. There is
 * no "next action" CTA — next_safe_action is a refusal/gate token only.
 */
export type OpportunityQueueScanOptions = {
  readOnly?: boolean;
  paperActions?: boolean;
  feed?: OperatorBriefFeedContext | null;
};

export function buildOpportunityQueueScan(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
  options: OpportunityQueueScanOptions = {},
): OperatorBriefRow[] {
  const { feed = null } = options;
  const providers = collectOpportunityProviderLabels(row, evidence);
  const unknowns = collectOpportunityUnknowns(row, evidence);
  const conflicts = collectOpportunityConflicts(row, evidence);
  const invalidation = collectOpportunityInvalidationLines(row, evidence);
  const freshness = readOpportunityFreshnessView(row, evidence);
  return [
    queueHappenedLine(row),
    queueInferredLine(row, evidence),
    {
      question: "How fresh?",
      answer: [
        freshness.operatorAnswer,
        feed?.as_of_time ? `Feed as-of ${feed.as_of_time}` : null,
        feed?.as_of_provenance ? `provenance ${feed.as_of_provenance}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
      honesty: freshness.honesty,
    },
    buildOpportunityEvidenceNavigation(row, evidence),
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
    {
      question: "What is unknown?",
      answer: unknowns.length
        ? unknowns.join(", ")
        : "UNKNOWN — no unavailable_fields or missing ranking inputs attached",
      honesty: unknowns.length ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "What would invalidate it?",
      answer: invalidation.length ? invalidation.join(" ") : NO_INVALIDATION,
      honesty: invalidation.length ? "DERIVED" : "UNKNOWN",
    },
    queueRefusalLine(row, options),
  ];
}

export type OperatorBriefFeedContext = {
  as_of_time?: string;
  as_of_provenance?: string;
  data_mode?: string;
  data_provider?: string;
  mode?: string;
};

export type OperatorBriefOptions = {
  readOnly?: boolean;
  paperActions?: boolean;
  feed?: OperatorBriefFeedContext | null;
  withheldRankedCount?: number;
  bookHonesty?: string;
  unreadyReason?: string;
};

export function buildOpportunityOperatorBrief(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
  options: OperatorBriefOptions = {},
): OperatorBriefRow[] {
  const { readOnly = false, paperActions = false, feed, withheldRankedCount, bookHonesty, unreadyReason } =
    options;
  const instrument = row.instrument_id?.trim() || "UNKNOWN instrument";
  const providers = collectOpportunityProviderLabels(row, evidence);
  if (feed?.data_provider?.trim()) {
    const name = feed.data_provider.trim();
    if (!providers.includes(name)) providers.push(name);
  }
  const unknowns = collectOpportunityUnknowns(row, evidence);
  const conflicts = collectOpportunityConflicts(row, evidence);
  const invalidation = collectOpportunityInvalidationLines(row, evidence);
  const freshness = readOpportunityFreshnessView(row, evidence);
  const whyParts: string[] = [];
  if (isPresent(evidence?.evidence_promotion_reason)) whyParts.push(String(evidence?.evidence_promotion_reason));
  else if (isPresent(row.evidence_promotion_reason)) whyParts.push(String(row.evidence_promotion_reason));
  else if (row.ranking_vector?.basis) whyParts.push(`Ranked on ${humanizeEnum(row.ranking_vector.basis)}`);
  if (unreadyReason === "LIVE_AS_OF_UNAVAILABLE") {
    whyParts.push("Live feed is withholding ranked rows without a receive clock");
  }
  if (typeof withheldRankedCount === "number" && withheldRankedCount > 0) {
    whyParts.push(`${withheldRankedCount} ranked row(s) withheld`);
  }
  if (bookHonesty) whyParts.push(humanizeEnum(bookHonesty));
  const why = whyParts.length ? whyParts.join(". ") : "UNKNOWN — no promotion reason attached";
  const whyHonesty: OperatorBriefHonesty =
    isPresent(row.evidence_promotion_reason) ||
    isPresent(evidence?.evidence_promotion_reason) ||
    Boolean(row.ranking_vector?.basis) ||
    unreadyReason === "LIVE_AS_OF_UNAVAILABLE" ||
    (typeof withheldRankedCount === "number" && withheldRankedCount > 0) ||
    Boolean(bookHonesty)
      ? "DERIVED"
      : "UNKNOWN";
  const next = resolveSemanticState(
    "research",
    isOpportunityIneligible(row) ? "STOP" : row.next_safe_action,
  );
  const canOpen = canOpenOpportunityWorkspace(row);
  const refusal: string[] = [];
  if (readOnly) refusal.push("This mode is read-only on Radar (no discovery mutations).");
  if (!paperActions) refusal.push("Paper ack actions are not permitted on this session.");
  if (eligibilityBlocksAction(row)) {
    refusal.push("Eligibility or next-safe-action is STOP/INELIGIBLE/UNAVAILABLE.");
  }
  if (!row.instrument_id?.trim()) refusal.push("No instrument_id — workspace preview cannot be offered.");
  if (!canOpen && row.next_safe_action && row.next_safe_action !== "OPEN_WORKSPACE") {
    refusal.push(`Backend next safe action is ${next.label}, not workspace preview.`);
  }
  if (unreadyReason === "LIVE_AS_OF_UNAVAILABLE") {
    refusal.push("Live receive clock unavailable — ranked presentation is withheld, not executable.");
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

  // Instrument + lifecycle only — headline is IMP-derived and answered under
  // "Inference vs observation?" (matches queueHappenedLine honesty).
  const happenedParts: string[] = [instrument];
  if (isPresent(row.lifecycle_state)) {
    happenedParts.push(humanizeEnum(String(row.lifecycle_state)));
  }
  if (isPresent(row.eligibility_state)) {
    happenedParts.push(`eligibility ${humanizeEnum(String(row.eligibility_state))}`);
  }

  return [
    {
      question: "What happened?",
      answer: happenedParts.join(" · "),
      honesty: row.instrument_id?.trim() ? "OBSERVED" : "UNKNOWN",
    },
    {
      question: "Why is IMP showing this?",
      answer: `${why}. ${evidenceInputsSentence(row)}.`,
      honesty: whyHonesty,
    },
    {
      question: "How fresh?",
      answer: [
        freshness.operatorAnswer,
        feed?.as_of_time ? `Feed as-of ${feed.as_of_time}` : null,
        feed?.as_of_provenance ? `provenance ${feed.as_of_provenance}` : null,
        feed?.data_mode ? `data mode ${humanizeEnum(feed.data_mode)}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
      honesty: freshness.honesty,
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
    buildOpportunityEvidenceNavigation(row, evidence),
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

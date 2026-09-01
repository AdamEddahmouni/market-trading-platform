import {
  laneModuleLabel,
  parsePaperDraftProvenance,
  type PaperDraftSourceContext,
  type PaperOrderDraft,
} from "../paper-now/paperOrderDraft";
import { formatPaperSourceTimeLabel } from "./paperSourceTimestamp";

export type PaperDecisionSourceType = "paper_command_attention" | "workspace_lane";

export type PaperDecisionSourceReason = {
  code: string;
  label: string;
};

/** Immutable source-time context persisted with Paper order intents. */
export type PaperDecisionSourceSnapshot = {
  source_type: PaperDecisionSourceType;
  source_id: string;
  source_module?: string;
  headline?: string;
  tier?: number;
  reasons?: PaperDecisionSourceReason[];
  source_time?: number;
};

export type PaperSourceTimePresentation = "attention_surfaced" | "lane_handoff" | "historical";

export type PaperPersistedSourceContext = {
  snapshot: PaperDecisionSourceSnapshot | null;
  snapshotAvailable: boolean;
  snapshotMismatch: boolean;
  headline: string | null;
  tier: number | null;
  reasons: PaperDecisionSourceReason[];
  sourceTimeLabel: string | null;
  sourceTime: number | null;
  sourceTimePresentation: PaperSourceTimePresentation | null;
  sourceTimeFieldLabel: string | null;
  historicalLabel: string;
};

const MAX_REASON_COUNT = 5;
const MAX_HEADLINE_LENGTH = 240;
const MAX_REASON_LABEL_LENGTH = 200;

function cleanText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.slice(0, maxLength);
}

function parseReasons(value: unknown): PaperDecisionSourceReason[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const reasons: PaperDecisionSourceReason[] = [];
  for (const item of value.slice(0, MAX_REASON_COUNT)) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const code = cleanText(row.code, 64);
    const label = cleanText(row.label, MAX_REASON_LABEL_LENGTH);
    if (!code || !label) continue;
    reasons.push({ code, label });
  }
  return reasons.length > 0 ? reasons : undefined;
}

function parseSourceTime(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return undefined;
  return Math.trunc(value);
}

function parseTier(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return undefined;
  return Math.trunc(value);
}

export function parsePaperDecisionSourceSnapshot(value: unknown): PaperDecisionSourceSnapshot | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  const sourceType = row.source_type;
  if (sourceType !== "paper_command_attention" && sourceType !== "workspace_lane") return null;
  const sourceId = cleanText(row.source_id, 128);
  if (!sourceId) return null;
  const snapshot: PaperDecisionSourceSnapshot = {
    source_type: sourceType,
    source_id: sourceId,
  };
  const sourceModule = cleanText(row.source_module, 64);
  if (sourceModule) snapshot.source_module = sourceModule;
  const headline = cleanText(row.headline, MAX_HEADLINE_LENGTH);
  if (headline) snapshot.headline = headline;
  const tier = parseTier(row.tier);
  if (tier !== undefined) snapshot.tier = tier;
  const reasons = parseReasons(row.reasons);
  if (reasons) snapshot.reasons = reasons;
  const sourceTime = parseSourceTime(row.source_time);
  if (sourceTime !== undefined) snapshot.source_time = sourceTime;
  return snapshot;
}

function snapshotMatchesCorrelation(
  snapshot: PaperDecisionSourceSnapshot,
  correlationId: string | null,
): boolean {
  if (!correlationId?.trim()) return false;
  const correlation = correlationId.trim();
  if (snapshot.source_type === "workspace_lane") {
    return correlation === `lane:${snapshot.source_id}`;
  }
  if (correlation.startsWith("lane:")) return false;
  if (correlation.startsWith("attention:")) {
    return correlation === `attention:${snapshot.source_id}`;
  }
  return correlation === snapshot.source_id;
}

function sourceContextToSnapshotFields(
  sourceContext: PaperDraftSourceContext | null | undefined,
): Pick<PaperDecisionSourceSnapshot, "headline" | "tier" | "reasons" | "source_time"> {
  if (!sourceContext) return {};
  const snapshot: Pick<PaperDecisionSourceSnapshot, "headline" | "tier" | "reasons" | "source_time"> = {};
  const headline = cleanText(sourceContext.headline, MAX_HEADLINE_LENGTH);
  if (headline) snapshot.headline = headline;
  if (typeof sourceContext.tier === "number" && Number.isFinite(sourceContext.tier) && sourceContext.tier >= 0) {
    snapshot.tier = Math.trunc(sourceContext.tier);
  }
  const reasons = parseReasons(sourceContext.reasons);
  if (reasons) snapshot.reasons = reasons;
  const sourceTime = parseSourceTime(sourceContext.source_time);
  if (sourceTime !== undefined) snapshot.source_time = sourceTime;
  return snapshot;
}

/** Map draft provenance + sourceContext into a bounded request snapshot. */
export function buildPaperDecisionSourceSnapshot(draft: PaperOrderDraft): PaperDecisionSourceSnapshot | undefined {
  const provenance = parsePaperDraftProvenance(draft);
  if (!provenance.isValid || provenance.type === "MANUAL" || provenance.type === "UNKNOWN") {
    return undefined;
  }
  const contextFields = sourceContextToSnapshotFields(provenance.sourceContext);
  if (provenance.type === "LANE" && provenance.laneId) {
    const snapshot: PaperDecisionSourceSnapshot = {
      source_type: "workspace_lane",
      source_id: provenance.laneId,
      source_module: provenance.laneId,
    };
    if (contextFields.headline) snapshot.headline = contextFields.headline;
    if (contextFields.source_time !== undefined) snapshot.source_time = contextFields.source_time;
    return snapshot;
  }
  if (provenance.type === "ATTENTION") {
    const attentionId = provenance.attentionId ?? provenance.sourceId;
    if (!attentionId) return undefined;
    const snapshot: PaperDecisionSourceSnapshot = {
      source_type: "paper_command_attention",
      source_id: attentionId,
      ...contextFields,
    };
    return snapshot;
  }
  return undefined;
}

export function paperSourceTimeFieldLabel(presentation: PaperSourceTimePresentation | null): string | null {
  if (!presentation) return null;
  if (presentation === "attention_surfaced") return "Attention surfaced";
  if (presentation === "lane_handoff") return "Lane handoff created";
  return "Source context captured";
}

function sourceTimePresentationFromSnapshot(
  snapshot: PaperDecisionSourceSnapshot,
): PaperSourceTimePresentation | null {
  if (snapshot.source_time === undefined) return null;
  if (snapshot.source_type === "paper_command_attention") return "attention_surfaced";
  if (snapshot.source_type === "workspace_lane") return "lane_handoff";
  return "historical";
}

export { formatPaperSourceTimeLabel } from "./paperSourceTimestamp";

export function laneSnapshotHeadline(moduleId: string): string {
  return `${laneModuleLabel(moduleId)} lane handoff`;
}

export function buildPersistedPaperSourceContext(
  snapshotInput: unknown,
  correlationId: string | null,
): PaperPersistedSourceContext {
  const empty: PaperPersistedSourceContext = {
    snapshot: null,
    snapshotAvailable: false,
    snapshotMismatch: false,
    headline: null,
    tier: null,
    reasons: [],
    sourceTimeLabel: null,
    sourceTime: null,
    sourceTimePresentation: null,
    sourceTimeFieldLabel: null,
    historicalLabel: "Source context at decision handoff",
  };
  const parsed = parsePaperDecisionSourceSnapshot(snapshotInput);
  if (!parsed) return empty;
  const mismatch = !snapshotMatchesCorrelation(parsed, correlationId);
  if (mismatch) {
    return {
      ...empty,
      snapshotMismatch: true,
    };
  }
  const headline =
    parsed.headline ??
    (parsed.source_type === "workspace_lane" ? laneSnapshotHeadline(parsed.source_id) : null);
  const sourceTimePresentation = sourceTimePresentationFromSnapshot(parsed);
  return {
    snapshot: parsed,
    snapshotAvailable: true,
    snapshotMismatch: false,
    headline,
    tier: parsed.tier ?? null,
    reasons: parsed.reasons ?? [],
    sourceTime: parsed.source_time ?? null,
    sourceTimeLabel: formatPaperSourceTimeLabel(parsed.source_time),
    sourceTimePresentation,
    sourceTimeFieldLabel: paperSourceTimeFieldLabel(sourceTimePresentation ?? "historical"),
    historicalLabel: "Source context at decision handoff",
  };
}

export function paperSourceContextTableSummary(
  persisted: PaperPersistedSourceContext,
  fallbackDetail: string,
): string {
  if (persisted.snapshotMismatch) return "Source context unavailable";
  if (persisted.headline) return persisted.headline;
  return fallbackDetail;
}

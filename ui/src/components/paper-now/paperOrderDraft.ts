import type { AttentionItem } from "../../api/client";
import type { PaperOrderRequest } from "../../api/schemas";
import type { WorkspaceModuleId } from "../WorkspaceModuleNav";
import { extractLaneProvenance, extractLaneProvenanceFallback } from "../workspace-module-shared/laneProvenance";
import { buildPaperDecisionSourceSnapshot } from "../paper/paperDecisionSourceSnapshot";
import { formatPaperSourceTimeLabel } from "../paper/paperSourceTimestamp";
import { handoffTimeFromNow, resolvePaperDecisionSourceTime } from "../paper/resolvePaperDecisionSourceTime";

export type PaperOrderSide = "BUY" | "SELL";

export type PaperDraftSourceContext = {
  headline?: string;
  tier?: number;
  reasons?: Array<{ code: string; label: string }>;
  /** Epoch ns (backend convention) or epoch ms (legacy fixtures). Set once at handoff. */
  source_time?: number;
};

export type PaperOrderDraft = {
  version: 1;
  instrumentId: string;
  side: PaperOrderSide;
  quantity: number;
  orderType: "MARKET";
  sourceAttentionId?: string;
  sourceContext?: PaperDraftSourceContext;
};

export type PaperDraftProvenanceType = "LANE" | "ATTENTION" | "MANUAL" | "UNKNOWN";

export type PaperDraftProvenance = {
  type: PaperDraftProvenanceType;
  sourceId: string | null;
  laneId: string | null;
  attentionId: string | null;
  sourceLabel: string;
  sourceTimestamp: string | null;
  sourceReasonSummary: string | null;
  sourceSymbol: string | null;
  isValid: boolean;
  warnings: string[];
  sourceContext: PaperDraftSourceContext | null;
};

type DraftInput = {
  instrumentId: string;
  side: PaperOrderSide | null;
  quantity: number | null;
  maxOrderShares: number;
  sourceAttentionId?: string;
  sourceContext?: PaperDraftSourceContext;
};

const DRAFT_ALLOWED_KEYS = new Set([
  "version",
  "instrumentId",
  "side",
  "quantity",
  "orderType",
  "sourceAttentionId",
  "sourceContext",
]);

const KNOWN_PROVENANCE_PREFIXES = ["lane:", "attention:"] as const;

function parseSourceContext(value: unknown): PaperDraftSourceContext | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  const context: PaperDraftSourceContext = {};
  if (typeof row.headline === "string" && row.headline.trim()) {
    context.headline = row.headline.trim();
  }
  if (typeof row.tier === "number" && Number.isFinite(row.tier)) {
    context.tier = row.tier;
  }
  if (Array.isArray(row.reasons)) {
    const reasons = row.reasons
      .filter((item) => item && typeof item === "object")
      .map((item) => {
        const reason = item as Record<string, unknown>;
        if (typeof reason.code !== "string" || typeof reason.label !== "string") return null;
        return { code: reason.code, label: reason.label };
      })
      .filter((item): item is { code: string; label: string } => item !== null);
    if (reasons.length > 0) context.reasons = reasons;
  }
  if (typeof row.source_time === "number" && Number.isFinite(row.source_time) && row.source_time > 0) {
    context.source_time = Math.trunc(row.source_time);
  }
  return Object.keys(context).length > 0 ? context : undefined;
}

function summarizeSourceReasons(context: PaperDraftSourceContext | null | undefined): string | null {
  if (!context) return null;
  if (context.headline?.trim()) return context.headline.trim();
  if (context.reasons?.length) {
    return context.reasons.map((reason) => reason.label).join("; ");
  }
  return null;
}

export function attentionSourceContextFromItem(
  item: Pick<AttentionItem, "headline" | "tier" | "reasons" | "surfaced_time">,
  options?: { handoffTime?: number },
): PaperDraftSourceContext {
  const context: PaperDraftSourceContext = { headline: item.headline };
  if (typeof item.tier === "number") context.tier = item.tier;
  if (item.reasons.length > 0) {
    context.reasons = item.reasons.map((reason) => ({ code: reason.code, label: reason.label }));
  }
  const sourceTime = resolvePaperDecisionSourceTime({
    canonicalSourceTime: item.surfaced_time,
    handoffTime: options?.handoffTime,
  });
  if (sourceTime !== undefined) context.source_time = sourceTime;
  return context;
}

export function createPaperOrderDraft(input: DraftInput): PaperOrderDraft | null {
  const instrumentId = input.instrumentId.trim().toUpperCase();
  if (!instrumentId || !input.side || input.quantity === null) return null;
  if (!Number.isInteger(input.quantity) || input.quantity < 1) return null;
  if (!Number.isFinite(input.maxOrderShares) || input.maxOrderShares < 1 || input.quantity > input.maxOrderShares) return null;
  const sourceContext = input.sourceContext ? parseSourceContext(input.sourceContext) : undefined;
  return {
    version: 1,
    instrumentId,
    side: input.side,
    quantity: input.quantity,
    orderType: "MARKET",
    ...(input.sourceAttentionId ? { sourceAttentionId: input.sourceAttentionId } : {}),
    ...(sourceContext ? { sourceContext } : {}),
  };
}

export function parsePaperOrderDraft(value: unknown, routeSymbol: string): PaperOrderDraft | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const candidate = value as Record<string, unknown>;
  if (Object.keys(candidate).some((key) => !DRAFT_ALLOWED_KEYS.has(key))) return undefined;
  if (candidate.version !== 1 || candidate.orderType !== "MARKET") return undefined;
  if (candidate.side !== "BUY" && candidate.side !== "SELL") return undefined;
  if (
    typeof candidate.instrumentId !== "string" ||
    candidate.instrumentId.trim().toUpperCase() !== routeSymbol.trim().toUpperCase()
  ) {
    return undefined;
  }
  if (typeof candidate.quantity !== "number" || !Number.isInteger(candidate.quantity) || candidate.quantity < 1) {
    return undefined;
  }
  if (candidate.sourceAttentionId !== undefined && typeof candidate.sourceAttentionId !== "string") return undefined;
  const sourceContext = parseSourceContext(candidate.sourceContext);
  return {
    version: 1,
    instrumentId: candidate.instrumentId.trim().toUpperCase(),
    side: candidate.side,
    quantity: candidate.quantity,
    orderType: "MARKET",
    ...(candidate.sourceAttentionId ? { sourceAttentionId: candidate.sourceAttentionId } : {}),
    ...(sourceContext ? { sourceContext } : {}),
  };
}

export function paperOrderDraftFingerprint(draft: PaperOrderDraft): string {
  return `${draft.instrumentId}|${draft.side}|${draft.quantity}|${draft.orderType}`;
}

export function parsePaperDraftProvenance(draft: PaperOrderDraft | undefined): PaperDraftProvenance {
  const empty: PaperDraftProvenance = {
    type: "MANUAL",
    sourceId: null,
    laneId: null,
    attentionId: null,
    sourceLabel: "Direct workspace entry",
    sourceTimestamp: null,
    sourceReasonSummary: null,
    sourceSymbol: draft?.instrumentId ?? null,
    isValid: true,
    warnings: [],
    sourceContext: draft?.sourceContext ?? null,
  };
  if (!draft) return empty;

  const sourceContext = draft.sourceContext ?? null;
  const sourceReasonSummary = summarizeSourceReasons(sourceContext);
  const sourceSymbol = draft.instrumentId;
  const sourceTimestamp = formatPaperSourceTimeLabel(sourceContext?.source_time);

  if (!draft.sourceAttentionId?.trim()) {
    return {
      ...empty,
      sourceSymbol,
      sourceContext,
      sourceReasonSummary,
    };
  }

  const sourceId = draft.sourceAttentionId.trim();
  const warnings: string[] = [];

  if (sourceId.startsWith("lane:")) {
    const moduleId = sourceId.slice("lane:".length);
    if (!moduleId) {
      return {
        type: "UNKNOWN",
        sourceId,
        laneId: null,
        attentionId: null,
        sourceLabel: "Unknown provenance",
        sourceTimestamp: null,
        sourceReasonSummary,
        sourceSymbol,
        isValid: false,
        warnings: ["Malformed lane provenance — missing lane id."],
        sourceContext,
      };
    }
    const lane = parseLaneProvenance(sourceId);
    return {
      type: "LANE",
      sourceId,
      laneId: moduleId,
      attentionId: null,
      sourceLabel: lane?.label ?? moduleId,
      sourceTimestamp,
      sourceReasonSummary,
      sourceSymbol,
      isValid: true,
      warnings: lane?.isKnown ? warnings : ["Unknown lane id — handoff degrades safely."],
      sourceContext,
    };
  }

  if (sourceId.startsWith("attention:")) {
    const attentionId = sourceId.slice("attention:".length);
    if (!attentionId) {
      return {
        type: "UNKNOWN",
        sourceId,
        laneId: null,
        attentionId: null,
        sourceLabel: "Unknown provenance",
        sourceTimestamp: null,
        sourceReasonSummary,
        sourceSymbol,
        isValid: false,
        warnings: ["Malformed attention provenance — missing attention id."],
        sourceContext,
      };
    }
    return {
      type: "ATTENTION",
      sourceId,
      laneId: null,
      attentionId,
      sourceLabel: "Paper Command",
      sourceTimestamp,
      sourceReasonSummary,
      sourceSymbol,
      isValid: true,
      warnings,
      sourceContext,
    };
  }

  const unsupportedPrefix = KNOWN_PROVENANCE_PREFIXES.find((prefix) => sourceId.startsWith(prefix));
  if (unsupportedPrefix && sourceId === unsupportedPrefix) {
    return {
      type: "UNKNOWN",
      sourceId,
      laneId: null,
      attentionId: null,
      sourceLabel: "Unknown provenance",
      sourceTimestamp: null,
      sourceReasonSummary,
      sourceSymbol,
      isValid: false,
      warnings: ["Malformed provenance id."],
      sourceContext,
    };
  }

  const colonPrefix = sourceId.includes(":") ? sourceId.split(":")[0] : null;
  if (colonPrefix && colonPrefix !== "lane" && colonPrefix !== "attention") {
    return {
      type: "UNKNOWN",
      sourceId,
      laneId: null,
      attentionId: null,
      sourceLabel: "Unknown provenance",
      sourceTimestamp: null,
      sourceReasonSummary,
      sourceSymbol,
      isValid: false,
      warnings: [`Unsupported provenance prefix "${colonPrefix}".`],
      sourceContext,
    };
  }

  return {
    type: "ATTENTION",
    sourceId,
    laneId: null,
    attentionId: sourceId,
    sourceLabel: "Paper Command",
    sourceTimestamp,
    sourceReasonSummary,
    sourceSymbol,
    isValid: true,
    warnings,
    sourceContext,
  };
}

export function derivePaperDecisionCorrelationId(draft: PaperOrderDraft): string | undefined {
  const provenance = parsePaperDraftProvenance(draft);
  if (!provenance.isValid || provenance.type === "MANUAL" || provenance.type === "UNKNOWN") {
    return undefined;
  }
  return draft.sourceAttentionId?.trim() || undefined;
}

export function formatPaperDraftSourceLabel(draft: PaperOrderDraft | undefined): string | null {
  const provenance = parsePaperDraftProvenance(draft);
  if (provenance.type === "MANUAL") return null;
  if (!provenance.isValid) return "Unknown draft source";
  if (provenance.type === "LANE") return `${provenance.sourceLabel} lane`;
  if (provenance.type === "ATTENTION") {
    return provenance.attentionId
      ? `Paper Command attention ${provenance.attentionId}`
      : "Paper Command attention";
  }
  return provenance.sourceLabel;
}

export function buildPaperOrderRequest(draft: PaperOrderDraft, attemptKey: string): PaperOrderRequest {
  const correlationId = derivePaperDecisionCorrelationId(draft);
  const decisionSourceSnapshot = buildPaperDecisionSourceSnapshot(draft);
  return {
    side: draft.side,
    quantity: draft.quantity,
    order_type: draft.orderType,
    instrument_id: draft.instrumentId,
    symbol: draft.instrumentId,
    client_order_id: attemptKey,
    idempotency_key: attemptKey,
    ...(correlationId ? { correlation_id: correlationId } : {}),
    ...(decisionSourceSnapshot ? { decision_source_snapshot: decisionSourceSnapshot } : {}),
  };
}

export function createPaperPreviewAttemptKey(scope: "paper-now" | "workspace-ticket"): string {
  return `${scope}-${globalThis.crypto.randomUUID()}`;
}

/** Seeds a minimal MARKET draft from a workspace lane for Paper mode handoff. */
export function createLanePaperOrderDraft(
  instrumentId: string,
  moduleId: WorkspaceModuleId,
  options?: { now?: () => number; lanePayload?: unknown },
): PaperOrderDraft {
  const handoffTime = handoffTimeFromNow(options?.now);
  const provenance =
    options?.lanePayload !== undefined
      ? extractLaneProvenance(options.lanePayload) ??
        extractLaneProvenanceFallback(options.lanePayload, moduleId)
      : null;
  const laneSourceTime =
    provenance?.source_time && provenance.source_kind !== "unknown" ? provenance.source_time : undefined;
  return {
    version: 1,
    instrumentId: instrumentId.trim().toUpperCase(),
    side: "BUY",
    quantity: 1,
    orderType: "MARKET",
    sourceAttentionId: `lane:${moduleId}`,
    sourceContext: laneSourceTime !== undefined ? { source_time: laneSourceTime } : { source_time: handoffTime },
  };
}

/** Seeds a placeholder MARKET draft from Paper Command attention for workspace handoff. */
export function createAttentionPaperOrderDraft(
  item: Pick<AttentionItem, "attention_id" | "instrument_id" | "headline" | "tier" | "reasons" | "surfaced_time">,
  options?: { now?: () => number },
): PaperOrderDraft | null {
  const instrumentId = item.instrument_id?.trim().toUpperCase();
  if (!instrumentId) return null;
  const handoffTime = handoffTimeFromNow(options?.now);
  return {
    version: 1,
    instrumentId,
    side: "BUY",
    quantity: 1,
    orderType: "MARKET",
    sourceAttentionId: item.attention_id,
    sourceContext: attentionSourceContextFromItem(item, { handoffTime }),
  };
}

export function isLanePaperOrderDraft(draft: PaperOrderDraft | undefined): boolean {
  return parsePaperDraftProvenance(draft).type === "LANE";
}

export function isAttentionPaperOrderDraft(draft: PaperOrderDraft | undefined): boolean {
  return parsePaperDraftProvenance(draft).type === "ATTENTION";
}

export const LANE_MODULE_IDS = [
  "squeeze",
  "order-flow",
  "order-book",
  "catalyst",
  "options",
  "futures",
  "large-transactions",
  "disclosure",
  "institutional-flow",
  "fund-etf",
] as const;

export type LaneModuleId = (typeof LANE_MODULE_IDS)[number];

const LANE_MODULE_LABELS: Record<LaneModuleId, string> = {
  squeeze: "Short Squeeze",
  "order-flow": "Order Flow",
  "order-book": "Order Book",
  catalyst: "Catalyst",
  options: "Options",
  futures: "Futures",
  "large-transactions": "Large Transactions",
  disclosure: "Disclosure",
  "institutional-flow": "Institutional Flow",
  "fund-etf": "Fund / ETF",
};

export function isKnownLaneModuleId(moduleId: string): moduleId is LaneModuleId {
  return (LANE_MODULE_IDS as readonly string[]).includes(moduleId);
}

export function laneModuleLabel(moduleId: string): string {
  return isKnownLaneModuleId(moduleId) ? LANE_MODULE_LABELS[moduleId] : moduleId;
}

export function parseLaneProvenance(
  sourceAttentionId: string | undefined,
): { moduleId: string; label: string; isKnown: boolean } | null {
  if (!sourceAttentionId?.startsWith("lane:")) return null;
  const moduleId = sourceAttentionId.slice("lane:".length);
  if (!moduleId) return null;
  const isKnown = isKnownLaneModuleId(moduleId);
  return { moduleId, label: laneModuleLabel(moduleId), isKnown };
}

export const LANE_DRAFT_PLACEHOLDER_NOTE =
  "Placeholder draft uses BUY × 1 MARKET — confirm side and quantity before submit.";

export const ATTENTION_DRAFT_PLACEHOLDER_NOTE =
  "Placeholder draft from Paper Command — not an execution recommendation. Confirm side and quantity before submit.";

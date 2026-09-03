import {
  formatPaperDraftSourceLabel,
  laneModuleLabel,
  parsePaperDraftProvenance,
  type PaperDraftProvenance,
  type PaperDraftProvenanceType,
} from "../paper-now/paperOrderDraft";
import {
  buildPersistedPaperSourceContext,
  paperSourceContextTableSummary,
  type PaperPersistedSourceContext,
} from "../paper/paperDecisionSourceSnapshot";

export type PaperDecisionSourceCategory = "PAPER_COMMAND" | "WORKSPACE_LANE" | "MANUAL" | "UNKNOWN";

export type PaperOperationalProvenance = PaperDraftProvenance & {
  correlationId: string | null;
  clientOrderId: string | null;
  sourceCategory: PaperDecisionSourceCategory;
  badgeLabel: string;
  sourceDetail: string;
  provenanceLabel: string;
  isDecisionProvenance: boolean;
  persistedSourceContext: PaperPersistedSourceContext;
  tableSourceSummary: string;
};

const ATTENTION_CORRELATION_PATTERN = /^(attention:|attention-|att-|ATT-)/;

const TERMINAL_ORDER_STATES = new Set([
  "FILLED",
  "CANCELLED",
  "REJECTED",
  "EXPIRED",
  "RISK_REJECTED",
]);

export function isTerminalPaperOrderState(state: string | undefined | null): boolean {
  if (!state) return false;
  return TERMINAL_ORDER_STATES.has(String(state).toUpperCase());
}

function sourceCategoryFromType(type: PaperDraftProvenanceType): PaperDecisionSourceCategory {
  if (type === "LANE") return "WORKSPACE_LANE";
  if (type === "ATTENTION") return "PAPER_COMMAND";
  if (type === "UNKNOWN") return "UNKNOWN";
  return "MANUAL";
}

function badgeLabelFromProvenance(provenance: PaperDraftProvenance): string {
  if (provenance.type === "LANE") {
    const laneId = provenance.laneId ?? provenance.sourceId?.replace(/^lane:/, "") ?? "LANE";
    return laneModuleLabel(laneId).replace(/\s+/g, " ").toUpperCase();
  }
  if (provenance.type === "ATTENTION") return "PAPER COMMAND";
  if (provenance.type === "UNKNOWN") return "UNKNOWN";
  return "MANUAL";
}

function sourceDetailFromProvenance(
  provenance: PaperDraftProvenance,
  correlationId: string | null,
): string {
  if (provenance.type === "ATTENTION" && provenance.attentionId) {
    return provenance.attentionId;
  }
  if (provenance.type === "LANE" && provenance.laneId) {
    return provenance.laneId;
  }
  if (provenance.type === "UNKNOWN" && correlationId) {
    return correlationId;
  }
  if (provenance.type === "MANUAL") {
    return "No recorded decision source";
  }
  return provenance.sourceLabel;
}

function isLikelyAttentionCorrelation(correlationId: string): boolean {
  if (correlationId.startsWith("attention:")) return true;
  return ATTENTION_CORRELATION_PATTERN.test(correlationId);
}

function manualProvenance(
  symbol: string | null = null,
  snapshotInput?: unknown,
  correlationId: string | null = null,
): PaperOperationalProvenance {
  const provenance = parsePaperDraftProvenance(undefined);
  const persistedSourceContext = buildPersistedPaperSourceContext(snapshotInput, correlationId);
  const base = {
    ...provenance,
    sourceSymbol: symbol,
    correlationId,
    clientOrderId: null,
    sourceCategory: "MANUAL" as const,
    badgeLabel: "MANUAL",
    sourceDetail: "No recorded decision source",
    provenanceLabel: "Manual entry",
    isDecisionProvenance: false,
    persistedSourceContext,
    tableSourceSummary: paperSourceContextTableSummary(persistedSourceContext, "No recorded decision source"),
  };
  return base;
}

/** Safely interpret persisted order correlation values for portfolio history. */
export function parsePersistedPaperDecisionProvenance(
  correlationId: string | undefined | null,
  clientOrderId?: string | undefined | null,
  symbol?: string | null,
  decisionSourceSnapshot?: unknown,
): PaperOperationalProvenance {
  const correlation = correlationId?.trim() || null;
  const clientOrder = clientOrderId?.trim() || null;

  if (!correlation) {
    return manualProvenance(symbol ?? null, decisionSourceSnapshot, null);
  }

  if (clientOrder && correlation === clientOrder) {
    return {
      ...manualProvenance(symbol ?? null, decisionSourceSnapshot, correlation),
      correlationId: correlation,
      clientOrderId: clientOrder,
    };
  }

  if (correlation.startsWith("lane:")) {
    const draftProvenance = parsePaperDraftProvenance({
      version: 1,
      instrumentId: symbol?.trim().toUpperCase() || "ORDER",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: correlation,
    });
    return buildOperationalProvenance(draftProvenance, correlation, clientOrder, decisionSourceSnapshot);
  }

  if (correlation.startsWith("attention:")) {
    const draftProvenance = parsePaperDraftProvenance({
      version: 1,
      instrumentId: symbol?.trim().toUpperCase() || "ORDER",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: correlation,
    });
    return buildOperationalProvenance(draftProvenance, correlation, clientOrder, decisionSourceSnapshot);
  }

  if (isLikelyAttentionCorrelation(correlation)) {
    const draftProvenance = parsePaperDraftProvenance({
      version: 1,
      instrumentId: symbol?.trim().toUpperCase() || "ORDER",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: correlation,
    });
    return buildOperationalProvenance(draftProvenance, correlation, clientOrder, decisionSourceSnapshot);
  }

  if (correlation.includes(":")) {
    const draftProvenance = parsePaperDraftProvenance({
      version: 1,
      instrumentId: symbol?.trim().toUpperCase() || "ORDER",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: correlation,
    });
    if (draftProvenance.type === "UNKNOWN") {
      return buildOperationalProvenance(draftProvenance, correlation, clientOrder, decisionSourceSnapshot);
    }
  }

  const persistedSourceContext = buildPersistedPaperSourceContext(decisionSourceSnapshot, correlation);
  return {
    type: "UNKNOWN",
    sourceId: correlation,
    laneId: null,
    attentionId: null,
    sourceLabel: "Unknown source",
    sourceTimestamp: null,
    sourceReasonSummary: null,
    sourceSymbol: symbol ?? null,
    isValid: false,
    warnings: ["Correlation is not a recognized decision provenance id."],
    sourceContext: null,
    correlationId: correlation,
    clientOrderId: clientOrder,
    sourceCategory: "UNKNOWN",
    badgeLabel: "UNKNOWN",
    sourceDetail: correlation,
    provenanceLabel: "Unknown source",
    isDecisionProvenance: false,
    persistedSourceContext,
    tableSourceSummary: paperSourceContextTableSummary(persistedSourceContext, correlation),
  };
}

function buildOperationalProvenance(
  provenance: PaperDraftProvenance,
  correlationId: string,
  clientOrderId: string | null,
  decisionSourceSnapshot?: unknown,
): PaperOperationalProvenance {
  const provenanceLabel =
    formatPaperDraftSourceLabel({
      version: 1,
      instrumentId: provenance.sourceSymbol ?? "ORDER",
      side: "BUY",
      quantity: 1,
      orderType: "MARKET",
      sourceAttentionId: correlationId,
    }) ?? provenance.sourceLabel;
  const sourceDetail = sourceDetailFromProvenance(provenance, correlationId);
  const persistedSourceContext = buildPersistedPaperSourceContext(decisionSourceSnapshot, correlationId);

  return {
    ...provenance,
    correlationId,
    clientOrderId,
    sourceCategory: sourceCategoryFromType(provenance.type),
    badgeLabel: badgeLabelFromProvenance(provenance),
    sourceDetail,
    provenanceLabel,
    isDecisionProvenance: provenance.type === "LANE" || provenance.type === "ATTENTION",
    persistedSourceContext,
    tableSourceSummary: paperSourceContextTableSummary(persistedSourceContext, sourceDetail),
  };
}

export function paperDecisionSourceFilterLabel(category: PaperDecisionSourceCategory | "ALL"): string {
  switch (category) {
    case "ALL":
      return "All sources";
    case "PAPER_COMMAND":
      return "Paper Command";
    case "WORKSPACE_LANE":
      return "Workspace lane";
    case "MANUAL":
      return "Manual";
    case "UNKNOWN":
      return "Unknown";
    default:
      return category;
  }
}

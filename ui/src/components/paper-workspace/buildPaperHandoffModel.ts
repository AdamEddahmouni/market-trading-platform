import type { WorkspaceModuleId } from "../WorkspaceModuleNav";
import {
  ATTENTION_DRAFT_PLACEHOLDER_NOTE,
  LANE_DRAFT_PLACEHOLDER_NOTE,
  parseLaneProvenance,
  parsePaperDraftProvenance,
  parsePaperOrderDraft,
  type PaperDraftProvenanceType,
  type PaperOrderDraft,
} from "../paper-now/paperOrderDraft";
import { formatPaperSourceTimeLabel } from "../paper/paperSourceTimestamp";
import { laneModuleTitle } from "../workspace-module-shared/buildLaneModeContent";

export type PaperHandoffKind = "lane" | "attention" | "manual" | "unknown";

export type PaperHandoffModel = {
  kind: PaperHandoffKind;
  provenanceType: PaperDraftProvenanceType;
  sourceLane: WorkspaceModuleId | null;
  sourceTitle: string;
  provenanceId: string | null;
  attentionId: string | null;
  isLaneOriginated: boolean;
  isAttentionOriginated: boolean;
  isMalformed: boolean;
  isUnknownLane: boolean;
  hasHandoff: boolean;
  placeholder: { side: PaperOrderDraft["side"]; quantity: number; orderType: "MARKET" };
  placeholderWarning: string;
  handoffSummary: string;
  sourceContextSummary: string | null;
  sourceTier: number | null;
  sourceReasons: Array<{ code: string; label: string }>;
  sourceContextNote: string;
  sourceTime: number | null;
  sourceTimeLabel: string | null;
  sourceTimeFieldLabel: string | null;
  currentContextNote: string;
  draftVersion: 1 | null;
  symbol: string;
  warnings: string[];
};

function handoffKindFromProvenance(type: PaperDraftProvenanceType): PaperHandoffKind {
  if (type === "LANE") return "lane";
  if (type === "ATTENTION") return "attention";
  if (type === "MANUAL") return "manual";
  return "unknown";
}

export function buildPaperHandoffModel(
  draft: PaperOrderDraft | undefined,
  routeSymbol: string,
): PaperHandoffModel {
  const symbol = routeSymbol.trim().toUpperCase();
  const currentContextNote =
    "Current workspace evidence loads independently from the handoff. Review before preview.";
  const sourceContextNote =
    "Source context reflects what Paper Command surfaced — not current portfolio or risk state.";

  const empty: PaperHandoffModel = {
    kind: "manual",
    provenanceType: "MANUAL",
    sourceLane: null,
    sourceTitle: "",
    provenanceId: null,
    attentionId: null,
    isLaneOriginated: false,
    isAttentionOriginated: false,
    isMalformed: false,
    isUnknownLane: false,
    hasHandoff: false,
    placeholder: { side: "BUY", quantity: 1, orderType: "MARKET" },
    placeholderWarning: LANE_DRAFT_PLACEHOLDER_NOTE,
    handoffSummary: "No handoff — review workspace evidence before drafting.",
    sourceContextSummary: null,
    sourceTier: null,
    sourceReasons: [],
    sourceContextNote,
    sourceTime: null,
    sourceTimeLabel: null,
    sourceTimeFieldLabel: null,
    currentContextNote,
    draftVersion: null,
    symbol,
    warnings: [],
  };

  if (!draft) return empty;

  const validated = parsePaperOrderDraft(draft, symbol);
  const provenance = parsePaperDraftProvenance(draft);
  const laneProvenance = parseLaneProvenance(draft.sourceAttentionId);
  const kind = handoffKindFromProvenance(provenance.type);
  const isMalformed = !validated || !provenance.isValid;
  const isUnknownLane = Boolean(laneProvenance && !laneProvenance.isKnown);
  const sourceLane =
    laneProvenance?.isKnown ? (laneProvenance.moduleId as WorkspaceModuleId) : null;

  const placeholder = {
    side: draft.side,
    quantity: draft.quantity,
    orderType: draft.orderType as "MARKET",
  };

  const sourceReasons = provenance.sourceContext?.reasons ?? [];
  const sourceTier = provenance.sourceContext?.tier ?? null;
  const sourceContextSummary = provenance.sourceReasonSummary;
  const sourceTime = provenance.sourceContext?.source_time ?? null;
  const sourceTimeLabel = formatPaperSourceTimeLabel(sourceTime);
  const sourceTimeFieldLabel =
    kind === "attention" && sourceTimeLabel
      ? "Attention surfaced"
      : kind === "lane" && sourceTimeLabel
        ? "Lane handoff created"
        : null;

  let handoffSummary = empty.handoffSummary;
  let placeholderWarning = LANE_DRAFT_PLACEHOLDER_NOTE;

  if (isMalformed) {
    handoffSummary =
      "Draft provenance could not be validated — workspace evidence remains readable; draft a new ticket after review.";
  } else if (kind === "unknown") {
    handoffSummary =
      "Unknown draft provenance — treat placeholder values as non-recommendations and review workspace evidence before preview.";
  } else if (kind === "lane" && laneProvenance) {
    placeholderWarning = LANE_DRAFT_PLACEHOLDER_NOTE;
    handoffSummary = `Opened from the ${laneProvenance.label} lane. ${placeholder.side} × ${placeholder.quantity} ${placeholder.orderType} is a starting placeholder, not a recommendation. Review workspace evidence and preview against current Paper portfolio and risk state before submitting.`;
  } else if (kind === "attention") {
    placeholderWarning = ATTENTION_DRAFT_PLACEHOLDER_NOTE;
    const attentionLabel = provenance.attentionId ?? provenance.sourceId ?? "attention";
    handoffSummary = `Opened from Paper Command attention ${attentionLabel}. The draft is a starting point, not an execution recommendation. Current workspace evidence and Paper portfolio/risk state may differ from the source context.`;
  }

  const sourceTitle =
    kind === "lane" && sourceLane
      ? laneModuleTitle(sourceLane)
      : kind === "attention"
        ? "Paper Command"
        : kind === "unknown"
          ? "Unknown provenance"
          : "";

  return {
    kind,
    provenanceType: provenance.type,
    sourceLane,
    sourceTitle,
    provenanceId: provenance.sourceId,
    attentionId: provenance.attentionId,
    isLaneOriginated: kind === "lane",
    isAttentionOriginated: kind === "attention",
    isMalformed,
    isUnknownLane,
    hasHandoff: kind === "lane" || kind === "attention" || kind === "unknown",
    placeholder,
    placeholderWarning,
    handoffSummary,
    sourceContextSummary,
    sourceTier,
    sourceReasons,
    sourceContextNote: kind === "attention" ? sourceContextNote : "Source context is carried from the handoff only when available.",
    sourceTime,
    sourceTimeLabel,
    sourceTimeFieldLabel,
    currentContextNote,
    draftVersion: validated?.version ?? null,
    symbol,
    warnings: provenance.warnings,
  };
}

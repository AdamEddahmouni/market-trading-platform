import type { PaperOrderSubmitResponse } from "../../api/schemas";
import { PORTFOLIO_SECTIONS } from "../paper-portfolio/paperPortfolioPresentation";
import {
  formatPaperDraftSourceLabel,
  formatPaperPlaceholderOrderLabel,
  parsePaperDraftProvenance,
  type PaperOrderDraft,
  type PaperOrderSide,
} from "../paper-now/paperOrderDraft";

/** Durable post-submit acknowledgement derived from the Paper submit response. */
export type PaperOrderAcknowledgement = {
  orderId: string | null;
  intentId: string | null;
  fillId: string | null;
  duplicate: boolean;
  decision: string | null;
  orderState: string | null;
  side: string | null;
  quantity: number | null;
  instrumentId: string | null;
  orderLabel: string | null;
  correlationId: string | null;
  opportunityId: string | null;
  provenanceLabel: string | null;
  /** Portfolio Order history anchor — not a second execution surface. */
  orderHistoryHref: string;
  hasDurableOrder: boolean;
  /** True only when the server already returned a fill; never invents one. */
  fillObserved: boolean;
};

const ORDER_HISTORY_HREF = `/portfolio#${PORTFOLIO_SECTIONS.orderHistory}`;

function readString(record: Record<string, unknown> | null | undefined, key: string): string | null {
  if (!record) return null;
  const value = record[key];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function readNumber(record: Record<string, unknown> | null | undefined, key: string): number | null {
  if (!record) return null;
  const value = record[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function normalizeSide(value: string | null): PaperOrderSide | null {
  if (!value) return null;
  const upper = value.toUpperCase();
  if (upper === "BUY" || upper === "SELL") return upper;
  return null;
}

/**
 * Build an operator-facing acknowledgement from the server submit payload.
 * Preserves opportunity provenance from the handoff draft when present.
 * Does not invent fills — `fillObserved` tracks only what the response carried.
 */
export function buildPaperOrderAcknowledgement(
  submission: PaperOrderSubmitResponse["submission"],
  draft?: PaperOrderDraft,
): PaperOrderAcknowledgement {
  const order = asRecord(submission.order);
  const fill = asRecord(submission.fill ?? undefined);
  const orderId = readString(submission as Record<string, unknown>, "order_id") ?? readString(order, "order_id");
  const intentId = readString(submission as Record<string, unknown>, "intent_id");
  const fillId =
    readString(submission as Record<string, unknown>, "fill_id") ??
    readString(fill, "fill_id");
  const orderState = readString(order, "state") ?? readString(order, "status");
  const side =
    normalizeSide(readString(order, "side")) ??
    (draft?.side ?? null);
  const quantity =
    readNumber(order, "desired_quantity") ??
    readNumber(order, "quantity") ??
    readNumber(order, "requested_quantity") ??
    (draft?.quantity ?? null);
  const instrumentId =
    readString(order, "instrument_id") ??
    readString(asRecord(order?.instrument), "instrument_id") ??
    (draft?.instrumentId ?? null);
  const correlationId =
    readString(submission as Record<string, unknown>, "correlation_id") ??
    readString(order, "correlation_id") ??
    (draft?.sourceAttentionId ?? null);

  const provenance = parsePaperDraftProvenance(draft);
  const opportunityId =
    provenance.opportunityId ??
    (correlationId?.startsWith("opportunity:") ? correlationId.slice("opportunity:".length) : null);
  const provenanceLabel =
    formatPaperDraftSourceLabel(draft) ??
    (opportunityId ? `Radar watched opportunity ${opportunityId}` : null);

  const orderLabel =
    side && quantity != null && quantity > 0
      ? formatPaperPlaceholderOrderLabel(side, quantity)
      : null;

  return {
    orderId,
    intentId,
    fillId,
    duplicate: Boolean(submission.duplicate),
    decision: typeof submission.decision === "string" ? submission.decision : null,
    orderState,
    side,
    quantity,
    instrumentId,
    orderLabel,
    correlationId,
    opportunityId,
    provenanceLabel,
    orderHistoryHref: ORDER_HISTORY_HREF,
    hasDurableOrder: Boolean(orderId),
    fillObserved: Boolean(fillId || fill),
  };
}

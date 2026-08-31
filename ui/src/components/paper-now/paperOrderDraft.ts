import type { PaperOrderRequest } from "../../api/schemas";

export type PaperOrderSide = "BUY" | "SELL";

export type PaperOrderDraft = {
  version: 1;
  instrumentId: string;
  side: PaperOrderSide;
  quantity: number;
  orderType: "MARKET";
  sourceAttentionId?: string;
};

type DraftInput = {
  instrumentId: string;
  side: PaperOrderSide | null;
  quantity: number | null;
  maxOrderShares: number;
  sourceAttentionId?: string;
};

export function createPaperOrderDraft(input: DraftInput): PaperOrderDraft | null {
  const instrumentId = input.instrumentId.trim().toUpperCase();
  if (!instrumentId || !input.side || input.quantity === null) return null;
  if (!Number.isInteger(input.quantity) || input.quantity < 1) return null;
  if (!Number.isFinite(input.maxOrderShares) || input.maxOrderShares < 1 || input.quantity > input.maxOrderShares) return null;
  return {
    version: 1,
    instrumentId,
    side: input.side,
    quantity: input.quantity,
    orderType: "MARKET",
    ...(input.sourceAttentionId ? { sourceAttentionId: input.sourceAttentionId } : {}),
  };
}

export function parsePaperOrderDraft(value: unknown, routeSymbol: string): PaperOrderDraft | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const candidate = value as Record<string, unknown>;
  const allowed = new Set(["version", "instrumentId", "side", "quantity", "orderType", "sourceAttentionId"]);
  if (Object.keys(candidate).some((key) => !allowed.has(key))) return undefined;
  if (candidate.version !== 1 || candidate.orderType !== "MARKET") return undefined;
  if (candidate.side !== "BUY" && candidate.side !== "SELL") return undefined;
  if (typeof candidate.instrumentId !== "string" || candidate.instrumentId.trim().toUpperCase() !== routeSymbol.trim().toUpperCase()) return undefined;
  if (typeof candidate.quantity !== "number" || !Number.isInteger(candidate.quantity) || candidate.quantity < 1) return undefined;
  if (candidate.sourceAttentionId !== undefined && typeof candidate.sourceAttentionId !== "string") return undefined;
  return {
    version: 1,
    instrumentId: candidate.instrumentId.trim().toUpperCase(),
    side: candidate.side,
    quantity: candidate.quantity,
    orderType: "MARKET",
    ...(candidate.sourceAttentionId ? { sourceAttentionId: candidate.sourceAttentionId } : {}),
  };
}

export function paperOrderDraftFingerprint(draft: PaperOrderDraft): string {
  return `${draft.instrumentId}|${draft.side}|${draft.quantity}|${draft.orderType}`;
}

export function buildPaperOrderRequest(draft: PaperOrderDraft, attemptKey: string): PaperOrderRequest {
  return {
    side: draft.side,
    quantity: draft.quantity,
    order_type: draft.orderType,
    instrument_id: draft.instrumentId,
    symbol: draft.instrumentId,
    client_order_id: attemptKey,
    idempotency_key: attemptKey,
  };
}

export function createPaperPreviewAttemptKey(scope: "paper-now" | "workspace-ticket"): string {
  return `${scope}-${globalThis.crypto.randomUUID()}`;
}

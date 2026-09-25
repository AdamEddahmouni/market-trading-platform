import { createPaperOrderDraft, type PaperOrderDraft } from "../paper-now/paperOrderDraft";
import type { PortfolioPositionRow } from "./paperPortfolioPresentation";

export type PositionTradeAction = "add" | "reduce" | "close";

export function buildPositionTradeDraft(
  position: Pick<PortfolioPositionRow, "instrumentId" | "side" | "quantity">,
  action: PositionTradeAction,
  maxOrderShares: number,
): PaperOrderDraft | null {
  if (position.side === "flat" || !Number.isInteger(position.quantity) || position.quantity < 1) return null;
  const sameSide = position.side === "long" ? "BUY" : "SELL";
  const oppositeSide = position.side === "long" ? "SELL" : "BUY";
  return createPaperOrderDraft({
    instrumentId: position.instrumentId,
    side: action === "add" ? sameSide : oppositeSide,
    quantity: action === "close" ? position.quantity : 1,
    maxOrderShares,
  });
}

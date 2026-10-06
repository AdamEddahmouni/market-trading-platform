import type { TradeLifecycle } from "../../../api/screenerLifecycle";
import { formatMoney, formatSignedMoney, type SignedMoney } from "../../paper-portfolio/paperExperimentPresentation";
import { formatStopPrice, formatStopTime } from "../../paper-workspace/buildPaperTrailingStopModel";
import { etClock } from "../panels/shared";

/** Labels only. Every state, price, time and P&L value is the server's lifecycle projection. */

export const UNAVAILABLE = "Unavailable";
export const actionLabel = (state: string) => state.replace(/_/g, " ");

const STAGE: Record<TradeLifecycle["stage"], string> = {
  SELECTED_NOT_ASSESSED: "SELECTED · NOT ASSESSED", NO_ACTION: "NO ACTION", CONSIDERING_ENTRY: "CONSIDERING ENTRY",
  ENTER_NOT_EXECUTED: "ENTER DECIDED · NOT EXECUTED", ENTRY_SUBMITTED: "PAPER ENTRY SUBMITTED · NOT FILLED",
  REVALIDATION_REQUIRED: "DECISION NEEDS FRESH EVIDENCE", POSITION_OPEN: "POSITION OPEN",
  EXIT_NOT_EXECUTED: "EXIT DECIDED · POSITION STILL OPEN", EXIT_SUBMITTED: "PAPER CLOSE SUBMITTED · POSITION STILL OPEN", POSITION_CLOSED: "POSITION CLOSED",
};

/** The one line a trader reads first. An open position also names its current decision. */
export function stageLabel(lifecycle: TradeLifecycle): string {
  const base = STAGE[lifecycle.stage];
  return lifecycle.stage === "POSITION_OPEN" && lifecycle.decision ? `${base} · ${actionLabel(lifecycle.decision.action_state)}` : base;
}

export const ENTRY_LABEL: Record<TradeLifecycle["entry"]["status"], string> = {
  NOT_PROPOSED: "None", CONSIDERED: "Considered — not decided", DECIDED_ENTER: "DECIDED — NOT EXECUTED", SUBMITTED_PAPER: "Paper order submitted — not filled",
  PARTIALLY_FILLED: "Partially filled (simulated)", FILLED: "Filled (simulated)", BLOCKED: "Blocked", EXPIRED: "Decision expired — not executed",
};
export const EXIT_LABEL: Record<TradeLifecycle["exit"]["status"], string> = {
  NO_EXIT: "No exit", EXIT_DECIDED: "EXIT decided — position still open", EXIT_SUBMITTED: "Paper close submitted — not filled",
  PARTIALLY_CLOSED: "Partially closed — position still open", CLOSED: "Closed (simulated close fill)", BLOCKED: "EXIT decided — Paper close blocked",
};
export const PAPER_CLOSE_LABEL: Record<TradeLifecycle["exit"]["paper_close"], string> = {
  NOT_APPLICABLE: "Not applicable", NOT_SUBMITTED: "NOT SUBMITTED", SUBMITTED_NOT_FILLED: "Submitted — not filled", PARTIALLY_FILLED: "Partially filled", FILLED: "Filled (simulated)",
};
export const ORIGIN_LABEL: Record<NonNullable<TradeLifecycle["decision"]>["origin"], string> = {
  AI_PROPOSAL_SERVER_GATED: "AI proposal, server-gated decision", DETERMINISTIC_RISK_CONTROL: "Deterministic risk control", SERVER_FAILSAFE: "Server fail-safe",
};
export const RISK_LABEL: Record<TradeLifecycle["risk_control"]["status"], string> = {
  NOT_CONFIGURED: "SMA trailing stop not configured", WARMING_UP: "Warming up — no stop level yet", ACTIVE: "ACTIVE", STALE: "Stop update stale",
  BLOCKED: "Blocked", BREACHED: "BREACHED", CLOSED: "Closed", NOT_APPLICABLE: "Not applicable — no open position",
  NO_STOP_RECORD: "No stop record for this episode", UNAVAILABLE: "Unavailable",
};
export const QUALITY_LABEL: Record<TradeLifecycle["pnl"]["quality"], string> = {
  CURRENT: "CURRENT", STALE: "STALE — not a current valuation", DEGRADED: "DEGRADED — not a current valuation", UNAVAILABLE: "UNAVAILABLE",
  REALIZED: "Realized from simulated fills", NOT_APPLICABLE: "Not applicable",
};

const CODES: Record<string, string> = {
  QUOTE_STALE_OR_UNAVAILABLE: "Current quote is stale or unavailable", NO_GOVERNED_OPPORTUNITY: "No governed Opportunity",
  PAPER_AUTHORITY_UNAVAILABLE: "Paper authority unavailable", CANDIDATE_EXPIRED: "Candidate evidence expired", POSITION_SNAPSHOT_STALE: "Position snapshot is stale",
  PENDING_ORDER_REVALIDATION: "A Paper order is pending", SUPPORT_UNAVAILABLE: "Grounded support unavailable", DIRECTION_UNSUPPORTED: "Direction not supported by evidence",
  ENTRY_PLAN_UNAVAILABLE: "Entry plan unavailable", EXIT_PLAN_UNAVAILABLE: "Exit plan unavailable", HOLD_BASIS_UNAVAILABLE: "Hold basis unavailable",
  EXIT_CONDITION_NOT_MET: "No exit condition is met", ILLEGAL_POSITION_ACTION: "Action not valid for the current position",
  OPPORTUNITY_DIRECTION_MISMATCH: "Opportunity direction differs", SHORT_NOT_ALLOWED: "Short entries are not allowed", LOCAL_NOT_CONFIGURED: "No model is configured",
  SMA_TRAILING_STOP_BREACHED: "SMA trailing stop breached", SERVER_RISK_EXIT: "Server risk exit", MONOTONIC_CLAMP: "Stop held by monotonic clamp",
  PAPER_EXPERIMENT_REQUIRED: "No active Paper experiment — positions, fills and P&L are unavailable here",
  CANDIDATE_RUN_NOT_FOUND: "The AI Screener run is no longer available", POSITION_SNAPSHOT_UNAVAILABLE: "Position snapshot unavailable",
  DECISION_EPISODE_LINEAGE_UNAVAILABLE: "Some decisions could not be tied to a position episode", MARK_REFRESH_UNAVAILABLE: "Current marks could not be refreshed",
};
const CONDITIONS: Record<string, string> = {
  CURRENT_QUOTE: "Current quote available", DIRECTION_SUPPORTED: "Directional support", THESIS_CONTINUES: "Thesis continues", THESIS_REVERSED: "Thesis reversed",
  DECISION_EXPIRED: "Decision expired", SMA_TRAILING_STOP_BREACHED: "SMA trailing stop breached",
};
const humanize = (code: string) => code.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
/** Plain language first; the raw code stays available beside it. */
export const codeText = (code: string) => CODES[code] ?? humanize(code);
export const conditionText = (id: string | null) => (id && (CONDITIONS[id] ?? humanize(id))) || UNAVAILABLE;

export const money = (minor: number | null | undefined, currency: string) => formatMoney(minor, currency);
export const signedMoney = (minor: number | null | undefined, currency: string): SignedMoney => formatSignedMoney(minor, currency);
export const clock = (iso: string | null | undefined) => (iso ? etClock(iso) : UNAVAILABLE);
export const stamp = (iso: string | null | undefined) => formatStopTime(iso);
export const stopPrice = (value: string | null | undefined) => formatStopPrice(value);
export const quotePrice = (value: string | null | undefined) => (value == null || value === "" || !Number.isFinite(Number(value)) ? UNAVAILABLE : `$${Number(value).toFixed(2)}`);

export function ageText(ms: number | null | undefined): string {
  if (ms == null) return UNAVAILABLE;
  const seconds = Math.round(ms / 1000);
  return seconds < 90 ? `${seconds}s old` : seconds < 5400 ? `${Math.round(seconds / 60)}m old` : `${Math.round(seconds / 3600)}h old`;
}

/** Freshness as the evidence recorded it. Reference and publication-based inputs are never called current market data. */
export function freshnessText(item: { freshness_status?: string | null; delivery_mode?: string | null; role?: string | null }): string {
  const status = item.freshness_status ?? "UNAVAILABLE";
  const label = status === "PUBLICATION_CURRENT" ? "PUBLICATION-BASED" : status === "CURRENT_AS_FILED" ? "REFERENCE" : status.replace(/_/g, " ");
  const parts = [label];
  const mode = item.delivery_mode?.replace(/_/g, " ");
  if (mode && mode !== label.replace(/-/g, " ")) parts.push(mode);
  if (item.role === "REFERENCE_CONTEXT" && label !== "REFERENCE") parts.push("REFERENCE");
  return parts.join(" · ");
}

export const marketDataLabel = (mode: string) => mode === "LIVE_OBSERVATIONAL" ? "LIVE OBSERVATIONAL" : mode.replace(/_/g, " ");
export const evidenceCounts = (lifecycle: TradeLifecycle) => {
  const counts = lifecycle.candidate?.evidence.counts;
  return counts ? `${counts.supporting} supporting · ${counts.conflicting} conflicting · ${counts.weak} weak · ${counts.missing} missing · ${counts.blocked} blocked` : "Lineage unavailable";
};

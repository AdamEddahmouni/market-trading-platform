import type { OptionBrief, OptionsPayload, OptionsState } from "../../../api/screenerOptions";

/** Unavailable is "—", never zero. */
export const DASH = "—";
const compactFormat = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const expiryFormat = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" });
const expiryShort = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric" });
const etClock = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

export const price = (value: number | null | undefined) => value == null ? DASH : value.toFixed(2);
export const count = (value: number | null | undefined) => value == null ? DASH : value >= 10_000 ? compactFormat.format(value) : value.toLocaleString("en-US");
/** Provider IV is a decimal fraction: 0.2414 → 24.1 %. */
export const iv = (value: number | null | undefined) => value == null ? DASH : `${(value * 100).toFixed(1)}%`;
export const ratio = (value: number | null | undefined) => value == null ? DASH : value.toFixed(2);
/** Rounds to the display precision; a value that rounds to zero never shows as "-0.00". */
export const greek = (value: number | null | undefined, digits = 3) => {
  if (value == null) return DASH;
  const text = value.toFixed(digits);
  return Number(text) === 0 ? text.replace("-", "") : text;
};
export const pct = (value: number | null | undefined) => value == null ? DASH : `${value.toFixed(1)}%`;
/** Expiries are calendar dates; format in UTC so the day never shifts. */
export const expiry = (iso: string | null | undefined, short = false) => iso ? (short ? expiryShort : expiryFormat).format(new Date(`${iso}T00:00:00Z`)) : DASH;
export const etTime = (iso: string | null | undefined) => iso ? `${etClock.format(new Date(iso))} ET` : DASH;
export function ago(ms: number) {
  return ms < 60_000 ? `${Math.max(0, Math.round(ms / 1000))}s` : ms < 3_600_000 ? `${Math.round(ms / 60_000)}m` : `${Math.round(ms / 3_600_000)}h`;
}
/** The snapshot's own clock, advanced locally between polls. */
export function snapshotAge(payload: OptionsPayload, receivedAt: number, now = Date.now()) {
  return payload.clock ? payload.clock.age_ms + Math.max(0, now - receivedAt) : null;
}

export const OPTIONS_STATE_LABELS: Record<OptionsState, string> = {
  CURRENT_SNAPSHOT: "Current snapshot", STALE: "Stale", MARKET_CLOSED: "Market closed", NOT_CONFIGURED: "Not configured",
  NOT_ENTITLED: "Not entitled", PROVIDER_UNAVAILABLE: "Unavailable", NO_CHAIN: "No chain", UNAVAILABLE: "Unavailable",
};
/** Badge class: maps options states onto the shared panel badge palette. */
export const OPTIONS_BADGE: Record<OptionsState, string> = {
  CURRENT_SNAPSHOT: "CURRENT", STALE: "STALE", MARKET_CLOSED: "SESSION_CLOSED", NOT_CONFIGURED: "UNAVAILABLE",
  NOT_ENTITLED: "NOT_ENTITLED", PROVIDER_UNAVAILABLE: "UNAVAILABLE", NO_CHAIN: "UNAVAILABLE", UNAVAILABLE: "UNAVAILABLE",
};
const REASONS: Record<string, string> = {
  PROVIDER_NOT_CONFIGURED: "Options source not configured for this workstation.",
  FINVIZ_OPTIONS_AUTH_REJECTED: "Finviz Elite rejected the options export credential (not entitled or expired).",
  FINVIZ_RATE_LIMITED: "Finviz rate limit reached; the chain will be requested again shortly.",
  FINVIZ_OPTIONS_HTTP_ERROR: "Current option chain unavailable.", FINVIZ_OPTIONS_UNAVAILABLE: "Current option chain unavailable.",
  FINVIZ_OPTIONS_INVALID_RESPONSE: "Current option chain unavailable: the provider response was not a chain export.",
  NO_CURRENT_CONTRACTS: "No current option contracts returned for this instrument.",
  ONLY_EXPIRED_CONTRACTS: "No current option contracts returned for this instrument; only expired contracts were listed.",
  NON_CURRENT_PROVIDER_REFUSED: "Current option chain unavailable.",
  OPTIONS_MARKET_CLOSED: "Market closed · showing latest available options snapshot",
  SNAPSHOT_AGE_EXCEEDED: "Options snapshot stale",
};
/** Primary state line. Never a stack trace. */
export function stateMessage(payload: Pick<OptionsPayload, "state" | "reason">) {
  if (payload.state === "STALE") return payload.reason && payload.reason !== "SNAPSHOT_AGE_EXCEEDED"
    ? `Options snapshot stale · last refresh failed: ${REASONS[payload.reason] ?? payload.reason.replace(/_/g, " ").toLowerCase()}` : "Options snapshot stale";
  if (payload.state === "NOT_CONFIGURED") return REASONS.PROVIDER_NOT_CONFIGURED;
  if (payload.state === "NO_CHAIN") return REASONS[payload.reason ?? "NO_CURRENT_CONTRACTS"] ?? REASONS.NO_CURRENT_CONTRACTS;
  if (payload.state === "MARKET_CLOSED") return REASONS.OPTIONS_MARKET_CLOSED;
  if (payload.state === "CURRENT_SNAPSHOT") return "Current snapshot";
  return (payload.reason && REASONS[payload.reason]) || "Current option chain unavailable.";
}
export const hasChain = (state: OptionsState) => state === "CURRENT_SNAPSHOT" || state === "MARKET_CLOSED" || state === "STALE";

export function contractLabel(symbol: string, brief: Pick<OptionBrief, "expiration" | "strike" | "type">) {
  return `${symbol} ${expiry(brief.expiration, true)} ${brief.strike} ${brief.type === "CALL" ? "C" : "P"}`;
}

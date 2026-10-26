import type { ReactNode } from "react";
import { LOCAL_SUFFIX, LOCAL_ZONE } from "./localZone";

/**
 * Plain words and one time and number format for the Screener. A code shown as words keeps the raw code in `title`
 * so it can still be searched; a time reads in ET with UTC and the machine's own clock in `title`.
 */

export const ET_ZONE = "America/New_York";

// ------------------------------------------------------------------ codes
/** Words that stay in capitals when a code is read out. */
const ACRONYMS = new Set(["AI", "API", "CFTC", "CUSIP", "EDGAR", "EIA", "ET", "ETF", "ETFS", "FDIC", "FIGI", "FINRA", "FRED", "FRN",
  "FTD", "ID", "IBKR", "IMP", "ISIN", "L1", "L2", "NBBO", "NY", "OTC", "PE", "RSS", "RVOL", "SEC", "SOMA", "TIPS", "TTL", "US",
  "USD", "UTC"]);

/**
 * A code in words: `FUTURE_CONTRACT` → "Future contract", `XA01.UNDERLYING` → "Underlying",
 * `FUTURES_CONTEXT_MAP_V1` → "Futures context map v1". Domain maps call this as their fallback.
 */
export function codeWords(code: string | null | undefined): string {
  if (!code) return "";
  const words = code.trim().replace(/^[A-Z]{1,4}\d{1,3}\./, "").split(/[_.\s]+/).filter(Boolean).map((word) => {
    const upper = word.toUpperCase();
    if (/^V\d+$/.test(upper)) return `v${upper.slice(1)}`;
    if (upper === "OPEND") return "OpenD";
    if (ACRONYMS.has(upper)) return upper === "ETFS" ? "ETFs" : upper;
    return word.toLowerCase();
  });
  if (!words.length) return code;
  const [first, ...rest] = words;
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(" ");
}

/** Parts joined with " · ", skipping blanks and any part that repeats an earlier one ("Finviz · snapshot · snapshot"). */
export function distinctJoin(parts: ReadonlyArray<string | null | undefined | false>): string {
  const seen = new Set<string>();
  return parts.filter((part): part is string => Boolean(part)).filter((part) => {
    const key = part.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).join(" · ");
}

/** A code shown as words, with the code itself on hover. */
export function Code({ code, children, className }: { code: string | null | undefined; children?: ReactNode; className?: string }) {
  if (!code) return null;
  return <span className={className} title={code}>{children ?? codeWords(code)}</span>;
}

/** Exchange codes as traders say them: `US_CBOT` → "CBOT", `US_NASDAQ` → "NASDAQ". */
export const exchangeText = (code: string | null | undefined) => code ? code.replace(/^US_/, "").replace(/_/g, " ") : "";

const UNIVERSE_TEXT: Record<string, string> = { US_EQUITIES: "US Equities", FUTURES: "Futures", US_ETFS: "ETFs", BONDS: "Bonds", CRYPTO: "Crypto" };
/** A universe by the name its tab shows. */
export const universeText = (code: string | null | undefined) => code ? UNIVERSE_TEXT[code] ?? codeWords(code) : "";

// ------------------------------------------------------------------ filters
const OPERATOR_SYMBOL: Record<string, string> = { eq: "=", ne: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤", between: "", in: "in",
  not_in: "not in", contains: "contains" };
type FilterRule = { field: string; operator: string; value: unknown };
/** One filter as its chip reads: "Price ≥ $5", "Short Float > 20%". Without a catalog entry the field id reads as words. */
export function filterText(rule: FilterRule, definition?: { label?: string; unit?: string | null } | null): string {
  const operator = OPERATOR_SYMBOL[rule.operator] ?? rule.operator;
  const value = Array.isArray(rule.value) ? rule.value.join(rule.operator === "between" ? "–" : ", ") : String(rule.value);
  return `${definition?.label ?? codeWords(rule.field)} ${operator} ${definition?.unit === "USD" ? "$" : ""}${value}${definition?.unit === "percent" ? "%" : ""}`
    .replace(/\s+/g, " ").trim();
}
/** A whole filter set, or "no filters". */
export const filtersText = (rules: readonly FilterRule[], describe: (rule: FilterRule) => string = (rule) => filterText(rule)) =>
  rules.length ? rules.map(describe).join(" · ") : "no filters";

// ------------------------------------------------------------------ sessions
const SESSION_TEXT: Record<string, string> = {
  PREMARKET: "Pre-market", PRE_MARKET: "Pre-market", REGULAR: "Regular session", AFTER_HOURS: "After hours",
  OVERNIGHT: "Overnight", CLOSED: "Market closed", "24_7": "24/7", TRADING: "Trading", MAINTENANCE: "Maintenance break",
  MIXED: "Mixed sessions", PROVIDER_SPECIFIC: "Per contract", PUBLICATION_BASED: "Published data", UNAVAILABLE: "Unknown",
};
/** One label for a market session wherever it appears (header, footer, panels, Quick Preview). */
export const sessionText = (code: string | null | undefined) => code ? SESSION_TEXT[code] ?? codeWords(code) : "Unknown";
const SESSION_HINT: Record<string, string> = {
  MIXED: "The visible contracts are in different trading sessions; each row's quote shows its own.",
  PROVIDER_SPECIFIC: "Each futures contract trades on its own schedule; the visible rows report theirs.",
  PUBLICATION_BASED: "Bonds are reference data published on a schedule, not a live trading session.",
  "24_7": "Crypto trades continuously; there is no session.",
};
export const sessionHint = (code: string | null | undefined) => (code && SESSION_HINT[code]) || "Market session";

// ------------------------------------------------------------------ times
const etParts = new Intl.DateTimeFormat("en-US", { timeZone: ET_ZONE, year: "numeric", month: "short", day: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const utcParts = new Intl.DateTimeFormat("en-CA", { timeZone: "UTC", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const localParts = new Intl.DateTimeFormat("en-US", { timeZone: LOCAL_ZONE, month: "short", day: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });

const dateOnly = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric" });
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

const parts = (format: Intl.DateTimeFormat, at: Date) =>
  Object.fromEntries(format.formatToParts(at).map((item) => [item.type, item.value])) as Record<string, string>;
const moment = (iso: string | null | undefined) => {
  if (!iso) return null;
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? null : at;
};

/** "14:03:38 ET" (seconds), or "14:03 ET". */
export function etTimeText(iso: string | null | undefined, seconds = true): string {
  const at = moment(iso);
  if (!at) return "—";
  const p = parts(etParts, at);
  return `${p.hour}:${p.minute}${seconds ? `:${p.second}` : ""} ET`;
}

/**
 * The Screener's one timestamp format, always ET 24-hour: "14:03:38 ET" today, "Oct 21 14:03 ET" on another day,
 * "Oct 21, 2025 14:03 ET" in another year. An unparseable value is shown as given.
 */
export function stampText(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  // A date without a time is a calendar date, never midnight UTC moved into ET.
  if (DATE_ONLY.test(iso)) return dateOnly.format(new Date(`${iso}T12:00:00Z`));
  const at = moment(iso);
  if (!at) return iso;
  const p = parts(etParts, at);
  const today = parts(etParts, new Date(now));
  if (p.year === today.year && p.month === today.month && p.day === today.day) return `${p.hour}:${p.minute}:${p.second} ET`;
  return `${p.month} ${p.day}${p.year === today.year ? "" : `, ${p.year}`} ${p.hour}:${p.minute} ET`;
}

/** An epoch-milliseconds time as an ISO string, for the formatters above (never shown as is). */
export const msIso = (ms: number) => new Date(ms).toISOString();

/** UTC, and the machine's own clock when it is not ET: the tooltip of every Screener time. */
export function stampTitle(iso: string | null | undefined): string {
  if (iso && DATE_ONLY.test(iso)) return `Calendar date ${iso}`;
  const at = moment(iso);
  if (!at) return iso ?? "Time unavailable";
  const u = parts(utcParts, at);
  const utc = `${u.year}-${u.month}-${u.day} ${u.hour}:${u.minute}:${u.second} UTC`;
  if (LOCAL_ZONE === ET_ZONE || LOCAL_ZONE === "UTC") return utc;
  const l = parts(localParts, at);
  return `${utc} · ${l.month} ${l.day} ${l.hour}:${l.minute}:${l.second} ${LOCAL_SUFFIX} (this computer)`;
}

/** A timestamp as `<time>`: ET text, machine-readable value, UTC and local on hover. */
export function Stamp({ iso, now, fallback = "—" }: { iso: string | null | undefined; now?: number; fallback?: string }) {
  if (!iso) return <>{fallback}</>;
  return <time dateTime={iso} title={stampTitle(iso)}>{stampText(iso, now)}</time>;
}

// ------------------------------------------------------------------ numbers
/** Fixed decimals, so a column lines up (21.4 and 35.38 become 21.4 and 35.4); a nonzero value below the last place reads "<0.01". */
export function fixedText(value: number, digits: number): string {
  const step = 10 ** -digits;
  if (value !== 0 && Math.abs(value) < step / 2) return `${value < 0 ? "−" : ""}<${step.toFixed(digits)}`;
  return value.toFixed(digits);
}

/** Decimals per field, shared by the grid and Quick Preview. */
export const FIELD_DIGITS: Readonly<Record<string, number>> = {
  rsi_14: 1, rel_volume: 2, short_ratio: 2, pe: 2, fwd_pe: 2, bid_to_cover: 2,
};
export const fieldDigits = (field: string) => FIELD_DIGITS[field];

/** US prices: 2 decimals from $1, 4 below (a $0.0100 quote never reads 0.01). */
export const priceText = (value: number) => value.toFixed(Math.abs(value) >= 1 || value === 0 ? 2 : 4);

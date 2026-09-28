import type { BondItem, BondSource } from "../../../api/screenerBonds";

const dateFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });

/** An ISO calendar date (no time) shown as "Sep 30, 2033". */
export function isoDate(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = Date.parse(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isFinite(parsed) ? dateFormat.format(parsed) : value;
}

const humanize = (value: string) => value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, " ");

/** Unit-explicit formatting; a missing value is always an em dash, never zero. */
export function bondValue(value: number | string | null, unit: string): string {
  if (value === null || value === "") return "—";
  if (typeof value === "string") return unit === "date" ? isoDate(value) : unit === "state" ? humanize(value) : value;
  switch (unit) {
    case "percent": return `${value.toFixed(3)}%`;
    case "share_percent": return `${value.toFixed(1)}%`;
    case "per_100_par": return `${Number(value.toFixed(6))} per 100`;
    case "years": return `${value.toFixed(2)} yrs`;
    case "days": return `${Math.round(value).toLocaleString()} days`;
    case "USD_BILLIONS": return `$${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}B`;
    case "USD": return `$${compact.format(value)}`;
    case "ratio": return `${value.toFixed(2)}×`;
    case "bp": return `${value > 0 ? "+" : ""}${value.toFixed(1)} bp`;
    case "count": return Math.round(value).toLocaleString();
    case "index": return value.toFixed(5);
    default: return String(value);
  }
}

export const CLASS_LABEL: Record<BondItem["class"], string> = {
  OBSERVED: "Observed", DERIVED: "Derived", REFERENCE: "Reference", UNAVAILABLE: "Unavailable",
};

const SOURCE_LABEL: Record<string, string> = {
  US_TREASURY_FISCAL_DATA_AUCTIONS: "Treasury Fiscal Data · auctions", US_TREASURY_FISCAL_DATA_MSPD: "Treasury Fiscal Data · MSPD",
  US_TREASURY_DAILY_RATES: "U.S. Treasury daily rates", IMP_DERIVED: "IMP derived", IMP_XA01: "IMP identity",
  FINRA_TRACE: "FINRA TRACE", IMP: "IMP",
};
export const sourceLabel = (source: string | null) => (source && (SOURCE_LABEL[source] ?? source)) || "";

/** "Treasury Fiscal Data · auctions · Sep 9, 2026" — the value's own source and clock. */
export function provenance(item: Pick<BondItem, "source" | "as_of">) {
  const clock = item.as_of ? (item.as_of.length > 10 ? `retrieved ${new Date(item.as_of).toLocaleString()}` : isoDate(item.as_of)) : "";
  return [sourceLabel(item.source), clock].filter(Boolean).join(" · ");
}

const STATE_TEXT: Record<string, string> = {
  CURRENT: "Current", PUBLICATION_CURRENT: "Publication current", STALE: "Stale", NOT_CONFIGURED: "Not configured",
  UNAVAILABLE: "Unavailable", DEGRADED: "Degraded (last good)", PARTIAL: "Partial", FINRA_TERMS_REQUIRED: "Licence required",
};
export const sourceState = (source: BondSource) => STATE_TEXT[source.state ?? ""] ?? humanize(source.state ?? "UNAVAILABLE");
const REASON_TEXT: Record<string, string> = {
  IMP_TREASURY_LIVE_NOT_SET: "set IMP_TREASURY_LIVE=1", FRED_API_KEY_MISSING: "FRED API key not configured",
  IMP_FRED_LIVE_NOT_SET: "set IMP_FRED_LIVE=1", IMP_FINRA_LIVE_NOT_SET: "set IMP_FINRA_LIVE=1",
  FINRA_CREDENTIALS_MISSING: "FINRA credentials not configured", LICENSED_TRACE_FEED_REQUIRED: "licensed TRACE feed required",
};
export const reasonLabel = (reason: string | null | undefined) => (reason && (REASON_TEXT[reason] ?? reason.replace(/_/g, " ").toLowerCase())) || "";

import type { ReactNode } from "react";
import type { CongressMember, CongressTransaction, DisclosedAmount, ParticipantProvider } from "../../../api/screenerParticipants";

/** Plain-language states. A provider state is never presented as an absence of disclosures. */
const STATE_TEXT: Record<string, string> = {
  PUBLICATION_CURRENT: "Current publication", CURRENT_AS_FILED: "Current as filed", CURRENT: "Current", STALE: "Stale",
  PARTIAL: "Partial", PENDING: "Loading", NOT_CONFIGURED: "Not configured", LIVE_DISABLED: "Live data off",
  UNAVAILABLE: "Unavailable", SOURCE_ERROR: "Source error", NO_MATCH: "No exact match", NO_DISCLOSURES: "No disclosures",
  NOT_APPLICABLE: "Not applicable", NOT_LOADED: "Not loaded", SEE_ORDER_FLOW: "See Order Flow",
  // S14: Senate eFD access boundary and managed 13F index (refresh states say nothing about liveness).
  TERMS_ACCEPTANCE_REQUIRED: "Terms acceptance required", READY: "Imported", INDEX_INVALID: "Index invalid",
  REFRESHING: "Refreshing", REFRESH_AVAILABLE: "Update available", UNCHECKED: "Not checked", UNMANAGED: "Manual build",
};
export const stateText = (state: string) => STATE_TEXT[state] ?? state.replace(/_/g, " ").toLowerCase();

const REASON_TEXT: Record<string, string> = {
  IMP_EDGAR_LIVE_NOT_SET: "SEC EDGAR live access is off (IMP_EDGAR_LIVE)",
  SEC_USER_AGENT_NOT_SET: "SEC requires a User-Agent with a contact email (SEC_USER_AGENT)",
  IMP_PUBLIC_RECORDS_LIVE_NOT_SET: "Official public-record access is off (IMP_PUBLIC_RECORDS_LIVE)",
  SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE: "Senate eFD needs the operator to accept its terms and import reports",
  OPERATOR_ATTESTATION_MISSING: "Senate import has no operator terms-acceptance record", SENATE_EFD_IMPORT_DIR_MISSING: "Senate import folder not found",
  SOME_REPORTS_FAILED: "Some imported reports could not be read", NO_REPORT_PARSED: "No imported report could be read",
  SENATE_PARTIAL: "Some Senate reports could not be read", HOUSE_SOURCE_ERROR: "House source error; Senate shown",
  HOUSE_LIVE_DISABLED: "House access off; Senate shown", HOUSE_NOT_CONFIGURED: "House not configured; Senate shown",
  THIRTEEN_F_INDEX_NOT_BUILT: "Local 13F index not built",
  INDEX_ENDS_BEFORE_FILING_DEADLINE: "Index data sets end before this quarter's filing deadline",
  NEWER_SEC_DATASET_PUBLISHED: "A newer SEC data set is published", SERVING_PREVIOUS_GENERATION: "Refresh running; previous index served",
  NEVER_CHECKED: "Not yet checked against the SEC list", LAST_CHECK_OLDER_THAN_7_DAYS: "Last SEC check is over 7 days old",
  HOUSE_ONLY: "House disclosures only; Senate not imported",
  LOADING_DOCUMENTS: "Official documents still loading", LOADING_INDEX: "Official index loading", FETCHING: "Fetching",
  TICKER_NOT_IN_SEC_MAP: "Ticker not in the SEC company map", ISSUER_CUSIP_UNKNOWN: "Issuer CUSIP not known from a filing",
  ROOT_NOT_MAPPED_TO_A_CFTC_MARKET: "Root not mapped to a CFTC market", ENTITY_NAME_TOO_GENERIC: "Company name too generic to match",
  NO_COMPANY_NAME: "No company name to match", COMPACT_VIEW: "Open the panel to load", FILING_WINDOW_OPEN: "13F filing window still open",
  SOME_ROOTS_NOT_MAPPED_TO_A_CFTC_MARKET: "Some roots have no CFTC market",
  // S15 coverage decisions and CFTC data quality
  PRODUCT_NOT_COVERED: "Single-stock future; no COT market", NO_CFTC_MARKET_FOUND: "No CFTC market for this root",
  AMBIGUOUS_MAPPING: "Ambiguous CFTC market", EXCHANGE_MISMATCH: "Provider venue contradicts the CFTC exchange",
  ROOT_NOT_IN_COVERAGE_REGISTRY: "Root has no recorded CFTC coverage decision",
  SOME_ROOTS_UNCLASSIFIED: "Some roots have no recorded CFTC coverage decision",
  KNOWN_MARKET_NOT_IN_RECENT_RELEASES: "Known CFTC market; not in recent releases",
  CONFLICTING_DUPLICATE_ROWS: "Conflicting CFTC rows; values withheld",
  LEGACY_TEXT_FILING_NOT_PARSED: "Legacy text filing; open the source",
  NO_TRADE_PRINTS_FOR_UNIVERSE: "No trade prints for this universe",
  LIVE_SUBSCRIPTION_PANEL: "Live panel; participant unknown",
  UNIVERSE_INDEX_LOADING: "Universe catalog loading",
};
export const reasonText = (code: string | null | undefined) => (code ? REASON_TEXT[code] ?? code.replace(/_/g, " ").toLowerCase() : "");

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
export const money = (value: number | null | undefined) => (value == null ? "—" : usd.format(value));
export const count = (value: number | null | undefined) => (value == null ? "—" : whole.format(value));
export const signed = (value: number | null | undefined) => (value == null ? "—" : `${value > 0 ? "+" : ""}${whole.format(value)}`);
export const short = (value: number | null | undefined) => (value == null ? "—" : compact.format(value));
/** A disclosed band, never a point value. */
export const amountText = (amount: DisclosedAmount | null | undefined) => amount?.display ?? "Amount not parsed";
/** Timestamps print as UTC dates with time; dates print as given. */
export const stamp = (iso: string | null | undefined) => (iso ? iso.replace("T", " ").replace(/:\d\dZ$/, "Z").replace("Z", " UTC") : "—");

export const OWNER_TEXT: Record<string, string> = { SELF: "Member", SPOUSE: "Spouse", JOINT: "Joint", DEPENDENT_CHILD: "Dependent child" };
export const TYPE_TEXT: Record<string, string> = { PURCHASE: "Purchase", SALE: "Sale", SALE_PARTIAL: "Partial sale", EXCHANGE: "Exchange" };
export const FAMILY_TEXT: Record<string, string> = { INSIDER: "Insider · Form 4", BENEFICIAL_13D: "Beneficial owner · 13D",
  BENEFICIAL_13G: "Beneficial owner · 13G" };

export function StateTag({ state, reason }: { state: string; reason?: string | null }) {
  return <span className={`participant-state state-${state.toLowerCase()}`} title={reason ? reasonText(reason) : undefined}>{stateText(state)}</span>;
}

export function ClassTag({ value }: { value: "OBSERVED" | "DERIVED" | "INSUFFICIENT_EVIDENCE" }) {
  return <span className="news-class" title={value === "DERIVED" ? "Computed by IMP from official records" : value === "OBSERVED"
    ? "As published in the official record" : "Not enough evidence to state this"}>{value.replace("_", " ")}</span>;
}

export function Providers({ providers, label }: { providers: ParticipantProvider[]; label: string }) {
  return <ul className="news-provider-strip" aria-label={label}>{providers.map((provider) =>
    <li key={`${provider.id}-${provider.scope}`} className={`news-provider participant-provider state-${provider.state.toLowerCase()}`}
      title={[provider.reason ? reasonText(provider.reason) : null, provider.cadence, provider.fetched_at ? `Fetched ${stamp(provider.fetched_at)}` : "Not fetched",
        provider.published ? `Published ${provider.published}` : null, provider.item_count != null ? `${provider.item_count} items` : null]
        .filter(Boolean).join(" · ")}>
      <span>{provider.label}</span> <strong>{stateText(provider.state)}</strong></li>)}</ul>;
}

export function SourceLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>;
}

export function Boundaries({ items }: { items: string[] }) {
  return <ul className="participant-boundaries" aria-label="Evidence boundaries">{items.map((item) => <li key={item}>{item}</li>)}</ul>;
}

/** Seat (House) or chamber (Senate). */
const seatText = (member: CongressMember, chamber: string) => member.state_district || (chamber === "SENATE" ? "Senate" : "—");
/** Provenance for a member cell: the spelling as filed and how identity was established. */
export const memberTitle = (member: CongressMember) => [member.source_name && member.source_name !== member.name ? `Filed as: ${member.source_name}` : null,
  member.resolution ? `Identity: ${member.resolution.replace(/_/g, " ").toLowerCase()}${member.basis ? ` (${member.basis.replace(/_/g, " ").toLowerCase()})` : ""}` : null]
  .filter(Boolean).join(" · ") || undefined;

/** Congressional transactions as filed: clocks kept apart, bands never points, no member characterization. */
export function CongressTable({ rows, caption, showInstrument = true }: { rows: CongressTransaction[]; caption: string; showInstrument?: boolean }) {
  return <table className="news-table-plain participant-table"><caption className="sr-only">{caption}</caption>
    <thead><tr>{showInstrument && <th scope="col">Instrument</th>}<th scope="col">Member</th><th scope="col">Owner</th>
      <th scope="col">Type</th><th scope="col">Asset as disclosed</th><th scope="col">Amount (disclosed band)</th>
      <th scope="col">Transaction</th><th scope="col">Filed</th><th scope="col" title="DERIVED: calendar days from transaction to filing">Lag</th>
      <th scope="col">Source</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.id}>
      {showInstrument && <th scope="row">{row.instrument?.symbol ?? row.disclosed_ticker ?? "—"}{row.instrument?.is_option ? <small> · option</small> : null}</th>}
      <td title={memberTitle(row.member)}>{row.member.name} <small>({seatText(row.member, row.chamber)})</small></td>
      <td>{OWNER_TEXT[row.owner] ?? row.owner}</td>
      <td>{TYPE_TEXT[row.transaction_type] ?? row.transaction_type}</td>
      <td className="news-ellipsis" title={row.asset_description}>{row.asset_description}</td>
      <td>{amountText(row.amount)}</td>
      <td>{row.transaction_date ?? "—"}</td>
      <td title={`Available ${stamp(row.available_at)} (${row.available_basis.replace(/[._]/g, " ")})`}>{row.filing_date}</td>
      <td>{row.disclosure_lag_days == null ? "—" : `${row.disclosure_lag_days}d`}</td>
      <td><SourceLink href={row.source_url}>PTR</SourceLink></td>
    </tr>)}</tbody></table>;
}

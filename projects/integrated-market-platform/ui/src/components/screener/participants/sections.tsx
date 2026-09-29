import type { ReactNode } from "react";
import type { CongressTransaction, ParticipantInstrument, ParticipantSection, PositioningReport } from "../../../api/screenerParticipants";
import { amountText, ClassTag, CongressTable, count, memberTitle, money, reasonText, short, signed, SourceLink, stamp, StateTag, stateText } from "./participantFormat";

/** Section payload shapes (the API schema keeps sections open; these are what S12 sections carry). */
type Clocks = { accession: string; form_type: string; filing_date: string | null; accepted_at: string | null; available_at: string | null;
  available_basis: string; state: string; reason: string | null; source_url: string };
type InsiderTxn = { security_title: string; derivative: boolean; transaction_date: string | null; code: string; code_label: string;
  acquired_disposed: string | null; shares: number | null; price: number | null; shares_owned_after: number | null; ownership: string | null };
type InsiderFiling = Clocks & { owners: { name: string; roles: string[]; officer_title: string | null }[]; rule_10b5_1?: boolean | null;
  transactions: InsiderTxn[] };
type BeneficialFiling = Clocks & { schedule?: string; is_amendment?: boolean; event_date?: string | null; class_title?: string;
  reporting_persons: { name: string; aggregate_shares: number | null; percent_of_class: number | null; person_types: string[] }[];
  quality_flags?: string[] };
type Holder = { manager: string; shares: number; value_usd: number; filing_date: string; available_at: string; option_lines: number;
  prior_shares: number | null; change: { change: string | null; class: string; flags: string[]; delta_shares: number | null } };
type AwardRow = { family: string; award_id: string; modification: string | null; recipient_name: string; action_date: string | null;
  obligation_amount: number | null; award_type: string; description: string | null; awarding_agency: string;
  awarding_sub_agency: string | null; source_url: string };
type AwardFamily = { count: number; has_more: boolean; rows: AwardRow[]; recipients: string[]; obligation_sum: number | null };
type LobbyingFiling = { filing_uuid: string; filing_type_display: string; filing_year: number | null; filing_period: string;
  posted_at: string | null; registrant_name: string; client_name: string; self_filed: boolean; income: number | null;
  expenses: number | null; amount_note: string; issues: { code: string; label: string }[]; source_url: string };

const as = <T,>(section: ParticipantSection | undefined) => (section ?? { state: "UNAVAILABLE", reason: null }) as ParticipantSection & T;

export function Section({ title, state, reason, cls, children }: { title: string; state?: string; reason?: string | null;
  cls?: "OBSERVED" | "DERIVED"; children: ReactNode }) {
  return <section className="participant-section" aria-label={title}>
    <h3>{title}{cls ? <ClassTag value={cls} /> : null}{state ? <StateTag state={state} reason={reason} /> : null}</h3>{children}</section>;
}

/** Any non-content state explains itself; a provider state is never shown as "no disclosures". */
export function StateNote({ section, empty }: { section: ParticipantSection; empty: string }) {
  if (section.state === "NO_DISCLOSURES") return <p className="participant-note">{empty}</p>;
  if (["PUBLICATION_CURRENT", "CURRENT_AS_FILED", "CURRENT"].includes(section.state)) return null;
  return <p className="participant-note" role="status">{reasonText(section.reason) || "State"} · {section.state === "PENDING"
    ? "loading from the official source" : "this is a source state, not an absence of disclosures"}.</p>;
}

function FilingClock({ filing }: { filing: Clocks }) {
  return <span title={`Available ${stamp(filing.available_at)} (${filing.available_basis.replace(/_/g, " ").toLowerCase()})`}>
    {filing.accepted_at ? stamp(filing.accepted_at) : filing.filing_date ?? "—"}</span>;
}

export function Beneficial({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ filings?: BeneficialFiling[]; note?: string }>(section);
  const filings = data.filings ?? [];
  return <Section title="Beneficial owners · 13D / 13G" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty="No recent Schedule 13D or 13G about this issuer in the loaded filings." />
    {filings.length > 0 && <table className="news-table-plain participant-table"><caption className="sr-only">Schedule 13D and 13G filings</caption>
      <thead><tr><th scope="col">Form</th><th scope="col">Accepted</th><th scope="col">Event date</th><th scope="col">Reporting person</th>
        <th scope="col">% of class</th>{!compact && <th scope="col">Shares</th>}<th scope="col">Source</th></tr></thead>
      <tbody>{filings.map((filing) => filing.state !== "CURRENT_AS_FILED"
        ? <tr key={filing.accession}><th scope="row">{filing.form_type}</th><td><FilingClock filing={filing} /></td>
          <td colSpan={compact ? 3 : 4}>{reasonText(filing.reason)}</td><td><SourceLink href={filing.source_url}>Filing</SourceLink></td></tr>
        : filing.reporting_persons.map((person, index) => <tr key={`${filing.accession}-${index}`}>
          <th scope="row">{index === 0 ? filing.form_type : ""}</th><td>{index === 0 ? <FilingClock filing={filing} /> : ""}</td>
          <td>{index === 0 ? filing.event_date ?? "—" : ""}</td><td>{person.name}</td>
          <td>{person.percent_of_class == null ? "—" : `${person.percent_of_class}%`}</td>
          {!compact && <td>{count(person.aggregate_shares)}</td>}
          <td>{index === 0 ? <SourceLink href={filing.source_url}>Filing</SourceLink> : ""}</td></tr>))}</tbody></table>}
    {!compact && data.note && <p className="participant-note">{data.note}</p>}
  </Section>;
}

export function Insiders({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ filings?: InsiderFiling[]; code_counts?: { P: number; S: number; other: number }; note?: string }>(section);
  const filings = data.filings ?? [];
  return <Section title="Insiders · Form 4" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty="No recent Form 4 filings for this issuer." />
    {data.code_counts && filings.length > 0 && <p className="participant-note">Reported non-derivative codes in loaded filings <ClassTag value="DERIVED" />:
      {" "}P {data.code_counts.P} · S {data.code_counts.S} · other {data.code_counts.other}</p>}
    {filings.map((filing) => <div key={filing.accession} className="participant-filing">
      <h4>{filing.owners.map((owner) => `${owner.name}${owner.officer_title ? ` (${owner.officer_title})` : owner.roles.length ? ` (${owner.roles.join(", ")})` : ""}`).join("; ") || filing.form_type}
        {" "}· <FilingClock filing={filing} />{filing.rule_10b5_1 ? " · 10b5-1 plan" : ""} · <SourceLink href={filing.source_url}>Form {filing.form_type}</SourceLink></h4>
      {filing.state !== "CURRENT_AS_FILED" ? <p className="participant-note">{reasonText(filing.reason)}</p>
        : <table className="news-table-plain participant-table"><caption className="sr-only">Transactions reported on this Form 4</caption>
          <thead><tr><th scope="col">Date</th><th scope="col">Code</th><th scope="col">Shares</th><th scope="col">Price</th>
            {!compact && <><th scope="col">Owned after</th><th scope="col">Security</th></>}</tr></thead>
          <tbody>{filing.transactions.map((txn, index) => <tr key={index}><td>{txn.transaction_date ?? "—"}</td>
            <th scope="row" title={txn.code_label}>{txn.code}{txn.acquired_disposed ? ` (${txn.acquired_disposed})` : ""}{txn.derivative ? " · derivative" : ""}</th>
            <td>{count(txn.shares)}</td><td>{txn.price == null ? "not disclosed" : `$${txn.price}`}</td>
            {!compact && <><td>{count(txn.shares_owned_after)}{txn.ownership === "I" ? " (indirect)" : ""}</td>
              <td className="news-ellipsis" title={txn.security_title}>{txn.security_title}</td></>}</tr>)}</tbody></table>}
    </div>)}
    {!compact && data.note && <p className="participant-note">{data.note}</p>}
  </Section>;
}

export function RecentFilings({ section }: { section: ParticipantSection }) {
  const filings = (as<{ filings?: Clocks[] }>(section).filings ?? []);
  if (!filings.length) return null;
  return <Section title="Recent ownership filings" cls="OBSERVED">
    <ul className="participant-list">{filings.map((filing) => <li key={filing.accession}>
      <SourceLink href={filing.source_url}>{filing.form_type}</SourceLink> · <FilingClock filing={filing} /></li>)}</ul></Section>;
}

type IndexStatus = { refresh_state?: string; refresh_reason?: string | null; indexed_through?: string | null; generated_at?: string | null;
  source_dataset_count?: number; managed?: boolean };
const REFRESH_TEXT: Record<string, string> = { CURRENT_AS_FILED: "current for published SEC data sets", REFRESH_AVAILABLE: "update available",
  REFRESHING: "refreshing (previous index served)", SOURCE_ERROR: "SEC list unavailable", UNCHECKED: "not yet checked", INDEX_INVALID: "index invalid",
  UNMANAGED: "manual build (no refresh)", NOT_CONFIGURED: "not configured" };

/** S14: what the local 13F index holds and whether a newer published data set exists. Publication-driven, never live. */
function ThirteenFIndexStatus({ index, compact }: { index: IndexStatus; compact: boolean }) {
  if (!index.refresh_state) return null;
  const refresh = REFRESH_TEXT[index.refresh_state] ?? stateText(index.refresh_state);
  if (compact) return index.indexed_through ? <p className="participant-note">13F data sets indexed through {index.indexed_through} · {refresh}.</p> : null;
  return <p className="participant-note" aria-label="13F index status" title={index.refresh_reason ? reasonText(index.refresh_reason) : undefined}>
    13F index: data sets indexed through {index.indexed_through ?? "—"}{index.source_dataset_count ? ` (${index.source_dataset_count} data sets)` : ""}
    {" "}· generated {stamp(index.generated_at)} · refresh: {refresh}.</p>;
}

export function Holdings13F({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ period?: string; prior_period?: string | null; holder_count?: number; filing_deadline?: string;
    change_counts?: Record<string, number>; holders?: Holder[]; note?: string; source_url?: string; index?: IndexStatus }>(section);
  const holders = (data.holders ?? []).slice(0, compact ? 3 : undefined);
  return <Section title="13F holdings (quarter-end)" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty="No 13F lines for this issuer's CUSIP in the loaded quarters." />
    {data.index && <ThirteenFIndexStatus index={data.index} compact={compact} />}
    {data.period && <p className="participant-note">As of quarter end {data.period}{data.prior_period ? ` · compared with ${data.prior_period}` : ""} ·
      {" "}{count(data.holder_count)} reporting managers{data.state === "PARTIAL" ? ` · filing window open until ${data.filing_deadline}` : ""}.
      A quarter-end holding filed weeks later is not a live position.</p>}
    {data.change_counts && data.period && !compact && <p className="participant-note">Manager changes vs prior quarter <ClassTag value="DERIVED" />:
      {" "}{Object.entries(data.change_counts).map(([key, value]) => `${key.replace(/_/g, " ").toLowerCase()} ${count(value)}`).join(" · ")}</p>}
    {holders.length > 0 && <table className="news-table-plain participant-table"><caption className="sr-only">Largest reported 13F holders</caption>
      <thead><tr><th scope="col">Manager</th><th scope="col">Shares</th>{!compact && <th scope="col">Value</th>}
        <th scope="col">Change</th><th scope="col">Filed</th></tr></thead>
      <tbody>{holders.map((holder) => <tr key={holder.manager}><th scope="row" className="news-ellipsis" title={holder.manager}>{holder.manager}</th>
        <td>{short(holder.shares)}</td>{!compact && <td>{money(holder.value_usd)}</td>}
        <td title={holder.change.flags.join(", ") || undefined}>{holder.change.change ? holder.change.change.toLowerCase() : "insufficient evidence"}
          {holder.change.flags.includes("SPLIT_LIKE_RATIO") ? " · split-like" : ""}</td>
        <td title={`Available ${stamp(holder.available_at)}`}>{holder.filing_date}</td></tr>)}</tbody></table>}
    {!compact && data.note && <p className="participant-note">{data.note}</p>}
  </Section>;
}

export function LargeActivity({ section, onOpenOrderFlow }: { section: ParticipantSection; onOpenOrderFlow?: () => void }) {
  const data = as<{ method?: string }>(section);
  return <Section title="Large market activity (participant unknown)" state={data.state} reason={data.reason}>
    {data.state === "SEE_ORDER_FLOW" ? <>
      <p className="participant-note">{data.method}</p>
      {onOpenOrderFlow && <button type="button" className="screener-control" onClick={onOpenOrderFlow}>Open Order Flow</button>}
    </> : <p className="participant-note">{reasonText(data.reason)}.</p>}
  </Section>;
}

export function PositioningTable({ report, compact = false }: { report: PositioningReport; compact?: boolean }) {
  return <table className="news-table-plain participant-table"><caption className="sr-only">{report.report_label} categories for {report.root}</caption>
    <thead><tr><th scope="col">Category</th><th scope="col">Long</th><th scope="col">Short</th>{!compact && <th scope="col">Spreading</th>}
      <th scope="col" title="DERIVED: long − short">Net</th><th scope="col" title="CFTC published weekly change (long − short)">Net chg</th>
      {!compact && <th scope="col">Traders L / S</th>}</tr></thead>
    <tbody>{report.categories.map((item) => <tr key={item.id}><th scope="row">{item.label}</th><td>{count(item.long)}</td><td>{count(item.short)}</td>
      {!compact && <td>{count(item.spreading)}</td>}
      <td className={item.net == null ? "" : item.net > 0 ? "participant-positive" : item.net < 0 ? "participant-negative" : ""}>{signed(item.net)}</td>
      <td>{signed(item.net_change)}</td>
      {!compact && <td>{item.traders_long == null && item.traders_short == null ? "—" : `${count(item.traders_long)} / ${count(item.traders_short)}`}</td>}</tr>)}</tbody></table>;
}

export function FuturesPositioning({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ report?: PositioningReport; root?: string }>(section);
  const report = data.report;
  return <Section title="CFTC Commitments of Traders" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty="No public COT report for this root in the loaded window." />
    {report && <>
      <p className="participant-note">{report.market_name} · {report.report_label} · positions as of {report.report_date} · published {stamp(report.publication_time)}
        {" "}· open interest {count(report.open_interest)} ({signed(report.change_open_interest)})</p>
      <PositioningTable report={report} compact={compact} />
      {!compact && <p className="participant-note">{report.net_method} · <SourceLink href={report.source_url}>CFTC</SourceLink></p>}
    </>}
  </Section>;
}

type ChamberSource = { id: string; chamber: string; state: string; reason: string | null };
type HouseCoverage = { parsed?: number; partially_parsed?: number; scanned_unparsed?: number; failed?: number; loading?: number };

/** S14: each chamber's source state and read coverage, side by side (one failing source never hides the other). */
export function ChamberCoverage({ sources, house }: { sources: ChamberSource[]; house?: HouseCoverage | null }) {
  return <ul className="participant-list" aria-label="Congressional source coverage">{sources.map((source) => {
    const counts = source.chamber === "HOUSE" && house && ["PUBLICATION_CURRENT", "PARTIAL"].includes(source.state)
      ? [`${count(house.parsed)} parsed`, house.partially_parsed ? `${count(house.partially_parsed)} partly parsed` : null,
        `${count(house.scanned_unparsed)} scanned/unparsed`, house.failed ? `${count(house.failed)} unreadable` : null,
        house.loading ? `${count(house.loading)} loading` : null].filter(Boolean).join(" · ") : null;
    return <li key={source.id} title={source.reason ? reasonText(source.reason) : undefined}>
      {source.chamber === "HOUSE" ? "House" : "Senate"} · {stateText(source.state)}{counts ? ` · ${counts}` : ""}</li>;
  })}</ul>;
}

export function Congressional({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ transactions?: CongressTransaction[]; total?: number; window_days?: number; note?: string; chambers?: string[];
    sources?: ChamberSource[]; coverage?: { house?: HouseCoverage } }>(section);
  const rows = data.transactions ?? [];
  const chambers = (data.chambers ?? ["HOUSE"]).includes("SENATE") ? "House or Senate" : "House";
  return <Section title="Congressional disclosures" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty={`No ${chambers} transactions disclosing this ticker were filed in the last ${data.window_days ?? 90} days.`} />
    {data.sources && !compact && <ChamberCoverage sources={data.sources} house={data.coverage?.house} />}
    {data.sources && compact && data.sources.some((source) => source.state !== "PUBLICATION_CURRENT" && source.state !== "READY") &&
      <p className="participant-note">{data.sources.map((source) => `${source.chamber === "HOUSE" ? "House" : "Senate"}: ${stateText(source.state).toLowerCase()}`).join(" · ")}</p>}
    {rows.length > 0 && (compact ? <ul className="participant-list">{rows.map((row) => <li key={row.id} title={memberTitle(row.member)}>
      {row.member.name} · {row.transaction_type.replace("_", " ").toLowerCase()} · {amountText(row.amount)} · traded {row.transaction_date ?? "—"} · filed {row.filing_date}</li>)}</ul>
      : <CongressTable rows={rows} caption={`${chambers} transactions disclosing this ticker`} showInstrument={false} />)}
    {data.total != null && data.total > rows.length && <p className="participant-note">{data.total - rows.length} more in the panel.</p>}
    {!compact && data.note && <p className="participant-note">{data.note}</p>}
  </Section>;
}

function AwardTable({ family, compact }: { family: AwardFamily; compact: boolean }) {
  return <table className="news-table-plain participant-table"><caption className="sr-only">Federal award actions</caption>
    <thead><tr><th scope="col">Action date</th><th scope="col">Recipient (as named)</th><th scope="col">Agency</th>
      <th scope="col">Obligation (signed)</th>{!compact && <><th scope="col">Type</th><th scope="col">Action</th></>}<th scope="col">Source</th></tr></thead>
    <tbody>{family.rows.map((row) => <tr key={`${row.award_id}-${row.modification}-${row.action_date}`}><td>{row.action_date ?? "—"}</td>
      <th scope="row" className="news-ellipsis" title={row.recipient_name}>{row.recipient_name}</th>
      <td className="news-ellipsis" title={[row.awarding_agency, row.awarding_sub_agency].filter(Boolean).join(" · ")}>{row.awarding_sub_agency ?? row.awarding_agency}</td>
      <td>{money(row.obligation_amount)}</td>
      {!compact && <><td>{row.award_type}</td><td className="news-ellipsis" title={row.description ?? undefined}>{row.modification ? `Mod ${row.modification}` : "Award"}{row.description ? ` · ${row.description}` : ""}</td></>}
      <td><SourceLink href={row.source_url}>USAspending</SourceLink></td></tr>)}</tbody></table>;
}

export function Awards({ section, compact }: { section: ParticipantSection; compact: boolean }) {
  const data = as<{ families?: Record<string, AwardFamily>; window_days?: number; query?: string; published?: string | null;
    match?: { note: string }; sum_note?: string }>(section);
  const families = data.families ?? {};
  return <Section title="Federal awards" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty={`No contract or grant actions for "${data.query ?? ""}" in the last ${data.window_days ?? 90} days.`} />
    {(["contract", "grant"] as const).map((key) => {
      const family = families[key];
      if (!family) return null;
      return <div key={key}><h4>{key === "contract" ? "Contracts" : "Grants & assistance"} · {family.count} actions{family.has_more ? "+" : ""}
        {family.obligation_sum != null ? <> · sum {money(family.obligation_sum)} <ClassTag value="DERIVED" /></> : family.has_more ? " · not summed (more actions than listed)" : ""}</h4>
        {family.rows.length > 0 && <AwardTable family={family} compact={compact} />}</div>;
    })}
    {!compact && <p className="participant-note">{data.match?.note} {data.sum_note} Published {data.published ?? "—"}. An award is not revenue and not a signal.</p>}
  </Section>;
}

export function Lobbying({ section }: { section: ParticipantSection }) {
  const data = as<{ filings?: LobbyingFiling[]; total_filings?: number; top_issues?: { label: string; filings: number }[];
    clients?: string[]; match?: { note: string } }>(section);
  const filings = data.filings ?? [];
  return <Section title="Lobbying disclosures (LDA)" state={data.state} reason={data.reason} cls="OBSERVED">
    <StateNote section={data} empty="No LDA filings name this company as a client this year or last." />
    {filings.length > 0 && <>
      <p className="participant-note">{data.total_filings} filings this year and last · issues as filed: {(data.top_issues ?? []).map((item) => `${item.label} (${item.filings})`).join(", ")}</p>
      <table className="news-table-plain participant-table"><caption className="sr-only">Lobbying filings</caption>
        <thead><tr><th scope="col">Period</th><th scope="col">Registrant</th><th scope="col">Client (as filed)</th>
          <th scope="col">Income</th><th scope="col">Expenses</th><th scope="col">Source</th></tr></thead>
        <tbody>{filings.map((filing) => <tr key={filing.filing_uuid}><td>{filing.filing_year} {filing.filing_type_display}</td>
          <th scope="row" className="news-ellipsis" title={filing.registrant_name}>{filing.registrant_name}{filing.self_filed ? " (in-house)" : ""}</th>
          <td className="news-ellipsis" title={filing.client_name}>{filing.client_name}</td>
          <td title={filing.amount_note}>{money(filing.income)}</td><td title={filing.amount_note}>{money(filing.expenses)}</td>
          <td><SourceLink href={filing.source_url}>Filing</SourceLink></td></tr>)}</tbody></table>
      <p className="participant-note">Income (outside firms) and expenses (in-house, including payments to firms) are never added together. {data.match?.note} Lobbying is activity, not government support.</p>
    </>}
  </Section>;
}

export function Provenance({ data }: { data: ParticipantInstrument }) {
  const identity = data.identity;
  return <Section title="Provenance">
    <ul className="participant-list">{data.providers.map((provider) => <li key={`${provider.id}-${provider.scope}`}>
      <span>{provider.label}</span> <StateTag state={provider.state} reason={provider.reason} />
      <small>{provider.reason ? ` · ${reasonText(provider.reason)}` : ""} · {provider.cadence}{provider.fetched_at ? ` · fetched ${stamp(provider.fetched_at)}` : ""}
        {provider.published ? ` · published ${provider.published}` : ""}{provider.source_url ? <> · <SourceLink href={provider.source_url}>source</SourceLink></> : null}</small></li>)}</ul>
    {identity && (identity.cik || identity.cusips.length > 0) && <p className="participant-note">Identity: ticker {identity.ticker ?? "—"}{identity.cik ? ` · SEC CIK ${identity.cik}` : ""}
      {identity.cusips.length ? ` · CUSIP ${identity.cusips.join(", ")} (from a 13D/13G cover page)` : ""}</p>}
    <ul className="participant-boundaries" aria-label="Evidence boundaries">{data.boundaries.map((item) => <li key={item}>{item}</li>)}</ul>
    {data.neutrality_note && <p className="participant-note">{data.neutrality_note}</p>}
  </Section>;
}

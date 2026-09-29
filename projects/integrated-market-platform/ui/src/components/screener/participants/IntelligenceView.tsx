import { useQuery } from "@tanstack/react-query";
import type { ScreenerUniverse } from "../../../api/screener";
import { CONGRESS_WINDOWS, fetchCongressView, fetchOwnershipView, fetchPositioningView, OWNERSHIP_WINDOWS,
  PARTICIPANT_PAGE_LIMIT, type ParticipantProvider } from "../../../api/screenerParticipants";
import { CongressTable, count, FAMILY_TEXT, Providers, reasonText, signed, SourceLink, stamp, StateTag, TYPE_TEXT } from "./participantFormat";
import { ChamberCoverage } from "./sections";
import type { IntelView } from "./participantParams";
import { CoverageSummary, PositioningFlags, PositioningTable, UnmappedRoots } from "./sections";
import "../news/news.css";
import "./participants.css";

type Props = {
  universe: ScreenerUniverse;
  universeLabel: string;
  view: IntelView;
  search: string;
  onUpdate: (updates: Record<string, string | null>) => void;
};
const REFRESH_MS = 5 * 60_000;

function Notice({ state, reason, providers }: { state: string; reason: string | null; providers: ParticipantProvider[] }) {
  if (["CURRENT_AS_FILED", "PUBLICATION_CURRENT", "NO_DISCLOSURES"].includes(state)) return null;
  const degraded = providers.filter((item) => !["CURRENT", "CURRENT_AS_FILED", "PUBLICATION_CURRENT"].includes(item.state));
  return <div className={`news-notice ${state === "SOURCE_ERROR" ? "error" : "warn"}`} role="status">
    <StateTag state={state} reason={reason} /> {reasonText(reason)}{degraded.length ? ` · ${degraded.map((item) => `${item.label}: ${reasonText(item.reason) || item.state.toLowerCase()}`).join("; ")}` : ""}.
    {state === "LIVE_DISABLED" || state === "NOT_CONFIGURED" ? " This is a source state, not an absence of disclosures." : ""}</div>;
}

function Pager({ offset, total, hasMore, onPage }: { offset: number; total: number; hasMore: boolean; onPage: (offset: number) => void }) {
  if (!total) return null;
  return <div className="participant-pager" role="group" aria-label="Pages">
    <span>{offset + 1}–{Math.min(offset + PARTICIPANT_PAGE_LIMIT, total)} of {count(total)}</span>
    <button type="button" className="screener-control" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - PARTICIPANT_PAGE_LIMIT))}>Previous</button>
    <button type="button" className="screener-control" disabled={!hasMore} onClick={() => onPage(offset + PARTICIPANT_PAGE_LIMIT)}>Next</button>
  </div>;
}

function Loading({ error, retry, label }: { error: boolean; retry: () => void; label: string }) {
  return error ? <div className="news-message error" role="alert">{label} request failed. <button type="button" onClick={retry}>Retry</button></div>
    : <div className="news-message" role="status">Loading {/^[A-Z]{2}/.test(label) ? label : label.charAt(0).toLowerCase() + label.slice(1)}…</div>;
}

/** The previous page stays visible (and its filter options usable) while the next one loads. */
const Updating = () => <div className="news-notice" role="status">Updating for the new window, filters, or page…</div>;

function OwnershipPane({ universe, params, onUpdate }: { universe: ScreenerUniverse; params: URLSearchParams; onUpdate: Props["onUpdate"] }) {
  const windowId = params.get("iwin") ?? "5d";
  const family = params.get("ifam");
  const sort = params.get("isort") ?? "latest";
  const offset = Number(params.get("ioff") ?? 0) || 0;
  const query = useQuery({
    queryKey: ["screener-participants-ownership", universe, windowId, family, sort, offset],
    queryFn: ({ signal }) => fetchOwnershipView({ universe, window: windowId, family, sort, offset }, signal),
    staleTime: 60_000, retry: 1, refetchInterval: (current) => current.state.data?.state === "PENDING" ? 10_000 : REFRESH_MS,
    placeholderData: (previous) => (previous?.universe === universe ? previous : undefined),
  });
  const data = query.data && query.data.universe === universe ? query.data : undefined;
  return <>
    <div className="news-controls" role="group" aria-label="Institutional view controls">
      <label>Filed within <select aria-label="Ownership window" value={windowId} onChange={(event) => onUpdate({ iwin: event.target.value, ioff: null })}>
        {OWNERSHIP_WINDOWS.map((item) => <option key={item} value={item}>{item.replace("d", "")} business day{item === "1d" ? "" : "s"}</option>)}</select></label>
      <label>Filing <select aria-label="Filing family" value={family ?? ""} onChange={(event) => onUpdate({ ifam: event.target.value || null, ioff: null })}>
        <option value="">All families</option>{(data?.families ?? [{ id: "INSIDER", label: "Insider (Form 4)" }, { id: "BENEFICIAL_13D", label: "Beneficial owner 13D" },
          { id: "BENEFICIAL_13G", label: "Beneficial owner 13G" }]).map((item) => <option key={item.id} value={item.id}>{item.label}
          {data?.family_counts?.[item.id] != null ? ` (${data.family_counts[item.id]})` : ""}</option>)}</select></label>
      <label>Sort <select aria-label="Ownership sort" value={sort} onChange={(event) => onUpdate({ isort: event.target.value, ioff: null })}>
        {(data?.sorts ?? [{ id: "latest", label: "Latest filed" }, { id: "symbol", label: "Symbol" }]).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
    </div>
    {!data ? <Loading error={query.isError} retry={() => void query.refetch()} label="Institutional filings" /> : <>
      <div className="news-status-strip"><Providers providers={data.providers} label="Institutional sources" /></div>
      <Notice state={data.state} reason={data.reason} providers={data.providers} />
      {query.isPlaceholderData && <Updating />}
      <div className="participant-body" tabIndex={0} role="region" aria-label="Ownership filings">
        {data.rows.length ? <table className="news-table-plain participant-table"><caption className="sr-only">SEC ownership filings for this universe</caption>
          <thead><tr><th scope="col">Filed</th><th scope="col">Symbol</th><th scope="col">Filing</th><th scope="col">Issuer (as indexed)</th>
            <th scope="col">Filer(s)</th><th scope="col">Match</th><th scope="col">Source</th></tr></thead>
          <tbody>{data.rows.map((row) => <tr key={`${row.accession}-${row.instrument.instrument_id}`}><td>{row.filed_date}</td>
            <th scope="row">{row.instrument.symbol}</th><td>{FAMILY_TEXT[row.family] ?? row.family}{row.is_amendment ? " · amendment" : ""}</td>
            <td className="news-ellipsis" title={row.issuer_name}>{row.issuer_name}</td>
            <td className="news-ellipsis" title={row.filers.join("; ")}>{row.filers.slice(0, 2).join("; ") || "—"}{row.filer_count > 2 ? ` +${row.filer_count - 2}` : ""}</td>
            <td title={row.match.role_basis === "ROLE_UNVERIFIED" ? "Two listed companies are on this filing; open it to confirm which is the subject" : "SEC CIK"}>
              {row.match.confidence === "MATCH_EXACT" ? "CIK exact" : "role unverified"}</td>
            <td><SourceLink href={row.source_url}>EDGAR</SourceLink></td></tr>)}</tbody></table>
          : data.state === "NO_DISCLOSURES" || data.state === "CURRENT_AS_FILED" ? <p className="news-message">No Form 4, 13D, or 13G filings for this universe in the window{family ? " for this family" : ""}.</p> : null}
        <p className="participant-note">{data.time_note}</p>
        {data.coverage && <p className="participant-note">Coverage: {count(data.coverage.instruments_with_cik as number)} of {count(data.coverage.universe_instruments as number)} instruments have an SEC CIK · daily indexes {(data.coverage.days as string[]).join(", ")}.</p>}
        <ul className="participant-boundaries" aria-label="Evidence boundaries">{data.boundaries.slice(0, 1).map((item) => <li key={item}>{item}</li>)}
          <li>A Form 4 is one insider's reported transaction; a 13D/13G reports a holder's stake as of its event date. Neither is a view on the stock.</li></ul>
      </div>
      <Pager offset={data.offset} total={data.result_count} hasMore={data.has_more && !query.isPlaceholderData} onPage={(next) => onUpdate({ ioff: next ? String(next) : null })} />
    </>}
  </>;
}

function CongressPane({ universe, params, onUpdate }: { universe: ScreenerUniverse; params: URLSearchParams; onUpdate: Props["onUpdate"] }) {
  const windowId = params.get("iwin") ?? "60d";
  const type = params.get("itype");
  const minAmount = Number(params.get("iamt") ?? 0) || null;
  const member = params.get("imem");
  const sort = params.get("isort") ?? "filed";
  const offset = Number(params.get("ioff") ?? 0) || 0;
  const query = useQuery({
    queryKey: ["screener-participants-congress", universe, windowId, type, minAmount, member, sort, offset],
    queryFn: ({ signal }) => fetchCongressView({ universe, window: windowId, type, minAmount, member, sort, offset }, signal),
    staleTime: 60_000, retry: 1,
    refetchInterval: (current) => (current.state.data?.coverage as { loading?: number } | undefined)?.loading || current.state.data?.state === "PENDING" ? 10_000 : REFRESH_MS,
    placeholderData: (previous) => (previous?.universe === universe ? previous : undefined),
  });
  const data = query.data && query.data.universe === universe ? query.data : undefined;
  const coverage = (data?.coverage ?? {}) as Record<string, number | string[] | null>;
  return <>
    <div className="news-controls" role="group" aria-label="Congress view controls">
      <label>Filed within <select aria-label="Congress window" value={windowId} onChange={(event) => onUpdate({ iwin: event.target.value, ioff: null })}>
        {CONGRESS_WINDOWS.map((item) => <option key={item} value={item}>{item.replace("d", "")} days</option>)}</select></label>
      <label>Type <select aria-label="Transaction type" value={type ?? ""} onChange={(event) => onUpdate({ itype: event.target.value || null, ioff: null })}>
        <option value="">All types</option>{(data?.filters.transaction_types ?? []).map((item) => <option key={item.id} value={item.id}>{TYPE_TEXT[item.id] ?? item.id} ({item.count})</option>)}</select></label>
      <label>Disclosed band from <select aria-label="Minimum disclosed amount" value={minAmount ?? ""} onChange={(event) => onUpdate({ iamt: event.target.value || null, ioff: null })}>
        <option value="">Any</option>{(data?.filters.amount_floors ?? []).map((item) => <option key={item} value={item}>${count(item)}+</option>)}</select></label>
      <label>Member <select aria-label="Member" value={member ?? ""} onChange={(event) => onUpdate({ imem: event.target.value || null, ioff: null })}>
        <option value="">All members</option>{(data?.filters.members ?? []).map((item) => <option key={item.id} value={item.id}
          title={item.filed_as && item.filed_as.length > 1 ? `Filed as: ${item.filed_as.join("; ")}` : undefined}>{item.name} ({item.state_district || (item.chamber === "SENATE" ? "Senate" : "—")})</option>)}</select></label>
      <label>Sort <select aria-label="Congress sort" value={sort} onChange={(event) => onUpdate({ isort: event.target.value, ioff: null })}>
        {(data?.sorts ?? [{ id: "filed", label: "Latest filed" }]).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
    </div>
    {!data ? <Loading error={query.isError} retry={() => void query.refetch()} label="Congressional disclosures" /> : <>
      <div className="news-status-strip"><Providers providers={data.providers} label="Congressional sources" /></div>
      <Notice state={data.state} reason={data.reason} providers={data.providers} />
      {query.isPlaceholderData && <Updating />}
      <div className="participant-body" tabIndex={0} role="region" aria-label="Congressional disclosures">
        {data.rows.length ? <CongressTable rows={data.rows} caption={`Congressional transactions in this universe filed since ${data.window.since}`} />
          : ["PUBLICATION_CURRENT", "PARTIAL", "NO_DISCLOSURES"].includes(data.state) ? <p className="news-message">No disclosed transactions match this universe and these filters.</p> : null}
        <p className="participant-note">Coverage: {count(coverage.filings as number)} House PTR filings in the window · {count(coverage.parsed as number)} machine-readable ·
          {" "}{count(coverage.not_machine_readable as number)} scanned (open on the Clerk site){coverage.loading ? ` · ${coverage.loading} still loading` : ""} ·
          {" "}{count(coverage.matched as number)} transactions match this universe · {count(coverage.ticker_outside_universe as number)} name other tickers ·
          {" "}{count(coverage.no_disclosed_ticker as number)} have no ticker.</p>
        <ChamberCoverage sources={data.providers.filter((item) => item.family === "CONGRESSIONAL").map((item) => ({ id: item.id,
          chamber: item.id === "senate_efd" ? "SENATE" : "HOUSE", state: item.state, reason: item.reason }))}
          house={coverage.house as { parsed?: number } | undefined} />
        <p className="participant-note">{data.time_note}</p>
        <p className="participant-note">{data.neutrality_note}</p>
        <ul className="participant-boundaries" aria-label="Evidence boundaries">{data.boundaries.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <Pager offset={data.offset} total={data.result_count} hasMore={data.has_more && !query.isPlaceholderData} onPage={(next) => onUpdate({ ioff: next ? String(next) : null })} />
    </>}
  </>;
}

function PositioningPane({ universe }: { universe: ScreenerUniverse }) {
  const query = useQuery({
    queryKey: ["screener-participants-positioning", universe],
    queryFn: ({ signal }) => fetchPositioningView(universe, signal), staleTime: 60_000, retry: 1,
    refetchInterval: (current) => current.state.data?.state === "PENDING" ? 10_000 : REFRESH_MS,
  });
  const data = query.data && query.data.universe === universe ? query.data : undefined;
  if (!data) return <Loading error={query.isError} retry={() => void query.refetch()} label="CFTC positioning" />;
  return <>
    <div className="news-status-strip"><Providers providers={data.providers} label="Positioning sources" /></div>
    <Notice state={data.state} reason={data.reason} providers={data.providers} />
    <div className="participant-body" tabIndex={0} role="region" aria-label="CFTC positioning by root">
      {data.coverage.breakdown && <CoverageSummary coverage={data.coverage} />}
      {data.groups.map((group) => group.rows.length > 0 && <section key={group.report} className="participant-section" aria-label={group.label}>
        <h3>{group.label}</h3>
        {group.rows.map((report) => <div key={report.root} className="participant-filing">
          <h4>{report.root} · {report.market_name} · as of {report.report_date} · published {stamp(report.publication_time)} · OI {count(report.open_interest)}</h4>
          {report.contract && <p className="participant-note">{report.contract} · CFTC {report.cftc_contract_market_code}
            {report.mapping ? ` · mapped by ${report.mapping.basis.replace(/_/g, " ").toLowerCase()}` : ""}
            {" "}· OI weekly change {signed(report.change_open_interest)} (published)</p>}
          <PositioningFlags report={report} />
          <PositioningTable report={report} compact={!report.contract} /></div>)}</section>)}
      {(data.coverage.mapped_without_report ?? []).length > 0 && <p className="participant-note">Known CFTC markets with no public report in the
        {" "}loaded window (below the CFTC reporting threshold): {data.coverage.mapped_without_report?.join(", ")}.</p>}
      {data.unmapped ? data.unmapped.length > 0 && <UnmappedRoots roots={data.unmapped} />
        : data.coverage.unmapped_roots.length > 0 && <p className="participant-note">No CFTC market mapped for: {data.coverage.unmapped_roots.join(", ")}.</p>}
      {data.report_policy && <p className="participant-note">{data.report_policy}</p>}
      <p className="participant-note">{data.time_note} Categories of the two reports differ and are never mapped onto each other.</p>
      <ul className="participant-boundaries" aria-label="Evidence boundaries">{data.boundaries.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  </>;
}

/** Universe-wide intelligence view: filings and disclosures as published, with their own clocks and states. */
export default function IntelligenceView({ universe, universeLabel, view, search, onUpdate }: Props) {
  const params = new URLSearchParams(search);
  const title = view === "ownership" ? "Institutional filings" : view === "congress" ? "Congressional disclosures" : "CFTC positioning";
  return <section className="participant-view" aria-label={`${title} · ${universeLabel}`}>
    {view === "ownership" ? <OwnershipPane universe={universe} params={params} onUpdate={onUpdate} />
      : view === "congress" ? <CongressPane universe={universe} params={params} onUpdate={onUpdate} />
      : <PositioningPane universe={universe} />}
  </section>;
}

import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchRatesCurve, type FredItem, type NyFedRate, type RatesCurvePayload } from "../../../api/screenerBonds";
import { bondValue, isoDate, reasonLabel, sourceState } from "../bonds/bondFormat";
import { CurveChart } from "../bonds/CurveChart";
import { ErrorDetail, PanelFrame, PanelMessage, usePanelVisible, useSelection } from "./shared";

const SHAPES: Record<string, string> = { UPWARD_SLOPING: "Upward sloping", INVERTED: "Inverted", FLAT_OR_MIXED: "Flat or mixed", UNAVAILABLE: "Unavailable" };
const SPREAD_LABELS: Record<string, string> = { "2s10s": "2s10s", "3m10y": "3m10y", "5s30s": "5s30s", "10s30s": "10s30s" };

function Selected({ data }: { data: RatesCurvePayload }) {
  const selected = data.selected;
  if (!selected) return <p className="screener-panel-note">Select a security to place it on the curve.</p>;
  const reference = selected.reference;
  const auction = selected.auction_yield.value != null ? selected.auction_yield : selected.auction_real_yield;
  const treasury = !selected.category || selected.category === "Treasury";
  const spread = selected.spread;
  return <dl className="bond-panel-list">
    <div><dt>{selected.cusip}</dt><dd>{selected.description}{selected.category && <small>{selected.category}</small>}</dd></div>
    <div><dt>Maturity</dt><dd>{isoDate(selected.maturity)} · {bondValue(selected.years_to_maturity, "years")}</dd></div>
    <div><dt>Matched reference</dt><dd>{reference.state === "REFERENCE"
      ? <>{reference.tenor} {reference.curve === "REAL_PAR" ? "real" : "nominal"} par {bondValue(reference.value ?? null, "percent")} <small>nearest published tenor · {isoDate(reference.publication_date)} · not this security&apos;s yield</small></>
      : <span className="screener-muted">{reasonLabel(reference.reason)}</span>}</dd></div>
    {selected.indicative && <div><dt>Closing bid (on-the-run bill)</dt><dd>{bondValue(selected.indicative.value, "percent")} <small>coupon-equivalent · Treasury daily bill rates · {isoDate(selected.indicative.as_of)}</small></dd></div>}
    {treasury && <div><dt>Latest auction yield</dt><dd>{bondValue(auction.value, "percent")} <small>{auction.basis === "REAL_HIGH_YIELD" ? "real · " : auction.basis === "HIGH_INVESTMENT_RATE" ? "investment rate · " : ""}auction {isoDate(auction.as_of)}</small></dd></div>}
    {spread.state === "DERIVED"
      ? <div><dt>Spread at observed price</dt><dd title={spread.note}>{bondValue(spread.value, "bp")} <small>yield {bondValue(spread.yield, "percent")} at {spread.price.toFixed(3)} ({spread.price_kind.replace(/_/g, " ").toLowerCase()}, {isoDate(spread.operation_date)}) vs {spread.curve === "REAL_PAR" ? "real" : "nominal"} par {bondValue(spread.par_yield, "percent")} interpolated {spread.tenors.join("–")} · {isoDate(spread.curve_date)} · dated, not current</small></dd></div>
      : <div><dt>Spread to benchmark</dt><dd className="screener-muted" title={spread.note}>— {spread.note}</dd></div>}
  </dl>;
}

function Fred({ title, items, state, reason, note }: { title: string; items: FredItem[]; state: string; reason: string | null; note?: string }) {
  return <section className="bond-panel-section" aria-label={title}>
    <h3>{title}</h3>
    {!items.length ? <p className="screener-panel-note">FRED {state === "NOT_CONFIGURED" ? "not configured" : state.toLowerCase().replace(/_/g, " ")}{reason ? ` · ${reasonLabel(reason)}` : ""}.</p> :
      <dl className="bond-panel-list">{items.map((item) => <div key={item.id} title={`${item.series_id} · ${item.source_agency} · knowledge from ${item.knowledge_start_date ?? "unknown"}`}>
        <dt>{item.title}</dt><dd>{item.value == null ? "—" : item.units === "Percent" ? `${item.value.toFixed(2)}%` : item.value.toFixed(2)} <small>{item.frequency} · {isoDate(item.observation_date)}{item.usage_rights !== "internal_research" ? " · licensed index" : ""}</small></dd></div>)}</dl>}
    {note && <p className="screener-panel-note">{note}</p>}
  </section>;
}

function NyFed({ data }: { data: RatesCurvePayload }) {
  const rates: NyFedRate[] = data.nyfed?.items ?? [];
  const soma = data.soma;
  return <section className="bond-panel-section" aria-label="Money-market reference rates">
    <h3>Reference rates (NY Fed)</h3>
    {!rates.length ? <p className="screener-panel-note">NY Fed rates {(data.nyfed?.state ?? "unavailable").toLowerCase().replace(/_/g, " ")}{data.nyfed?.reason ? ` · ${reasonLabel(data.nyfed.reason)}` : ""}.</p> :
      <dl className="bond-panel-list">{rates.map((item) => <div key={item.id} title={item.label}>
        <dt>{item.id}</dt><dd>{item.value.toFixed(2)}% <small>{isoDate(item.effective_date)}{item.volume_billions != null ? ` · $${item.volume_billions.toLocaleString()}B volume` : ""}{item.target_from != null && item.target_to != null ? ` · target ${item.target_from.toFixed(2)}–${item.target_to.toFixed(2)}%` : ""}</small></dd></div>)}</dl>}
    {soma && soma.as_of && <p className="screener-panel-note">SOMA holdings as of {isoDate(soma.as_of)}: {Object.entries(soma.counts).map(([kind, count]) => `${count.toLocaleString()} ${kind}`).join(" · ")} (by CUSIP; shown per security in Quick Preview).</p>}
  </section>;
}

export default function RatesCurvePanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  // Curve context loads without a selection; a selection only adds its placement.
  const instrument = row && settledId === row.instrument.instrument_id ? settledId : null;
  const query = useQuery({
    queryKey: ["screener-rates-curve", universe, instrument],
    queryFn: ({ signal }) => fetchRatesCurve(instrument, signal),
    enabled: universe === "BONDS" && visible, staleTime: 120_000, refetchInterval: visible ? 600_000 : false, retry: 1,
    placeholderData: (previous) => previous,
  });
  // Stale-response protection: a curve fetched for another selection never labels this one.
  const data = query.data && query.data.instrument_id === instrument ? query.data : query.data && !instrument ? query.data : undefined;
  const pending = Boolean(row) && settledId !== row?.instrument.instrument_id;
  const nominal = data?.nominal;
  const reference = data?.selected?.reference;
  return <PanelFrame id="rates_curve" detail={nominal?.publication_date ? `U.S. Treasury par curves · ${isoDate(nominal.publication_date)}` : "U.S. Treasury par curves"}
    state={nominal ? (nominal.state === "PUBLICATION_CURRENT" ? "CURRENT" : nominal.state) : null}
    clock={nominal?.publication_date ? `Daily publication · ${isoDate(nominal.publication_date)}` : null}>
    {query.isError && !data ? <PanelMessage tone="error" role="alert">Rates &amp; Curve request failed.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading Treasury curves…</PanelMessage>
      : <div className="bond-panel">
        <section className="bond-panel-chart" aria-label="Current curve">
          {nominal && nominal.points.length ? <CurveChart nominal={data.nominal} real={data.real}
            marker={data.selected && !pending ? { years: data.selected.years_to_maturity, value: reference?.state === "REFERENCE" ? reference.value ?? null : null,
              label: data.selected.cusip } : null} />
            : <PanelMessage tone="warn">Treasury par curve unavailable · {reasonLabel(data.sources.find((item) => item.id === "TREASURY_CURVE")?.reason)}</PanelMessage>}
        </section>
        <div className="bond-panel-side">
          <section className="bond-panel-section" aria-label="Curve spreads">
            <h3>Curve spreads <small>derived · {isoDate(data.spreads[0]?.publication_date)}</small></h3>
            <dl className="bond-panel-spreads">{data.spreads.map((spread) => <div key={spread.id} title={spread.formula}>
              <dt>{SPREAD_LABELS[spread.id] ?? spread.id}</dt><dd>{bondValue(spread.value_bp, "bp")}</dd></div>)}</dl>
            <p className="screener-panel-note"><strong>{SHAPES[data.shape.state]}</strong> · {data.shape.rule}. A description of this publication, not a forecast.</p>
          </section>
          <section className="bond-panel-section" aria-label="Selected bond">
            <h3>Selected bond</h3>{pending ? <p className="screener-panel-note">Loading {row?.cusip}…</p> : <Selected data={data} />}
          </section>
          <section className="bond-panel-section" aria-label="Real yields and breakevens">
            <h3>Real yields <small>{data.real.publication_date ? isoDate(data.real.publication_date) : "unavailable"}</small></h3>
            {data.breakevens.items.length ? <table className="bond-panel-table"><thead><tr><th scope="col">Tenor</th><th scope="col">Nominal</th><th scope="col">Real</th><th scope="col">Breakeven*</th></tr></thead>
              <tbody>{data.breakevens.items.map((item) => <tr key={item.tenor}><th scope="row">{item.tenor}</th><td>{item.nominal.toFixed(2)}%</td><td>{item.real.toFixed(2)}%</td><td>{item.value.toFixed(2)}%</td></tr>)}</tbody></table>
              : <p className="screener-panel-note">Unavailable · {reasonLabel(data.breakevens.reason)}</p>}
            {data.breakevens.method && <p className="screener-panel-note">* {data.breakevens.method}</p>}
          </section>
          <NyFed data={data} />
          <Fred title="Policy & inflation (FRED)" items={data.policy.items} state={data.policy.state} reason={data.policy.reason} />
          <Fred title="Credit & conditions (FRED)" items={data.credit.items} state={data.credit.state} reason={data.credit.reason} note={data.credit.note} />
          <section className="bond-panel-section" aria-label="Fixed-income activity">
            <h3>Trade activity (FINRA)</h3>
            <p className="screener-panel-note">Security trade prints: {reasonLabel("LICENSED_TRACE_FEED_REQUIRED")}; no corporate, agency, or municipal trade prices.</p>
            {data.finra.breadth && <p className="screener-panel-note">Corporate &amp; agency market breadth: {data.finra.breadth.state === "NOT_CONFIGURED" || !Object.keys(data.finra.breadth.categories).length
              ? `${data.finra.breadth.state.toLowerCase().replace(/_/g, " ")}${data.finra.breadth.reason ? ` · ${reasonLabel(data.finra.breadth.reason)}` : ""}`
              : Object.entries(data.finra.breadth.categories).map(([category, item]) => `${category.toLowerCase()} ${item.state === "PUBLICATION_CURRENT" ? `${item.rows.length} rows · ${isoDate(item.trade_date ?? null)}` : item.state.toLowerCase().replace(/_/g, " ")}`).join(" · ")} (counts, not prices).</p>}
            <p className="screener-panel-note">TRACE Treasury aggregates: {data.finra.aggregates.state === "PUBLICATION_CURRENT"
              ? `${data.finra.aggregates.rows?.length ?? 0} buckets · trade date ${isoDate(data.finra.aggregates.trade_date ?? null)} (aggregates, not quotes)`
              : `${data.finra.aggregates.state.toLowerCase().replace(/_/g, " ")}${data.finra.aggregates.reason ? ` · ${reasonLabel(data.finra.aggregates.reason)}` : ""}`}.</p>
          </section>
          <section className="bond-panel-section" aria-label="Source clocks">
            <h3>Source clocks</h3>
            <ul className="bond-sources">{data.sources.map((source) => <li key={source.id}><span>{source.label}</span>
              <span className={`bond-source-state ${(source.state ?? "unavailable").toLowerCase()}`}>{sourceState(source)}</span>
              <small>{source.as_of ? (source.as_of.length > 10 ? new Date(source.as_of).toLocaleString() : isoDate(source.as_of)) : reasonLabel(source.reason)}</small></li>)}</ul>
          </section>
        </div>
      </div>}
  </PanelFrame>;
}

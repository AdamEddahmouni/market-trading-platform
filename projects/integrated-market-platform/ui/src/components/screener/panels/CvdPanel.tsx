import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchCvd, type CvdPayload } from "../../../api/screenerPanels";
import { Age, EntitlementNote, ErrorDetail, etClock, marketClock, marketVolume, PanelFrame, PanelMessage, providerLabel, reasonText, selectionGate, signedMarketVolume, usePanelVisible, useSelection } from "./shared";
import { OpenDConnect } from "../setup/Remedy";
import type { ScreenerUniverse } from "../../../api/screener";

const CvdChart = lazy(() => import("./CvdChart"));
const BLOCKED = new Set(["UNAVAILABLE", "NOT_ENTITLED", "DISCONNECTED", "CONNECTING", "SUBSCRIPTION_BUSY"]);
const LOW_COVERAGE = 70;
/** Module-level so the chart is not rebuilt each render: fractional base units keep significant digits. */
const cryptoAxis = (value: number) => signedMarketVolume(value, "CRYPTO");

/** The CVD anchor is stated exactly; it is never called a session CVD. */
export function anchorLabel(window: CvdPayload["window"], clock: (iso: string | null | undefined) => string = etClock) {
  if (!window) return "CVD";
  return window.basis === "LAST_N_CAPTURED" ? `CVD over last ${window.max_records} captured trades` : `CVD since subscription ${clock(window.anchor_at)}`;
}

type BodyProps = { data: CvdPayload; clock: (iso: string | null | undefined) => string; unit: string; zone: string; universe: ScreenerUniverse };

function Body({ data, clock, unit, zone, universe }: BodyProps) {
  const signed = (value: number) => signedMarketVolume(value, universe);
  const summary = data.summary!;
  const coverage = summary.classified_volume_pct;
  const tone = summary.cvd > 0 ? "screener-positive" : summary.cvd < 0 ? "screener-negative" : "";
  const text = `${anchorLabel(data.window, clock)}: ${signed(summary.cvd)} ${unit}, derived from ${summary.trade_count} trades; `
    + `${coverage == null ? "no classified volume" : `${coverage.toFixed(0)}% of volume classified`}; last ${summary.recent_delta_seconds} seconds ${summary.recent_delta == null ? "no trades" : signed(summary.recent_delta)}.`;
  return <>
    <div className="screener-cvd-head">
      <div><span className="screener-panel-kicker">{anchorLabel(data.window, clock)}</span><strong className={tone}>{signed(summary.cvd)}</strong></div>
      <div><span className="screener-panel-kicker">Last {summary.recent_delta_seconds}s</span><strong>{summary.recent_delta == null ? "—" : signed(summary.recent_delta)}</strong></div>
      <div><span className="screener-panel-kicker">Classified volume</span>
        <strong className={coverage != null && coverage < LOW_COVERAGE ? "screener-warn" : undefined}>{coverage == null ? "—" : `${coverage.toFixed(0)}%`}</strong></div>
    </div>
    {coverage != null && coverage < LOW_COVERAGE && <PanelMessage tone="warn">{(100 - coverage).toFixed(0)}% of volume ({marketVolume(summary.unknown_volume, universe)}) has no side and is excluded; CVD is partial.</PanelMessage>}
    <Suspense fallback={<div className="screener-cvd-chart" />}><CvdChart points={data.points} label={text} timeZone={zone} formatValue={universe === "CRYPTO" ? cryptoAxis : undefined} /></Suspense>
    <p className="sr-only">{text}</p>
    <p className="screener-panel-note">Derived estimate: sides are {summary.aggressor_states.NATIVE && !summary.aggressor_states.INFERRED ? "the venue-reported taker side" : summary.aggressor_states.NATIVE ? "partly exchange-native, partly inferred" : "inferred"} ({summary.methods.join(", ").replace(/_/g, " ").toLowerCase() || "none"}). A rising CVD is not a forecast.</p>
  </>;
}

export default function CvdPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, universe } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-cvd", universe, settledId],
    queryFn: ({ signal }) => universe === "US_EQUITIES" ? fetchCvd(settledId!, signal) : fetchCvd(settledId!, signal, universe),
    enabled: Boolean(settledId) && visible,
    refetchInterval: (current) => visible ? (current.state.data?.state === "CURRENT" ? 1_000 : 3_000) : false,
    retry: 1,
  });
  const gate = selectionGate("cvd", row, settledId);
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const market = marketClock(universe);
  const unit = universe === "CRYPTO" ? row?.base_asset ?? "base units" : "shares";
  const clock = data?.latest_received_at ? <>latest trade {market.clock(data.latest_event_at)} · rcvd <Age iso={data.latest_received_at} staleMs={10_000} /> ago</> : null;
  return <PanelFrame id="cvd" state={data?.state} detail={data ? `Derived · ${providerLabel(data.provider)}` : "Derived"} clock={clock}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">CVD request failed.<ErrorDetail error={query.error} /> <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : BLOCKED.has(data.state) ? <PanelMessage tone={data.state === "CONNECTING" ? "muted" : "warn"}>{reasonText(data.reason) || data.state}<OpenDConnect reason={data.reason} /></PanelMessage>
      : <>
        {data.state !== "CURRENT" && <PanelMessage tone="warn">{data.state === "SESSION_CLOSED" ? "Session closed · last captured window" : reasonText(data.reason)}</PanelMessage>}
        {data.summary && data.summary.trade_count > 0 ? <Body data={data} clock={market.clock} unit={unit} zone={market.zone} universe={universe} />
          : <PanelMessage>{data.state === "SESSION_CLOSED" ? "No trades captured this session; no CVD to show." : "Subscribed; no trades printed yet."}</PanelMessage>}
        <EntitlementNote entitlement={data.entitlement} />
      </>)}
  </PanelFrame>;
}

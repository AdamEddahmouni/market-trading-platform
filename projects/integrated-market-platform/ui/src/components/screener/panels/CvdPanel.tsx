import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchCvd, type CvdPayload } from "../../../api/screenerPanels";
import { age, compact, EntitlementNote, etClock, PanelFrame, PanelMessage, reasonText, selectionGate, signedCompact, usePanelVisible, useSelection } from "./shared";

const CvdChart = lazy(() => import("./CvdChart"));
const BLOCKED = new Set(["UNAVAILABLE", "NOT_ENTITLED", "DISCONNECTED", "CONNECTING", "SUBSCRIPTION_BUSY"]);
const LOW_COVERAGE = 70;

/** The CVD anchor is stated exactly; it is never called a session CVD. */
export function anchorLabel(window: CvdPayload["window"]) {
  if (!window) return "CVD";
  return window.basis === "LAST_N_CAPTURED" ? `CVD over last ${window.max_records} captured trades` : `CVD since subscription ${etClock(window.anchor_at)}`;
}

function Body({ data }: { data: CvdPayload }) {
  const summary = data.summary!;
  const coverage = summary.classified_volume_pct;
  const tone = summary.cvd > 0 ? "screener-positive" : summary.cvd < 0 ? "screener-negative" : "";
  const text = `${anchorLabel(data.window)}: ${signedCompact(summary.cvd)} shares, derived from ${summary.trade_count} trades; `
    + `${coverage == null ? "no classified volume" : `${coverage.toFixed(0)}% of volume classified`}; last ${summary.recent_delta_seconds} seconds ${summary.recent_delta == null ? "no trades" : signedCompact(summary.recent_delta)}.`;
  return <>
    <div className="screener-cvd-head">
      <div><span className="screener-panel-kicker">{anchorLabel(data.window)}</span><strong className={tone}>{signedCompact(summary.cvd)}</strong></div>
      <div><span className="screener-panel-kicker">Last {summary.recent_delta_seconds}s</span><strong>{summary.recent_delta == null ? "—" : signedCompact(summary.recent_delta)}</strong></div>
      <div><span className="screener-panel-kicker">Classified volume</span>
        <strong className={coverage != null && coverage < LOW_COVERAGE ? "screener-warn" : undefined}>{coverage == null ? "—" : `${coverage.toFixed(0)}%`}</strong></div>
    </div>
    {coverage != null && coverage < LOW_COVERAGE && <PanelMessage tone="warn">{(100 - coverage).toFixed(0)}% of volume ({compact(summary.unknown_volume)}) has no side and is excluded; CVD is partial.</PanelMessage>}
    <Suspense fallback={<div className="screener-cvd-chart" />}><CvdChart points={data.points} label={text} /></Suspense>
    <p className="sr-only">{text}</p>
    <p className="screener-panel-note">Derived estimate: sides are {summary.aggressor_states.NATIVE ? "partly exchange-native, partly inferred" : "inferred"} ({summary.methods.join(", ").replace(/_/g, " ").toLowerCase() || "none"}). A rising CVD is not a forecast.</p>
  </>;
}

export default function CvdPanel({ api }: IDockviewPanelProps) {
  const { row, settledId } = useSelection();
  const visible = usePanelVisible(api);
  const query = useQuery({
    queryKey: ["screener-cvd", settledId],
    queryFn: ({ signal }) => fetchCvd(settledId!, signal),
    enabled: Boolean(settledId) && visible,
    refetchInterval: (current) => visible ? (current.state.data?.state === "CURRENT" ? 1_000 : 3_000) : false,
    retry: 1,
  });
  const gate = selectionGate("cvd", row, settledId);
  const data = query.data && query.data.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  const clock = data?.latest_received_at ? `latest trade ${etClock(data.latest_event_at)} · rcvd ${age(data.latest_received_at)} ago` : null;
  return <PanelFrame id="cvd" state={data?.state} detail={data ? `Derived · ${data.provider === "MOOMOO" ? "Moomoo" : data.provider ?? "No provider"}` : "Derived"} clock={clock}>
    {gate ?? (query.isError && !data ? <PanelMessage tone="error" role="alert">CVD request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
      : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
      : BLOCKED.has(data.state) ? <PanelMessage tone={data.state === "CONNECTING" ? "muted" : "warn"}>{reasonText(data.reason) || data.state}</PanelMessage>
      : <>
        {data.state !== "CURRENT" && <PanelMessage tone="warn">{data.state === "SESSION_CLOSED" ? "Session closed · last captured window" : reasonText(data.reason)}</PanelMessage>}
        {data.summary && data.summary.trade_count > 0 ? <Body data={data} />
          : <PanelMessage>{data.state === "SESSION_CLOSED" ? "No trades captured this session; no CVD to show." : "Subscribed; no trades printed yet."}</PanelMessage>}
        <EntitlementNote entitlement={data.entitlement} />
      </>)}
  </PanelFrame>;
}

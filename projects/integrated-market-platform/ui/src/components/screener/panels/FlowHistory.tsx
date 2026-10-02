import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchFlowSeries, type FlowRange, type FlowResolution } from "../../../api/screenerPanels";
import type { ScreenerUniverse } from "../../../api/screener";
import type { FlowViewport } from "./CvdChart";
import FlowTimeControls from "./FlowTimeControls";
import { flowDetailWindow } from "./flowDetailWindow";
import { ErrorDetail, marketClock, marketVolume, PanelMessage, providerLabel, reasonText, signedMarketVolume } from "./shared";

const Chart = lazy(() => import("./CvdChart"));
const cryptoAxis = (value: number) => signedMarketVolume(value, "CRYPTO");

/** Mounted with an identity key by both panels: controls never leak across symbols. */
export default function FlowHistory({ instrument, universe, visible, mode }: {
  instrument: string; universe: ScreenerUniverse; visible: boolean; mode: "cvd" | "delta";
}) {
  const [range, setRange] = useState<FlowRange>("5m");
  const [resolution, setResolution] = useState<FlowResolution>("auto");
  const [viewport, setViewport] = useState<FlowViewport | null>(null);
  const [requested, setRequested] = useState<FlowViewport | null>(null);
  const updateViewport = useCallback((next: FlowViewport) => setViewport(previous =>
    previous?.from === next.from && previous.to === next.to && previous.live === next.live ? previous : next), []);
  useEffect(() => {
    const timer = setTimeout(() => setRequested(viewport), 300);
    return () => clearTimeout(timer);
  }, [viewport]);
  // Historical inspection requests progressively finer detail. Live retains the chosen
  // viewport width, with its end anchored by the server clock on each refresh.
  const query = useQuery({
    queryKey: ["screener-flow-series", universe, instrument, range, resolution],
    queryFn: ({ signal }) => fetchFlowSeries(instrument, universe, range, resolution, undefined, signal),
    enabled: visible, retry: 1,
    refetchInterval: visible ? 5_000 : false,
    placeholderData: previous => previous,
  });
  const data = query.data?.instrument_id === instrument && query.data.range === range ? query.data : undefined;
  const detailWindow = requested ? flowDetailWindow(
    Math.max(0, requested.live ? Date.now() - Math.min(86399000, Math.max(1000, requested.to - requested.from)) : requested.from),
    requested.live ? Date.now() : Math.min(Date.now() - 1000, requested.to + 1000), data?.points ?? []) : undefined;
  const detail = useQuery({
    queryKey: ["screener-flow-detail", universe, instrument, range, resolution, requested],
    queryFn: ({ signal }) => fetchFlowSeries(instrument, universe, range, resolution,
      detailWindow ? { start: Math.max(detailWindow.start, Date.now() - 86399000),
        ...(!requested?.live ? { end: Math.min(Date.now() - 1000, detailWindow.end) } : {}) } : undefined, signal),
    enabled: visible && !!requested && !!data, retry: 1,
    refetchInterval: visible && requested?.live ? 5_000 : false,
  });
  const detailData = detail.data?.instrument_id === instrument ? detail.data : undefined;
  const fineCoverage = detailData?.coverage;
  // Keep broader context around detail so zoom-out and backwards pan still have data.
  const points = useMemo(() => fineCoverage && detailData?.points.length ? [
    ...(data?.points.filter(p => p.end_ms <= fineCoverage.requested_start_ms || p.time_ms >= fineCoverage.requested_end_ms) ?? []),
    ...detailData.points,
  ].sort((a, b) => a.time_ms - b.time_ms) : data?.points ?? [], [data?.points, detailData?.points, fineCoverage]);
  const market = marketClock(universe), signed = (n: number) => signedMarketVolume(n, universe);
  const clock = (ms: number | null) => market.clock(ms == null ? null : new Date(ms).toISOString());
  // A fresh blocked base response must also hide any cached historical detail.
  const coverage = data?.coverage && requested && !requested.live && fineCoverage ? fineCoverage : data?.coverage;
  const selected = points.filter(p => !viewport || (p.end_ms > viewport.from && p.time_ms <= viewport.to));
  const delta = selected.reduce((sum, p) => sum + p.delta, 0), trades = selected.reduce((sum, p) => sum + p.trade_count, 0);
  const classified = selected.reduce((sum, p) => sum + p.classified_volume, 0), unknown = selected.reduce((sum, p) => sum + p.unknown_volume, 0);
  const pct = classified + unknown ? classified / (classified + unknown) * 100 : null;
  const summary = `Visible ${clock(viewport?.from ?? coverage?.actual_start_ms ?? null)}–${clock(viewport?.to ?? coverage?.actual_end_ms ?? null)} · net signed flow ${signed(delta)} · ${trades.toLocaleString()} trades · classified ${pct == null ? "—" : `${pct.toFixed(0)}%`} · unknown volume ${marketVolume(unknown, universe)}.`;
  return <section className="screener-flow-history" aria-label={mode === "cvd" ? "Captured CVD history" : "Signed flow history"}>
    <FlowTimeControls range={range} resolution={resolution} crypto={universe === "CRYPTO"}
      onRange={value => { setRange(value); setViewport(null); setRequested(null); }} onResolution={setResolution} />
    {query.isError && <PanelMessage tone="warn">Flow history request failed.<ErrorDetail error={query.error} /></PanelMessage>}
    {detail.isError && <PanelMessage tone="warn">Detail request failed; displaying the available broader resolution.</PanelMessage>}
    {!data ? <PanelMessage>Loading captured flow history…</PanelMessage> : <>
      {!coverage ? <PanelMessage tone="warn">{reasonText(data.reason) || data.state}</PanelMessage> : <>
        <p className={coverage.complete ? "screener-panel-note" : "screener-flow-coverage"}>
          Requested {clock(coverage.requested_start_ms)}–{clock(coverage.requested_end_ms)} · available capture {clock(coverage.actual_start_ms)}–{clock(coverage.actual_end_ms)}.
          {coverage.complete ? " Continuous subscribed capture." : " Partial capture; missing history is not reconstructed."}
          {coverage.truncated ? " History retention truncated." : ""}
          {coverage.dropped_late_trades ? ` ${coverage.dropped_late_trades} late arrivals excluded outside the correction window.` : ""}
        </p>
        {coverage.gaps.map((gap, i) => <p className="screener-flow-coverage" key={i}>
          {((gap.end_ms - gap.start_ms) / 60000).toFixed(1)}-minute coverage gap · {clock(gap.start_ms)}–{clock(gap.end_ms)} ·
          {gap.reason === "SUBSCRIPTION_INTERRUPTION" ? " subscription interrupted" : gap.reason === "PROVIDER_CHANGE" ? " provider changed"
            : gap.reason === "PROVIDER_INTERRUPTION" ? " provider connection interrupted" : " feed continuity unverified (silence can include no prints)"}.
        </p>)}
        <p className="screener-panel-note">{mode === "cvd" ? `Captured accumulation since ${market.clock(coverage.anchor_at)}; includes only observed signed flow. The current headline retains its own stated anchor.` : "Signed delta per time bucket; direction may be native, inferred, or unknown."} Effective resolution {detailData?.resolution_seconds ?? data.resolution_seconds}s.</p>
        <p className="screener-panel-note">Captured sources: {[...new Set(points.flatMap(p => p.providers))].map(providerLabel).join(", ") || "none"}.</p>
        {data.latest && <p className="screener-panel-note">Captured CVD now {signed(data.latest.cvd)} · last 60s {signed(data.latest.recent_delta)} · {data.latest.trades_per_minute} trades/min · latest {market.clock(data.latest.event_at)}.</p>}
        {points.length ? <Suspense fallback={<div className="screener-cvd-chart" />}>
          <Chart points={points} label={summary} mode={mode} timeZone={market.zone}
            formatValue={universe === "CRYPTO" ? cryptoAxis : undefined} resetKey={`${universe}:${instrument}:${range}`}
            onViewport={updateViewport} />
        </Suspense> : <PanelMessage>No observed trades in the requested range.</PanelMessage>}
        <p className="screener-panel-note" aria-live="polite">{summary}</p>
        {pct != null && pct < 70 && <PanelMessage tone="warn">Low classification coverage; unknown volume is excluded from signed flow.</PanelMessage>}
        <p className="screener-panel-note">Runtime capture only; restarting starts a new capture. No earlier provider history is implied.</p>
      </>}
    </>}
  </section>;
}

import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { IDockviewPanelProps } from "dockview-react";
import { fetchChart } from "../../../api/screenerPanels";
import { classifyZones } from "../srClassify";
import { age, etClock, etDay, money, PanelFrame, PanelMessage, reasonText, selectionGate, usePanelVisible, useSelection } from "./shared";

const ExpandedChart = lazy(() => import("./ExpandedChart"));
// The same timeframes and session scopes the S3 current-bar contract supports.
const TIMEFRAMES = ["1m", "5m", "15m"] as const;
const SCOPES = [{ id: "EXTENDED", label: "Extended" }, { id: "RTH", label: "RTH" }] as const;
const BAR_STATES: Record<string, string> = { CURRENT: "Current", SESSION_CLOSED: "Session closed · last session", STALE: "Stale", UNAVAILABLE: "Unavailable" };

export default function ChartsPanel({ api }: IDockviewPanelProps) {
  const { row, settledId, quote } = useSelection();
  const visible = usePanelVisible(api);
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>("5m");
  const [scope, setScope] = useState<"EXTENDED" | "RTH">("EXTENDED");
  const query = useQuery({
    queryKey: ["screener-chart", settledId, timeframe, scope],
    queryFn: ({ signal }) => fetchChart(settledId!, timeframe, scope, signal),
    enabled: Boolean(settledId) && visible, staleTime: 10_000, retry: 1,
    refetchInterval: (current) => !visible ? false : current.state.data?.bars.provider_reason === "MOOMOO_SUBSCRIPTION_BUSY" ? 5_000 : 15_000,
    // Keep the previous chart only while this instrument changes timeframe or scope.
    placeholderData: (previous) => previous && previous.instrument.instrument_id === settledId ? previous : undefined,
  });
  const gate = selectionGate("charts", row, settledId);
  const data = query.data && query.data.instrument.instrument_id === row?.instrument.instrument_id ? query.data : undefined;
  // Price clock and bar clock stay separate: the marker is L1 when live, otherwise the last completed bar close.
  const livePrice = quote?.state === "LIVE" ? quote.fields.price?.value ?? null : null;
  const markerPrice = livePrice ?? data?.levels.price?.value ?? null;
  const classified = useMemo(() => data ? classifyZones(data.levels.zones, markerPrice, data.levels.min_strength) : null, [data, markerPrice]);
  const bars = data?.bars;
  const last = bars?.bars[bars.bars.length - 1];
  const scopeLabel = bars?.session_scope === "RTH" ? "RTH" : "Extended";
  const priceText = livePrice != null ? `L1 live $${money(livePrice)}${quote?.age_ms != null ? ` · ${quote.age_ms}ms` : ""}`
    : last ? `Last bar close $${money(last.close)} · ${etDay(last.end)}` : "No current price";
  const label = data && last ? `${data.instrument.symbol} ${bars!.timeframe} ${scopeLabel} candles, ${bars!.bar_count} completed bars to ${etDay(bars!.latest_complete_bar_end)}; ${priceText}`
    + `${classified?.support ? `; support ${money(classified.support.lower)} to ${money(classified.support.upper)}` : ""}`
    + `${classified?.resistance ? `; resistance ${money(classified.resistance.lower)} to ${money(classified.resistance.upper)}` : ""}` : "";
  return <PanelFrame id="charts" state={bars?.state === "UNAVAILABLE" ? "UNAVAILABLE" : bars?.state}
    detail={data ? `${timeframe} · ${scopeLabel} · Moomoo OpenD` : null}
    clock={bars?.received_at ? `bars rcvd ${age(bars.received_at)} ago` : null}>
    {gate ?? <>
      <div className="screener-panel-controls">
        <div role="group" aria-label="Chart timeframe" className="screener-segment">{TIMEFRAMES.map((item) =>
          <button key={item} type="button" aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>{item}</button>)}</div>
        <div role="group" aria-label="Session scope" className="screener-segment">{SCOPES.map((item) =>
          <button key={item.id} type="button" aria-pressed={scope === item.id} onClick={() => setScope(item.id)}>{item.label}</button>)}</div>
        <span className="screener-panel-price">{priceText}</span>
      </div>
      {query.isError && !data ? <PanelMessage tone="error" role="alert">Chart request failed. <button type="button" onClick={() => void query.refetch()}>Retry</button></PanelMessage>
        : !data ? <PanelMessage>Loading {row!.symbol}…</PanelMessage>
        : bars && bars.bars.length ? <Suspense fallback={<div className="screener-expanded-chart" />}>
          <ExpandedChart bars={bars.bars} forming={bars.forming} support={classified?.support ?? null} resistance={classified?.resistance ?? null} livePrice={livePrice} label={label} />
        </Suspense> : <PanelMessage tone="warn">Chart unavailable · {reasonText(bars?.provider_reason ?? bars?.reason) || "no bars"}</PanelMessage>}
      {data && <p className="screener-panel-note">{BAR_STATES[bars!.state] ?? bars!.state}{bars!.latest_complete_bar_end ? ` · last bar ${etDay(bars!.latest_complete_bar_end)}` : ""}
        {` · ${data.levels.method} `}{data.levels.state === "UNAVAILABLE" ? `levels unavailable (${reasonText(data.levels.reason)})` : `levels calculated ${etClock(data.levels.calculated_at)}`}
        {classified?.testing ? " · price is inside a zone" : ""}</p>}
      <p className="sr-only">{label}</p>
    </>}
  </PanelFrame>;
}

import { Link } from "react-router-dom";
import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from "lightweight-charts";
import {
  ADMITTED_REPLAY_INSTRUMENT_ID,
  FROZEN_DEMO_REFERENCE_SYMBOL,
  type WorkspaceSqueezeResponse,
} from "../api/client";
import { SqueezeWorkspacePanel } from "./squeeze/SqueezeWorkspacePanel";

type Bar = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
};

type Props = {
  instrumentId: string;
  bars: Bar[];
  features: Array<{ feature_id: string; value: string; epistemic_class: string }>;
  squeeze: WorkspaceSqueezeResponse | null;
  squeezeLoading?: boolean;
  replayChartAvailable: boolean;
  onScrub: (index: number) => void;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenSqueezeHistory?: (symbol: string) => void;
  cursorIndex: number;
  maxIndex: number;
};

function toChartTime(iso: string): Time {
  const ms = Date.parse(iso);
  return Math.floor(ms / 1000) as Time;
}

export function WorkspacePage({
  instrumentId,
  bars,
  features,
  squeeze,
  squeezeLoading = false,
  replayChartAvailable,
  onScrub,
  onExplain,
  onInspect,
  onOpenSqueezeHistory,
  cursorIndex,
  maxIndex,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current || !replayChartAvailable) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#141820" }, textColor: "#e8ecf4" },
      grid: { vertLines: { color: "#2a3142" }, horzLines: { color: "#2a3142" } },
      width: containerRef.current.clientWidth,
      height: 320,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#3d9970",
      downColor: "#c44e52",
      borderVisible: false,
      wickUpColor: "#3d9970",
      wickDownColor: "#c44e52",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const resize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [replayChartAvailable]);

  useEffect(() => {
    if (!seriesRef.current || !replayChartAvailable) return;
    const data: CandlestickData[] = bars.map((bar) => ({
      time: toChartTime(bar.time),
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
    }));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [bars, replayChartAvailable]);

  return (
    <section className="page workspace-page">
      <header className="page-header">
        <h1>Instrument Cockpit — {instrumentId}</h1>
        <p>
          {replayChartAvailable && squeeze?.available
            ? "Admitted replay fixture plus donor squeeze evidence (read-only)."
            : replayChartAvailable
              ? "Admitted replay fixture — open Short Squeeze module for donor evidence."
              : squeeze?.available
                ? "Donor squeeze evidence — replay chart unavailable for this symbol."
                : "Workspace context with capability-honest unavailable panels."}
        </p>
        <nav className="workspace-module-nav" aria-label="Workspace modules">
          <Link className="active" to={`/workspace/${instrumentId}`}>Overview</Link>
          <Link to={`/workspace/${instrumentId}/squeeze`}>Short Squeeze</Link>
          <Link to={`/workspace/${instrumentId}/order-flow`}>Order Flow</Link>
          <Link to={`/workspace/${instrumentId}/options`}>Options</Link>
        </nav>
      </header>

      {replayChartAvailable ? (
        <>
          <div className="replay-controls">
            <label htmlFor="replay-scrub">
              Replay cursor {cursorIndex + 1} / {maxIndex + 1}
            </label>
            <input
              id="replay-scrub"
              type="range"
              min={0}
              max={maxIndex}
              value={cursorIndex}
              onChange={(event) => onScrub(Number(event.target.value))}
            />
          </div>
          <div ref={containerRef} className="price-chart" />
          <section className="feature-grid">
            <h2>Derived features</h2>
            <ul>
              {features.map((feature) => (
                <li key={feature.feature_id}>
                  <span className="epistemic">{feature.epistemic_class}</span>
                  <strong>{feature.feature_id}</strong> {feature.value}
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : (
        <aside className="capability-panel unavailable workspace-replay-unavailable">
          <h2>Price / Replay</h2>
          <p>UNAVAILABLE — no admitted replay fixture for {instrumentId}.</p>
          <p className="workspace-hint">
            Replay chart is only available for {ADMITTED_REPLAY_INSTRUMENT_ID}. Frozen squeeze evidence is
            available for symbols such as {FROZEN_DEMO_REFERENCE_SYMBOL} — open one from EXPLORE.
          </p>
        </aside>
      )}

      <SqueezeWorkspacePanel
        instrumentId={instrumentId}
        squeeze={squeeze}
        loading={squeezeLoading}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenHistory={onOpenSqueezeHistory}
        compact
      />

      <aside className="capability-panel unavailable">
        <h2>Institutional Flow</h2>
        <p>UNAVAILABLE — no entitled source on admitted fixture.</p>
        <p className="workspace-hint">
          Order-flow CVD evidence is available on the NVDA workspace module when replay cutoff permits.
        </p>
      </aside>
    </section>
  );
}

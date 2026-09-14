import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { ImpChartMarker } from "./impSemanticAnnotations";
import type { ImpBarRecord } from "./impBarIdentity";
import {
  persistWorkspaceVelaShadowEnabled,
  readWorkspaceVelaShadowEnabled,
} from "./impWorkspaceVelaShadow";

const LazyVelaAdapter = lazy(() =>
  import("./ImpVelaChartAdapter").then((module) => ({ default: module.ImpVelaChartAdapter })),
);

export type WorkspacePriceChartBar = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
};

export type WorkspacePriceChartProps = {
  bars: WorkspacePriceChartBar[];
  impBars: ImpBarRecord[] | null;
  markers: ImpChartMarker[];
  replayChartAvailable: boolean;
};

function toChartTime(iso: string): Time {
  const ms = Date.parse(iso);
  return Math.floor(ms / 1000) as Time;
}

function LightweightWorkspaceChart({ bars }: { bars: WorkspacePriceChartBar[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
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
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    const data: CandlestickData[] = bars.map((bar) => ({
      time: toChartTime(bar.time),
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
    }));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [bars]);

  return <div ref={containerRef} className="price-chart" data-imp-chart-engine="lightweight-charts" />;
}

export function WorkspacePriceChart({
  bars,
  impBars,
  markers,
  replayChartAvailable,
}: WorkspacePriceChartProps) {
  const [shadowEnabled, setShadowEnabled] = useState(() => readWorkspaceVelaShadowEnabled());

  const velaReady = replayChartAvailable && shadowEnabled && impBars != null && impBars.length > 0;

  const shadowHint = useMemo(() => {
    if (!replayChartAvailable) return null;
    if (shadowEnabled && impBars == null) {
      return "Vela shadow enabled but canonical BAR_OHLCV_1M identity is incomplete — using lightweight-charts fallback.";
    }
    return null;
  }, [impBars, replayChartAvailable, shadowEnabled]);

  const toggleShadow = () => {
    const next = !shadowEnabled;
    setShadowEnabled(next);
    persistWorkspaceVelaShadowEnabled(next);
  };

  return (
    <div className="workspace-price-chart-stack">
      {replayChartAvailable ? (
        <div className="workspace-vela-shadow-controls">
          <button
            type="button"
            className="workspace-vela-shadow-toggle"
            aria-pressed={shadowEnabled}
            onClick={toggleShadow}
          >
            {shadowEnabled ? "Vela shadow on" : "Vela shadow off"}
          </button>
          <span className="workspace-vela-shadow-badge" data-ready={velaReady ? "true" : "false"}>
            {velaReady ? "VELA_WORKSPACE_SHADOW_READY" : "lightweight-charts default"}
          </span>
        </div>
      ) : null}
      {shadowHint ? (
        <p className="workspace-vela-shadow-hint" role="status">
          {shadowHint}
        </p>
      ) : null}
      {velaReady ? (
        <Suspense fallback={<p className="muted" role="status">Loading Vela shadow chart…</p>}>
          <LazyVelaAdapter
            bars={impBars}
            markers={markers}
            theme="dark"
            className="imp-vela-chart-host workspace-vela-shadow-chart"
            aria-label="IMP workspace Vela shadow chart"
          />
        </Suspense>
      ) : (
        <LightweightWorkspaceChart bars={bars} />
      )}
    </div>
  );
}

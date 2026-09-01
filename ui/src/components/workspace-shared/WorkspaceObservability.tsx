import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import {
  ADMITTED_REPLAY_INSTRUMENT_ID,
  FROZEN_DEMO_REFERENCE_SYMBOL,
  type WorkspaceEvidenceLane,
  type WorkspaceSqueezeResponse,
} from "../../api/client";
import { useContextQuery, useWorkspaceEvidenceQuery } from "../../api/hooks";
import { SqueezeWorkspacePanel } from "../squeeze/SqueezeWorkspacePanel";
import { LiveMarketPanel } from "../live/LiveMarketPanel";
import { WhatMattersNowPanel } from "../workspace/WhatMattersNowPanel";
import { WorkspaceEvidenceDrawer } from "../workspace/WorkspaceEvidenceDrawer";
import { formatDataHealthLabel } from "./workspaceHealth";

export type WorkspaceBar = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
};

export type WorkspaceObservabilityProps = {
  instrumentId: string;
  bars: WorkspaceBar[];
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

export function useWorkspaceContext(instrumentId: string) {
  const contextQuery = useContextQuery();
  const evidenceQuery = useWorkspaceEvidenceQuery(instrumentId);
  const context = contextQuery.data;
  const evidence = evidenceQuery.data;
  const isLive = context?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const dataLabel = formatDataHealthLabel(context?.as_of_context);
  const healthState = context?.quality_summary.state ?? "UNKNOWN";

  return {
    contextQuery,
    evidenceQuery,
    evidence,
    isLive,
    dataLabel,
    healthState,
  };
}

export function WorkspaceObservability({
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
}: WorkspaceObservabilityProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [selectedLane, setSelectedLane] = useState<WorkspaceEvidenceLane | null>(null);

  const { evidence, evidenceQuery, isLive, dataLabel } = useWorkspaceContext(instrumentId);

  useEffect(() => {
    void fetch("/operator/workspace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        layout: {
          collapsed: {},
          layout_schema_version: 1,
          open_panels: ["what-matters", "live-market", "paper-ticket"],
          panel_order: ["what-matters", "live-market", "paper-ticket"],
          research_lane: "overview",
          selected_instrument: instrumentId,
          timeframe: isLive ? "live" : "replay-cursor",
        },
        name: "Active",
      }),
    }).catch(() => undefined);
  }, [instrumentId, isLive]);

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
    <>
      {evidence ? (
        <WhatMattersNowPanel
          instrumentId={instrumentId}
          lanes={evidence.what_matters_now}
          mixSummary={evidence.evidence_mix_summary}
          dataLabel={dataLabel}
          onSelectLane={(lane) => setSelectedLane(lane)}
        />
      ) : evidenceQuery.isLoading ? (
        <p className="muted">Loading lane evidence…</p>
      ) : null}

      <LiveMarketPanel instrumentId={instrumentId} />

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
      ) : !isLive ? (
        <aside className="capability-panel unavailable workspace-replay-unavailable">
          <h2>Price / Replay</h2>
          <p>UNAVAILABLE — no admitted replay fixture for {instrumentId}.</p>
          <p className="workspace-hint">
            Replay chart is only available for {ADMITTED_REPLAY_INSTRUMENT_ID}. Frozen squeeze evidence is
            available for symbols such as {FROZEN_DEMO_REFERENCE_SYMBOL} — open one from EXPLORE.
          </p>
        </aside>
      ) : null}

      <SqueezeWorkspacePanel
        instrumentId={instrumentId}
        squeeze={squeeze}
        loading={squeezeLoading}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenHistory={onOpenSqueezeHistory}
        compact
      />

      <WorkspaceEvidenceDrawer
        lane={selectedLane}
        onClose={() => setSelectedLane(null)}
        onExplain={onExplain}
      />
    </>
  );
}

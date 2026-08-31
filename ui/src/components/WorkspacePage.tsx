import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from "lightweight-charts";
import {
  ADMITTED_REPLAY_INSTRUMENT_ID,
  FROZEN_DEMO_REFERENCE_SYMBOL,
  type WorkspaceEvidenceLane,
  type WorkspaceSqueezeResponse,
} from "../api/client";
import {
  useContextQuery,
  usePaperPortfolioQuery,
  useWorkspaceEvidenceQuery,
} from "../api/hooks";
import { SqueezeWorkspacePanel } from "./squeeze/SqueezeWorkspacePanel";
import { LiveMarketPanel } from "./live/LiveMarketPanel";
import { WhatMattersNowPanel } from "./workspace/WhatMattersNowPanel";
import { WorkspaceEvidenceDrawer } from "./workspace/WorkspaceEvidenceDrawer";
import { OrderTicket } from "./paper/OrderTicket";
import { ExecutionTracePanel } from "./paper/ExecutionTracePanel";
import { canUsePaperActions } from "./mode-session/modeAuthority";
import type { Mode } from "./mode-session/types";
import type { PaperOrderDraft } from "./paper-now/paperOrderDraft";

type Bar = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
};

type Props = {
  mode: Mode;
  paperActionsPermitted: boolean;
  initialPaperOrderDraft?: PaperOrderDraft;
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

function formatDataHealthLabel(context: { data_mode?: string; data_provider?: string | null } | undefined) {
  if (!context) return "";
  if (context.data_mode === "LIVE_OBSERVATIONAL") {
    return `LIVE · ${context.data_provider ?? "MOOMOO"}`;
  }
  if (context.data_mode === "CAPTURE_REPLAY") {
    return "REPLAY · MOOMOO CAPTURE";
  }
  return context.data_mode?.replace(/_/g, " ") ?? "";
}

export function WorkspacePage({
  mode,
  paperActionsPermitted,
  initialPaperOrderDraft,
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
  const [selectedLane, setSelectedLane] = useState<WorkspaceEvidenceLane | null>(null);
  const [traceIntentId, setTraceIntentId] = useState<string | undefined>();

  const contextQuery = useContextQuery();
  const evidenceQuery = useWorkspaceEvidenceQuery(instrumentId);
  const portfolioQuery = usePaperPortfolioQuery();

  const context = contextQuery.data;
  const evidence = evidenceQuery.data;
  const portfolio = portfolioQuery.data;
  const isLive = context?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const dataLabel = formatDataHealthLabel(context?.as_of_context);
  const healthState = context?.quality_summary.state ?? "UNKNOWN";
  const paperActionsAvailable = canUsePaperActions(
    mode,
    paperActionsPermitted,
    portfolio?.account,
  );

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

  const ticketContextLanes =
    evidence?.what_matters_now?.slice(0, 4).map((lane) => ({
      lane: lane.lane.replace(/_/g, " "),
      relevance: lane.relevance,
      summary: lane.summary,
    })) ?? [];

  return (
    <section className="page workspace-page unified-workstation">
      <header className="page-header">
        <h1>{instrumentId}</h1>
        <p className="workspace-health-line">
          {dataLabel} · {healthState}
          {evidence?.evidence_mix_summary && evidence.evidence_mix_summary !== "UNKNOWN"
            ? ` · ${evidence.evidence_mix_summary.replace(/_/g, " ")} evidence`
            : ""}
        </p>
        <nav className="workspace-module-nav" aria-label="Workspace modules">
          <Link className="active" to={`/workspace/${instrumentId}`}>Overview</Link>
          <Link to={`/workspace/${instrumentId}/squeeze`}>Short Squeeze</Link>
          <Link to={`/workspace/${instrumentId}/order-flow`}>Order Flow</Link>
          <Link to={`/workspace/${instrumentId}/order-book`}>Order Book</Link>
          <Link to={`/workspace/${instrumentId}/catalyst`}>Catalyst</Link>
          <Link to={`/workspace/${instrumentId}/institutional-flow`}>Institutional Flow</Link>
        </nav>
      </header>

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

      <div className="workspace-paper-row">
        {portfolio && paperActionsAvailable ? (
          <OrderTicket
            symbol={instrumentId}
            initialDraft={initialPaperOrderDraft}
            executionAuthority={portfolio.account.execution_authority}
            executionMode={portfolio.account.execution_mode}
            dataMode={portfolio.account.data_mode}
            maxOrderShares={portfolio.risk.limits.max_order_shares}
            contextLanes={ticketContextLanes}
            onSubmitted={(intentId) => {
              if (intentId) setTraceIntentId(intentId);
            }}
          />
        ) : portfolio ? (
          <aside className="panel mode-restriction-note" role="note">
            <strong>{mode} is read-only here.</strong>
            <p>Order and paper-session controls are unavailable for this context.</p>
          </aside>
        ) : null}
        {paperActionsAvailable && traceIntentId ? (
          <ExecutionTracePanel
            intentId={traceIntentId}
            onClose={() => setTraceIntentId(undefined)}
          />
        ) : null}
      </div>

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
    </section>
  );
}

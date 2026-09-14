import { useEffect, useMemo, useState } from "react";
import {
  ADMITTED_REPLAY_INSTRUMENT_ID,
  FROZEN_DEMO_REFERENCE_SYMBOL,
  type WorkspaceEvidenceLane,
  type WorkspaceSqueezeResponse,
} from "../../api/client";
import { useContextQuery, useWorkspaceEvidenceQuery } from "../../api/hooks";
import { WorkspacePriceChart } from "../charts/WorkspacePriceChart";
import {
  mapWorkspaceBarsToImpRecords,
  type WorkspaceCanonicalBar,
} from "../charts/workspaceImpBarFeed";
import { projectWorkspaceEvidenceMarkers } from "../charts/workspaceSemanticMarkers";
import { SqueezeWorkspacePanel } from "../squeeze/SqueezeWorkspacePanel";
import { LiveMarketPanel } from "../live/LiveMarketPanel";
import { WhatMattersNowPanel } from "../workspace/WhatMattersNowPanel";
import { WorkspaceEvidenceDrawer } from "../workspace/WorkspaceEvidenceDrawer";
import { formatDataHealthLabel } from "./workspaceHealth";

export type WorkspaceBar = WorkspaceCanonicalBar;

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
  const [selectedLane, setSelectedLane] = useState<WorkspaceEvidenceLane | null>(null);

  const { evidence, evidenceQuery, isLive, dataLabel } = useWorkspaceContext(instrumentId);

  const impBars = useMemo(
    () => (replayChartAvailable ? mapWorkspaceBarsToImpRecords(instrumentId, bars) : null),
    [bars, instrumentId, replayChartAvailable],
  );

  const chartMarkers = useMemo(() => {
    if (!impBars || !evidence) return [];
    return projectWorkspaceEvidenceMarkers(evidence.what_matters_now, impBars);
  }, [evidence, impBars]);

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
          <WorkspacePriceChart
            bars={bars}
            impBars={impBars}
            markers={chartMarkers}
            replayChartAvailable={replayChartAvailable}
          />
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

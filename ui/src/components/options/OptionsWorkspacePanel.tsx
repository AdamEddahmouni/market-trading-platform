import type { WorkspaceOptionsResponse } from "../../api/schemas";
import {
  ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID,
  ADMITTED_REPLAY_INSTRUMENT_ID,
} from "../../api/schemas";
import { DealerPositioningBlock } from "./DealerPositioningBlock";
import { ExecutionSimulationBlock } from "./ExecutionSimulationBlock";
import { OpportunityFusionBlock } from "./OpportunityFusionBlock";
import { StrategyOptimizerBlock } from "./StrategyOptimizerBlock";

type Props = {
  instrumentId: string;
  options: WorkspaceOptionsResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

function hasResearchSnapshots(options: WorkspaceOptionsResponse): boolean {
  return Boolean(
    options.strategy_snapshot ||
      options.execution_snapshot ||
      options.opportunity_snapshot ||
      options.dealer_snapshot ||
      options.event_vol_snapshot,
  );
}

export function OptionsWorkspacePanel({
  instrumentId,
  options,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading options evidence…</div>;
  }

  if (!options) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Options workspace</h2>
        <p>UNAVAILABLE — no payload</p>
      </aside>
    );
  }

  const researchSnapshots = hasResearchSnapshots(options);
  const activities = options.activities ?? [];
  const showWhaleUnavailable = !options.available && !researchSnapshots;

  if (showWhaleUnavailable) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Options / Unusual Activity</h2>
        <p>UNAVAILABLE — {options.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Options whale fixture is entitled for {ADMITTED_REPLAY_INSTRUMENT_ID} only within replay PIT
          cutoff. Cooperative O6–O9 research path uses {ADMITTED_OPTIONS_RESEARCH_INSTRUMENT_ID}.
        </p>
      </aside>
    );
  }

  return (
    <section className="options-panel">
      <header className="panel-header">
        <h2>Options workspace</h2>
        <p>{options.disclaimer}</p>
        {!options.available && researchSnapshots ? (
          <p className="workspace-hint">
            Whale unusual-activity unavailable ({options.reason ?? "no PIT events"}) — cooperative
            research snapshots below.
          </p>
        ) : null}
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:options:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:options:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection — not a trade recommendation</span>
      </div>

      <div className="options-research-blocks">
        <DealerPositioningBlock snapshot={options.dealer_snapshot} onExplain={onExplain} />
        <StrategyOptimizerBlock snapshot={options.strategy_snapshot} onExplain={onExplain} />
        <ExecutionSimulationBlock snapshot={options.execution_snapshot} onExplain={onExplain} />
        <OpportunityFusionBlock snapshot={options.opportunity_snapshot} onExplain={onExplain} />
      </div>

      {options.available && activities.length > 0 ? (
        <>
          <h3>Unusual options activity</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Event time</th>
                <th>Type</th>
                <th>Strike</th>
                <th>Expiry</th>
                <th>Volume</th>
                <th>OI</th>
                <th>Vol/OI</th>
                <th>Liquidity</th>
                <th>Direction</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((row) => (
                <tr key={`${row.event_time}-${row.normalized_event_id}`}>
                  <td>{row.event_time}</td>
                  <td>{row.option_type}</td>
                  <td>{String(row.strike)}</td>
                  <td>{row.expiry}</td>
                  <td>{String(row.volume)}</td>
                  <td>{String(row.open_interest)}</td>
                  <td>{String(row.volume_oi_ratio)}</td>
                  <td>{row.liquidity_ok ? "PASS" : "FAIL"}</td>
                  <td>{row.direction_label}</td>
                  <td>{String(row.confirmation_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      <aside className="capability-panel unavailable">
        <h3>Full Options Chain</h3>
        <p>UNAVAILABLE — options.chain capability not entitled.</p>
      </aside>
    </section>
  );
}

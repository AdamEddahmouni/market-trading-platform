import type { ExecutionSnapshot } from "../../api/schemas";

type Props = {
  snapshot: ExecutionSnapshot | null | undefined;
  onExplain?: (ref: string) => void;
};

function assignmentRiskLabel(events: Array<Record<string, unknown>> | undefined): string {
  if (!events || events.length === 0) {
    return "none observed";
  }
  const assignments = events.filter((event) => event.event_type === "ASSIGNMENT");
  if (assignments.length === 0) {
    return "none observed";
  }
  return `${assignments.length} assignment event(s)`;
}

export function ExecutionSimulationBlock({ snapshot, onExplain }: Props) {
  if (!snapshot) {
    return null;
  }

  if (!snapshot.available) {
    return (
      <section className="execution-simulation-block unavailable">
        <h3>Execution simulation (O9)</h3>
        <p className="execution-outcome">{snapshot.outcome ?? "UNAVAILABLE"}</p>
        <p>{snapshot.reason ?? "EXECUTION_UNAVAILABLE"}</p>
      </section>
    );
  }

  const fills = snapshot.entry_fills ?? [];
  const lifecycleEvents = snapshot.lifecycle_events ?? [];
  const ledger = snapshot.ledger_summary ?? {};

  return (
    <section className="execution-simulation-block available">
      <h3>Execution simulation (O9)</h3>
      <p className="execution-disclaimer">
        Conservative NBBO fills — research simulation, not live execution.
      </p>
      <dl className="metric-grid">
        <div>
          <dt>Outcome</dt>
          <dd className="execution-outcome">{snapshot.outcome ?? snapshot.status ?? "—"}</dd>
        </div>
        <div>
          <dt>Strategy template</dt>
          <dd>{snapshot.strategy_template ?? "—"}</dd>
        </div>
        <div>
          <dt>Realized P&amp;L</dt>
          <dd>{snapshot.realized_pnl ?? "—"}</dd>
        </div>
        <div>
          <dt>Unrealized P&amp;L</dt>
          <dd>{snapshot.unrealized_pnl ?? "—"}</dd>
        </div>
        <div>
          <dt>Assignment risk</dt>
          <dd>{assignmentRiskLabel(lifecycleEvents)}</dd>
        </div>
        <div>
          <dt>Open positions</dt>
          <dd>{ledger.open_positions ?? "—"}</dd>
        </div>
        <div>
          <dt>Entry fills</dt>
          <dd>{fills.length}</dd>
        </div>
        <div>
          <dt>Simulator</dt>
          <dd>{snapshot.simulator_registry_id ?? snapshot.model_version ?? "—"}</dd>
        </div>
      </dl>
      {snapshot.quality_flags && snapshot.quality_flags.length > 0 ? (
        <p className="execution-quality">Flags: {snapshot.quality_flags.join(", ")}</p>
      ) : null}
      {snapshot.execution_replay_hash ? (
        <p className="execution-replay-hash">Replay hash: {snapshot.execution_replay_hash}</p>
      ) : null}
      {onExplain ? (
        <button type="button" onClick={() => onExplain("options:execution:simulation")}>
          Trace execution
        </button>
      ) : null}
      {fills.length > 0 ? (
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Leg</th>
              <th>Side</th>
              <th>Type</th>
              <th>Strike</th>
              <th>Fill</th>
              <th>Liquidity</th>
            </tr>
          </thead>
          <tbody>
            {fills.map((fill, index) => (
              <tr key={`${fill.leg_index ?? index}-${fill.strike}`}>
                <td>{fill.leg_index ?? index}</td>
                <td>{fill.side ?? "—"}</td>
                <td>{fill.call_put ?? "—"}</td>
                <td>{fill.strike ?? "—"}</td>
                <td>{fill.fill_price ?? "—"}</td>
                <td>{fill.liquidity_ok ? "PASS" : "FAIL"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

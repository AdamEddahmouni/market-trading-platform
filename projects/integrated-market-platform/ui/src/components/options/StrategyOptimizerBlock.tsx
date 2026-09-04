import type { StrategySnapshot } from "../../api/schemas";

type Props = {
  snapshot: StrategySnapshot | null | undefined;
  onExplain?: (ref: string) => void;
};

export function StrategyOptimizerBlock({ snapshot, onExplain }: Props) {
  if (!snapshot) {
    return null;
  }

  if (!snapshot.available) {
    return (
      <section className="strategy-optimizer-block unavailable">
        <h3>Strategy optimizer (O8)</h3>
        <p className="strategy-outcome">{snapshot.outcome ?? "UNAVAILABLE"}</p>
        <p>{snapshot.reason ?? "STRATEGY_UNAVAILABLE"}</p>
      </section>
    );
  }

  const best = snapshot.best_candidate;
  const payoff =
    best && typeof best.payoff === "object" && best.payoff !== null
      ? (best.payoff as Record<string, unknown>)
      : undefined;

  return (
    <section className="strategy-optimizer-block available">
      <h3>Strategy optimizer (O8)</h3>
      <p className="strategy-disclaimer">
        Lane-local strategy ranking — not SHARED P4 fused opportunity.
      </p>
      <dl className="metric-grid">
        <div>
          <dt>Outcome</dt>
          <dd className="strategy-outcome">{snapshot.outcome ?? snapshot.status ?? "—"}</dd>
        </div>
        <div>
          <dt>Best template</dt>
          <dd>{best?.template ?? "—"}</dd>
        </div>
        <div>
          <dt>Edge alignment</dt>
          <dd>{best?.edge_alignment ?? "—"}</dd>
        </div>
        <div>
          <dt>Net expected P&amp;L</dt>
          <dd>{best?.net_expected_pnl ?? "—"}</dd>
        </div>
        <div>
          <dt>Expected P&amp;L</dt>
          <dd>{String(payoff?.expected_pnl ?? "—")}</dd>
        </div>
        <div>
          <dt>Win probability</dt>
          <dd>{String(payoff?.win_probability ?? "—")}</dd>
        </div>
        <div>
          <dt>Friction cost</dt>
          <dd>{String(payoff?.friction_cost ?? "—")}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{snapshot.model_version ?? snapshot.method ?? "—"}</dd>
        </div>
      </dl>
      {snapshot.quality_flags && snapshot.quality_flags.length > 0 ? (
        <p className="strategy-quality">Flags: {snapshot.quality_flags.join(", ")}</p>
      ) : null}
      {snapshot.replay_hash ? <p className="strategy-replay-hash">Replay hash: {snapshot.replay_hash}</p> : null}
      {onExplain ? (
        <button type="button" onClick={() => onExplain("options:strategy:best_candidate")}>
          Trace strategy
        </button>
      ) : null}
      {snapshot.ranked_candidates && snapshot.ranked_candidates.length > 1 ? (
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Template</th>
              <th>Alignment</th>
              <th>Net EV</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.ranked_candidates.map((row) => (
              <tr key={row.template ?? String(row.net_expected_pnl)}>
                <td>{row.template ?? "—"}</td>
                <td>{row.edge_alignment ?? "—"}</td>
                <td>{row.net_expected_pnl ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

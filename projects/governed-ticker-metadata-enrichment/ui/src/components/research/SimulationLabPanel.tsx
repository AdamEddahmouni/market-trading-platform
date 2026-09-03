import type { ResearchSimulationResponse } from "../../api/schemas";
import { CountBarChartPanel } from "../charts/ResearchChartPanels";

type Props = {
  payload: ResearchSimulationResponse;
};

function countSeries(rows: Record<string, unknown>[], key: string) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = String(row[key] ?? "unknown");
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return Array.from(counts.entries()).map(([label, count]) => ({ label, count }));
}

export function SimulationLabPanel({ payload }: Props) {
  const decisionSeries = countSeries(payload.risk_decisions, "decision");
  const ledger = payload.ledger_summary;

  return (
    <section className="simulation-lab-panel">
      <div className="simulation-banner" role="status">
        <strong>{payload.mode_label}</strong>
        <span>{payload.authority_boundary}</span>
        <span>Read-only deterministic simulation — no order placement</span>
      </div>

      <header className="panel-header">
        <h2>Simulation Lab</h2>
        <p>{payload.disclaimer}</p>
      </header>

      <dl className="metric-grid">
        <div>
          <dt>Cash (minor units)</dt>
          <dd>{ledger.cash_minor ?? "—"}</dd>
        </div>
        <div>
          <dt>Position shares</dt>
          <dd>{ledger.position_shares ?? "—"}</dd>
        </div>
        <div>
          <dt>Realized P&amp;L (minor)</dt>
          <dd>{ledger.realized_pnl_minor ?? "—"}</dd>
        </div>
        <div>
          <dt>Ledger entries</dt>
          <dd>{ledger.entry_count}</dd>
        </div>
        <div>
          <dt>Reconciliation</dt>
          <dd>{String(payload.reconciliation.status ?? "—")}</dd>
        </div>
        <div>
          <dt>Fill audit</dt>
          <dd>{String(payload.fill_audit?.status ?? "—")}</dd>
        </div>
      </dl>

      <CountBarChartPanel
        title="Risk decisions at cutoff"
        series={decisionSeries}
        provenance={{
          source: "phase 7 risk simulation",
          method: "run_risk_simulation_evaluation decisions at cutoff",
        }}
        ariaLabel="Risk decision distribution"
      />

      <table className="data-table">
        <thead>
          <tr>
            <th>Decision</th>
            <th>Constraint</th>
            <th>Cutoff</th>
            <th>Intent</th>
          </tr>
        </thead>
        <tbody>
          {payload.risk_decisions.map((row, index) => (
            <tr key={`${row.risk_decision_id ?? index}-${index}`}>
              <td>{String(row.decision ?? "—")}</td>
              <td>{String(row.constraint_detail ?? row.reason_code ?? "—")}</td>
              <td>{String(row.signal_prediction_cutoff ?? "—")}</td>
              <td>{String(row.intent_id ?? "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table className="data-table">
        <thead>
          <tr>
            <th>Fill time</th>
            <th>Direction</th>
            <th>Quantity</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {payload.fills.map((row, index) => (
            <tr key={`${row.fill_id ?? index}-${index}`}>
              <td>{String(row.fill_time ?? "—")}</td>
              <td>{String(row.direction ?? "—")}</td>
              <td>{String(row.fill_quantity ?? "—")}</td>
              <td>{String(row.fill_price_minor ?? "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

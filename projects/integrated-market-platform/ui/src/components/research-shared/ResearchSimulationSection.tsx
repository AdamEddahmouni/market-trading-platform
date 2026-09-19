import { Link } from "react-router-dom";
import { useResearchSimulationQuery } from "../../api/hooks";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { LoadingState } from "../shared/LoadingState";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { CountBarChartPanel } from "../charts/ResearchChartPanels";
import { formatResearchTime, presentCheckStatus } from "./researchPresentation";
import { SimulationHarnessMetricsPanel } from "./SimulationHarnessMetricsPanel";

function countSeries(rows: Record<string, unknown>[], key: string) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const label = String(row[key] ?? "unknown");
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return Array.from(counts.entries()).map(([label, count]) => ({ label, count }));
}

/**
 * Research Simulation — the deterministic simulation experiment record:
 * ledger headline, risk decisions, fills, and reconciliation. This is a
 * research run (bar-conservative simulator): it is not a governed FTEP
 * campaign result and not production readiness, and it never places orders.
 */
export function ResearchSimulationSection() {
  const simulationQuery = useResearchSimulationQuery();

  if (simulationQuery.isLoading) {
    return <LoadingState label="Loading simulation record…" />;
  }

  if (simulationQuery.isError || !simulationQuery.data) {
    return (
      <ErrorState
        title="The simulation record is unavailable right now."
        affects="Simulation decisions, fills, and reconciliation cannot be displayed until the endpoint responds."
        rawDetail={
          simulationQuery.error instanceof Error ? simulationQuery.error.message : undefined
        }
        onRetry={() => void simulationQuery.refetch()}
      />
    );
  }

  const payload = simulationQuery.data;
  const ledger = payload.ledger_summary;
  const reconciliation = presentCheckStatus(payload.reconciliation?.status as string | undefined);
  const fillAudit = presentCheckStatus(payload.fill_audit?.status as string | undefined);
  const epistemic = resolveSemanticState("research", payload.epistemic_class);
  const decisionSeries = countSeries(payload.risk_decisions, "decision");

  return (
    <>
      <section className="research-panel" aria-labelledby="research-simulation-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Experiment run</div>
            <h2 id="research-simulation-heading">Deterministic simulation</h2>
          </div>
          {payload.as_of_context ? (
            <FreshnessIndicator asOf={payload.as_of_context.as_of_time} decays={false} />
          ) : null}
        </div>

        <p className="research-finding-claim">
          {ledger.entry_count} ledger {ledger.entry_count === 1 ? "entry" : "entries"} ·{" "}
          {payload.risk_decisions.length} risk{" "}
          {payload.risk_decisions.length === 1 ? "decision" : "decisions"} · {payload.fills.length}{" "}
          {payload.fills.length === 1 ? "fill" : "fills"}.
        </p>

        <div className="research-trust-row">
          <StatePill tone={epistemic.tone} label={epistemic.label} raw={epistemic.raw} />
          <StatePill
            tone={reconciliation.tone}
            label={`Reconciliation: ${reconciliation.label}`}
            raw={reconciliation.raw}
          />
          <StatePill
            tone={fillAudit.tone}
            label={`Fill audit: ${fillAudit.label}`}
            raw={fillAudit.raw}
          />
        </div>

        <dl className="research-fact-grid">
          <div>
            <dt>Cash (minor units)</dt>
            <dd>{ledger.cash_minor ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Position (shares)</dt>
            <dd>{ledger.position_shares ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Realized P&amp;L (minor units)</dt>
            <dd>{ledger.realized_pnl_minor ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Ledger entries</dt>
            <dd>{ledger.entry_count}</dd>
          </div>
        </dl>

        <p className="research-muted">
          Deterministic bar-conservative simulation over the replay window. Amounts are in minor
          units because the contract carries no currency field. This run is evidence about the
          simulator and risk policy — it is not a governed campaign result, not a calibration
          claim, and it never places orders.
        </p>
        <p className="research-muted">
          <Link to="/lab/simulation">Inspect this simulation workflow in Lab</Link> — Lab is the
          process surface; this page stays the interpretation of the snapshot.
        </p>
      </section>

      <SimulationHarnessMetricsPanel
        payload={payload}
        headingId="research-simulation-harness-heading"
      />

      <section className="research-panel" aria-labelledby="research-simulation-decisions-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Decisions</div>
            <h2 id="research-simulation-decisions-heading">Risk decisions at cutoff</h2>
          </div>
        </div>
        <CountBarChartPanel
          title="Risk decision distribution"
          series={decisionSeries}
          provenance={{
            source: "phase 7 risk simulation",
            method: "run_risk_simulation_evaluation decisions at cutoff",
          }}
          emptyMessage="No risk decisions fall inside the current replay window."
          ariaLabel="Risk decision distribution"
        />
        {payload.risk_decisions.length ? (
          <div className="research-table-wrap">
            <table className="data-table">
              <caption className="chart-data-caption">Risk decisions at the current cutoff</caption>
              <thead>
                <tr>
                  <th scope="col">Decision</th>
                  <th scope="col">Constraint</th>
                  <th scope="col">Cutoff</th>
                  <th scope="col">Intent</th>
                </tr>
              </thead>
              <tbody>
                {payload.risk_decisions.map((row, index) => {
                  const decision = resolveSemanticState(
                    "executionAuthority",
                    row.decision == null ? undefined : String(row.decision),
                  );
                  const cutoff = formatResearchTime(row.signal_prediction_cutoff);
                  const intentId = row.intent_id == null ? null : String(row.intent_id);
                  return (
                    <tr key={`${String(row.risk_decision_id ?? index)}-${index}`}>
                      <td>
                        <StatePill tone={decision.tone} label={decision.label} raw={decision.raw} size="sm" />
                      </td>
                      <td>{String(row.constraint_detail ?? row.reason_code ?? "—")}</td>
                      <td>{cutoff ?? "Unavailable"}</td>
                      <td>
                        {intentId ? <CopyableIdentifier value={intentId} chars={4} /> : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="research-panel" aria-labelledby="research-simulation-fills-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Fills</div>
            <h2 id="research-simulation-fills-heading">Simulated fills</h2>
          </div>
        </div>
        {payload.fills.length === 0 ? (
          <p className="research-muted" role="status">
            No simulated fills fall inside the current replay window.
          </p>
        ) : (
          <div className="research-table-wrap">
            <table className="data-table">
              <caption className="chart-data-caption">Simulated fills at the current cutoff</caption>
              <thead>
                <tr>
                  <th scope="col">Fill time</th>
                  <th scope="col">Direction</th>
                  <th scope="col">Quantity</th>
                  <th scope="col">Price (minor units)</th>
                </tr>
              </thead>
              <tbody>
                {payload.fills.map((row, index) => {
                  const fillTime = formatResearchTime(row.fill_time);
                  return (
                    <tr key={`${String(row.fill_id ?? index)}-${index}`}>
                      <td>{fillTime ?? "Unavailable"}</td>
                      <td>{String(row.direction ?? "—")}</td>
                      <td>{String(row.fill_quantity ?? "—")}</td>
                      <td>{String(row.fill_price_minor ?? "—")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <details className="research-panel research-methodology">
        <summary>Audit and technical detail</summary>
        <dl className="research-fact-grid">
          <div>
            <dt>Risk policy</dt>
            <dd>
              {payload.risk_policy_id ? (
                <CopyableIdentifier value={payload.risk_policy_id} chars={6} />
              ) : (
                "Unavailable"
              )}
            </dd>
          </div>
          <div>
            <dt>Epistemic class (raw)</dt>
            <dd>{payload.epistemic_class ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Authority boundary (raw)</dt>
            <dd>{payload.authority_boundary}</dd>
          </div>
        </dl>
        {payload.disclaimer ? <p className="research-muted">{payload.disclaimer}</p> : null}
        <JsonDetailPanel title="Reconciliation detail" value={payload.reconciliation} />
        {payload.fill_audit ? (
          <JsonDetailPanel title="Fill audit detail" value={payload.fill_audit} />
        ) : null}
        <JsonDetailPanel title="Orders (raw)" value={payload.orders} />
        <JsonDetailPanel title="Intents (raw)" value={payload.intents} />
        <JsonDetailPanel title="Attributions (raw)" value={payload.attributions} />
      </details>
    </>
  );
}

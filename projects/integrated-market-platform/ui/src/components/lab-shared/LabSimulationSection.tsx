import { Link } from "react-router-dom";
import { useResearchSimulationQuery } from "../../api/hooks";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { LoadingState } from "../shared/LoadingState";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { formatResearchTime, presentCheckStatus } from "../research-shared/researchPresentation";
import { simulationResultSummary } from "./labPresentation";
import { SimulationHarnessMetricsPanel } from "../research-shared/SimulationHarnessMetricsPanel";

/**
 * Lab Simulation workbench — configuration, current snapshot, and honest
 * limits. Interpretation of the ledger lives in Research.
 */
export function LabSimulationSection() {
  const simulationQuery = useResearchSimulationQuery();

  if (simulationQuery.isLoading) {
    return <LoadingState label="Loading simulation workflow…" />;
  }

  if (simulationQuery.isError || !simulationQuery.data) {
    return (
      <ErrorState
        title="The simulation workflow snapshot is unavailable."
        affects="Assumptions, ledger, and reconciliation cannot be inspected until /research/simulation responds."
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
  const boundary = resolveSemanticState("research", payload.authority_boundary);

  return (
    <>
      <section className="lab-panel" aria-labelledby="lab-simulation-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Simulation workflow</div>
            <h2 id="lab-simulation-heading">Deterministic simulation</h2>
          </div>
          {payload.as_of_context ? (
            <FreshnessIndicator asOf={payload.as_of_context.as_of_time} decays={false} />
          ) : null}
        </div>
        <div className="lab-trust-row">
          <StatePill tone="paper" label="Read-only" raw="inspectable" />
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
        <p className="lab-claim">{simulationResultSummary(payload)}</p>
        <p className="lab-muted">
          Simulation is not forward-test evidence and not production readiness. This is a
          deterministic bar-conservative snapshot, not a governed FTEP campaign, and it never
          places Paper or Live orders. There is no run-history list — only the current result.
        </p>
        <div className="lab-actions">
          <Link to="/research/simulation">View interpretation in Research</Link>
        </div>
      </section>

      <SimulationHarnessMetricsPanel payload={payload} headingId="lab-simulation-harness-heading" />

      <section className="lab-panel" aria-labelledby="lab-simulation-config-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">Configuration</div>
          <h2 id="lab-simulation-config-heading">Recorded assumptions</h2>
        </div>
        <dl className="lab-fact-grid">
          <div>
            <dt>Mode label</dt>
            <dd>{payload.mode_label}</dd>
          </div>
          <div>
            <dt>Authority boundary</dt>
            <dd>
              <StatePill tone={boundary.tone} label={boundary.label} raw={boundary.raw} />
            </dd>
          </div>
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
        </dl>
        {payload.disclaimer ? <p className="lab-muted">{payload.disclaimer}</p> : null}
        <p className="lab-muted">
          Lab does not offer simulation parameter editors. The UI API accepts no simulation
          request body, so any frontend knob would do nothing.
        </p>
      </section>

      <section className="lab-panel" aria-labelledby="lab-simulation-during-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">During run</div>
          <h2 id="lab-simulation-during-heading">Run state</h2>
        </div>
        <p className="lab-muted" role="status">
          No queued, running, cancelled, or progress fields are exposed. Retry from this page is
          not a supported mutation; refreshing re-reads the same snapshot.
        </p>
      </section>

      <section className="lab-panel" aria-labelledby="lab-simulation-ledger-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">After run</div>
          <h2 id="lab-simulation-ledger-heading">Ledger and fills</h2>
        </div>
        <dl className="lab-fact-grid">
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
        {payload.risk_decisions.length === 0 && payload.fills.length === 0 ? (
          <p className="lab-muted" role="status">
            No simulated decisions or fills fall inside the current replay window.
          </p>
        ) : (
          <div className="lab-table-wrap">
            <table className="data-table">
              <caption className="chart-data-caption">
                Current simulation snapshot. Amounts stay in minor units because the contract has
                no currency field.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Kind</th>
                  <th scope="col">Detail</th>
                  <th scope="col">Time</th>
                  <th scope="col">Identity</th>
                </tr>
              </thead>
              <tbody>
                {payload.risk_decisions.map((row, index) => {
                  const decision = resolveSemanticState(
                    "executionAuthority",
                    row.decision == null ? undefined : String(row.decision),
                  );
                  const intentId = row.intent_id == null ? null : String(row.intent_id);
                  return (
                    <tr key={`decision-${String(row.risk_decision_id ?? index)}`}>
                      <td>
                        <StatePill tone={decision.tone} label={decision.label} raw={decision.raw} size="sm" />
                      </td>
                      <td>{String(row.constraint_detail ?? row.reason_code ?? "—")}</td>
                      <td>{formatResearchTime(row.signal_prediction_cutoff) ?? "Unavailable"}</td>
                      <td>
                        {intentId ? <CopyableIdentifier value={intentId} chars={4} /> : "—"}
                      </td>
                    </tr>
                  );
                })}
                {payload.fills.map((row, index) => (
                  <tr key={`fill-${String(row.fill_id ?? index)}`}>
                    <td>Fill {String(row.direction ?? "")}</td>
                    <td>
                      qty {String(row.fill_quantity ?? "—")} · price {String(row.fill_price_minor ?? "—")}{" "}
                      minor
                    </td>
                    <td>{formatResearchTime(row.fill_time) ?? "Unavailable"}</td>
                    <td>
                      {row.fill_id ? <CopyableIdentifier value={String(row.fill_id)} chars={4} /> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <details className="lab-panel lab-methodology">
        <summary>Methodology and technical detail</summary>
        <dl className="lab-fact-grid">
          <div>
            <dt>Epistemic class (raw)</dt>
            <dd>{payload.epistemic_class ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Authority boundary (raw)</dt>
            <dd>{payload.authority_boundary}</dd>
          </div>
        </dl>
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

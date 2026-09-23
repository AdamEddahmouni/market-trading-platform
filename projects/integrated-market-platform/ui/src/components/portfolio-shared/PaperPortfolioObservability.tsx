import { Link } from "react-router-dom";
import type { PaperPortfolioResponse } from "../../api/client";
import { resolveSemanticState } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { EmptyState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import { PaperRiskRibbon } from "../paper-now/PaperRiskRibbon";
import {
  PORTFOLIO_SECTIONS,
  buildPortfolioAttention,
  buildPortfolioPositions,
  buildPortfolioSummaryMetrics,
  exposureAvailable,
  marksDecay,
  paperCapitalHonesty,
  positionNeedsAttention,
  type SignedAmountPresentation,
} from "../paper-portfolio/paperPortfolioPresentation";

type Props = {
  data: PaperPortfolioResponse;
  viewMode: "DEMO" | "PAPER";
  onTraceOrder?: (intentId?: string, orderId?: string) => void;
  hideOrdersSection?: boolean;
};

function SignedAmount({ amount }: { amount: SignedAmountPresentation }) {
  return (
    <span className="portfolio-signed" data-direction={amount.direction}>
      {amount.text}
      {amount.direction === "gain" ? " gain" : null}
      {amount.direction === "loss" ? " loss" : null}
    </span>
  );
}

export function PaperPortfolioObservability({
  data,
  viewMode,
  onTraceOrder,
  hideOrdersSection = false,
}: Props) {
  const { account, risk, data_health, fills } = data;
  const honesty = paperCapitalHonesty(viewMode);
  const summary = buildPortfolioSummaryMetrics(data);
  const attention = buildPortfolioAttention(data);
  const positions = buildPortfolioPositions(data);
  const killSwitch = resolveSemanticState("portfolio", risk.kill_switch_active ? "ACTIVE" : "OFF");
  const reconciliation = resolveSemanticState(
    "portfolio",
    data.reconciliation_status ?? risk.reconciliation_status,
  );
  const dataHealth = resolveSemanticState("dataHealth", data_health.state);
  const execution = resolveSemanticState("executionAuthority", account.execution_authority);
  const executionMode = resolveSemanticState("executionAuthority", account.execution_mode);
  const dataMode = resolveSemanticState("session", account.data_mode);
  const decayMarks = marksDecay(account.data_mode);

  return (
    <div className="portfolio-operator">
      <AttentionBanner tone={honesty.tone} affects={honesty.affects}>
        {honesty.sentence}
      </AttentionBanner>

      <section
        className="panel portfolio-section"
        id={PORTFOLIO_SECTIONS.account}
        aria-labelledby="portfolio-account-heading"
      >
        <h2 id="portfolio-account-heading">Account</h2>
        <dl className="portfolio-fact-grid">
          <div>
            <dt>Account ID</dt>
            <dd>
              <CopyableIdentifier value={account.paper_account_id} />
            </dd>
          </div>
          <div>
            <dt>Session</dt>
            <dd>
              <CopyableIdentifier value={account.session_id} />
            </dd>
          </div>
          <div>
            <dt>Authority</dt>
            <dd>
              <StatePill
                tone={execution.tone}
                label={execution.label}
                raw={account.execution_authority}
                size="sm"
              />
            </dd>
          </div>
          <div>
            <dt>Execution</dt>
            <dd>
              <StatePill
                tone={executionMode.tone}
                label={executionMode.label}
                raw={account.execution_mode}
                size="sm"
              />
            </dd>
          </div>
          <div>
            <dt>Data mode</dt>
            <dd>
              <StatePill tone={dataMode.tone} label={dataMode.label} raw={account.data_mode} size="sm" />
            </dd>
          </div>
          <div>
            <dt>Data health</dt>
            <dd>
              <StatePill
                tone={dataHealth.tone}
                label={dataHealth.label}
                raw={data_health.state}
                size="sm"
              />
            </dd>
          </div>
          <div>
            <dt>Kill switch</dt>
            <dd>
              <StatePill
                tone={killSwitch.tone}
                label={killSwitch.label}
                raw={risk.kill_switch_active ? "ACTIVE" : "OFF"}
                size="sm"
              />
            </dd>
          </div>
          <div>
            <dt>Reconciliation</dt>
            <dd>
              <StatePill
                tone={reconciliation.tone}
                label={reconciliation.label}
                raw={data.reconciliation_status ?? risk.reconciliation_status}
                size="sm"
              />
            </dd>
          </div>
        </dl>
        <p className="portfolio-workspace-bridge">
          Construct and submit Paper orders in{" "}
          <Link to="/workspace">Workspace</Link>
          {data.active_instrument ? (
            <>
              {" "}
              · active instrument{" "}
              <Link to={`/workspace/${encodeURIComponent(data.active_instrument)}`}>
                {data.active_instrument}
              </Link>
            </>
          ) : null}
          .
        </p>
        <details className="portfolio-technical">
          <summary>Technical account detail</summary>
          <dl className="portfolio-fact-grid">
            <div>
              <dt>Currency</dt>
              <dd>{account.currency}</dd>
            </div>
            <div>
              <dt>Cash (minor)</dt>
              <dd>{account.cash_minor}</dd>
            </div>
            <div>
              <dt>Buying power (minor)</dt>
              <dd>{account.buying_power_minor}</dd>
            </div>
            <div>
              <dt>Data provider</dt>
              <dd>{account.data_provider}</dd>
            </div>
            <div>
              <dt>Execution provider</dt>
              <dd>{account.execution_provider}</dd>
            </div>
            <div>
              <dt>Authority boundary</dt>
              <dd>{data.authority_boundary}</dd>
            </div>
            {data_health.simulation_model ? (
              <div>
                <dt>Simulation model</dt>
                <dd>{data_health.simulation_model}</dd>
              </div>
            ) : null}
            {data_health.detail ? (
              <div>
                <dt>Health detail</dt>
                <dd>{data_health.detail}</dd>
              </div>
            ) : null}
          </dl>
        </details>
      </section>

      <section
        className="panel portfolio-section"
        id={PORTFOLIO_SECTIONS.summary}
        aria-labelledby="portfolio-summary-heading"
      >
        <h2 id="portfolio-summary-heading">Summary</h2>
        <dl className="portfolio-metric-strip">
          {summary.map((metric) => (
            <div key={metric.id} className={metric.available ? undefined : "unavailable"}>
              <dt>{metric.label}</dt>
              <dd>
                {metric.signed ? <SignedAmount amount={metric.signed} /> : metric.value}
              </dd>
            </div>
          ))}
        </dl>
        <PaperRiskRibbon portfolio={data} state="ready" />
      </section>

      {attention.length ? (
        <section
          className="panel portfolio-section"
          id={PORTFOLIO_SECTIONS.attention}
          aria-labelledby="portfolio-attention-heading"
        >
          <h2 id="portfolio-attention-heading">Needs attention</h2>
          <div className="portfolio-attention-stack">
            {attention.map((item) => (
              <AttentionBanner
                key={item.code}
                tone={item.tone}
                affects={item.affects}
                action={item.action}
              >
                {item.message}
              </AttentionBanner>
            ))}
          </div>
        </section>
      ) : null}

      <section
        className="panel portfolio-section"
        id={PORTFOLIO_SECTIONS.positions}
        aria-labelledby="portfolio-positions-heading"
      >
        <h2 id="portfolio-positions-heading">Positions</h2>
        {positions.length === 0 ? (
          <EmptyState
            title="No open positions"
            reason="This simulated account has no open positions in the current session."
            action={{ label: "Open Workspace", href: "/workspace" }}
          />
        ) : (
          <>
            <div className="portfolio-table-wrap portfolio-positions-table-wrap">
              <table className="data-table portfolio-positions-table">
                <caption className="imp-visually-hidden">Open simulated positions</caption>
                <thead>
                  <tr>
                    <th scope="col">Symbol</th>
                    <th scope="col">Side</th>
                    <th scope="col">Qty</th>
                    <th scope="col">Avg fill</th>
                    <th scope="col">Mark</th>
                    <th scope="col">Mark freshness</th>
                    <th scope="col">Unrealized P&amp;L</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((row) => (
                    <tr key={row.instrumentId} data-attention={positionNeedsAttention(row) ? "true" : "false"}>
                      <td>{row.symbol}</td>
                      <td>{row.sideLabel}</td>
                      <td>{row.quantity}</td>
                      <td>{row.averageFill}</td>
                      <td>{row.mark}</td>
                      <td>
                        <FreshnessIndicator
                          backendLabel={row.markQuality}
                          asOf={row.markAsOfNs}
                          decays={decayMarks}
                        />
                      </td>
                      <td>
                        <SignedAmount amount={row.unrealized} />
                      </td>
                      <td>
                        <Link className="portfolio-row-action" to={row.workspaceHref}>
                          Inspect in Workspace
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="portfolio-position-cards">
              {positions.map((row) => (
                <li key={row.instrumentId} className="portfolio-position-card">
                  <header>
                    <h3>{row.symbol}</h3>
                    <p>
                      {row.sideLabel} · {row.quantity}
                    </p>
                  </header>
                  <dl>
                    <div>
                      <dt>Mark</dt>
                      <dd>{row.mark}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>
                        <FreshnessIndicator
                          backendLabel={row.markQuality}
                          asOf={row.markAsOfNs}
                          decays={decayMarks}
                        />
                      </dd>
                    </div>
                    <div>
                      <dt>Unrealized P&amp;L</dt>
                      <dd>
                        <SignedAmount amount={row.unrealized} />
                      </dd>
                    </div>
                    <div>
                      <dt>Avg fill</dt>
                      <dd>{row.averageFill}</dd>
                    </div>
                  </dl>
                  <Link className="portfolio-row-action" to={row.workspaceHref}>
                    Inspect in Workspace
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {exposureAvailable(data.exposure) ? (
        <section
          className="panel portfolio-section"
          id={PORTFOLIO_SECTIONS.exposure}
          aria-labelledby="portfolio-exposure-heading"
        >
          <h2 id="portfolio-exposure-heading">Exposure</h2>
          <p className="muted">Share counts from the Paper contract — not dollar allocation.</p>
          <dl className="portfolio-metric-strip">
            <div>
              <dt>Gross</dt>
              <dd>{data.exposure.gross_shares} sh</dd>
            </div>
            <div>
              <dt>Net</dt>
              <dd>{data.exposure.net_shares} sh</dd>
            </div>
          </dl>
        </section>
      ) : null}

      <section
        className="panel portfolio-section"
        id={PORTFOLIO_SECTIONS.activity}
        aria-labelledby="portfolio-activity-heading"
      >
        <h2 id="portfolio-activity-heading">Fills</h2>
        {hideOrdersSection ? (
          <p className="muted">
            Snapshot fills only. Full order lifecycle is under{" "}
            <a href={`#${PORTFOLIO_SECTIONS.orderHistory}`}>Order history</a> below — not in this
            Fills panel.
          </p>
        ) : null}
        {fills.length === 0 ? (
          <EmptyState
            title="No fills recorded"
            reason="No simulated fills are present on this account snapshot."
          />
        ) : (
          <div className="portfolio-table-wrap">
            <table className="data-table">
              <caption className="imp-visually-hidden">Simulated fills</caption>
              <thead>
                <tr>
                  <th scope="col">Side</th>
                  <th scope="col">Qty</th>
                  <th scope="col">Price (minor)</th>
                  <th scope="col">Order</th>
                </tr>
              </thead>
              <tbody>
                {fills.map((fill) => (
                  <tr key={String(fill.fill_id)}>
                    <td>{String(fill.direction ?? "—")}</td>
                    <td>{String(fill.fill_quantity ?? "—")}</td>
                    <td>{String(fill.fill_price_minor ?? "—")}</td>
                    <td>
                      {typeof fill.order_id === "string" ? (
                        <CopyableIdentifier value={fill.order_id} chars={4} />
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!hideOrdersSection && data.orders.length > 0 ? (
          <div className="portfolio-table-wrap">
            <h3>Orders on this snapshot</h3>
            <table className="data-table">
              <caption className="imp-visually-hidden">Simulated orders on the portfolio snapshot</caption>
              <thead>
                <tr>
                  <th scope="col">Side</th>
                  <th scope="col">Qty</th>
                  <th scope="col">State</th>
                  <th scope="col">Filled</th>
                  {onTraceOrder ? <th scope="col">Trace</th> : null}
                </tr>
              </thead>
              <tbody>
                {data.orders.map((order) => {
                  const state = resolveSemanticState(
                    "portfolio",
                    typeof order.state === "string" ? order.state : undefined,
                  );
                  return (
                    <tr key={String(order.order_id)}>
                      <td>{String(order.side ?? order.direction ?? "—")}</td>
                      <td>{String(order.quantity ?? order.filled_quantity ?? "—")}</td>
                      <td>
                        <StatePill tone={state.tone} label={state.label} raw={state.raw} size="sm" />
                      </td>
                      <td>{String(order.filled_quantity ?? "—")}</td>
                      {onTraceOrder ? (
                        <td>
                          <button
                            type="button"
                            className="portfolio-row-action"
                            onClick={() =>
                              onTraceOrder(
                                typeof order.intent_id === "string" ? order.intent_id : undefined,
                                typeof order.order_id === "string" ? order.order_id : undefined,
                              )
                            }
                          >
                            View trace
                          </button>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}

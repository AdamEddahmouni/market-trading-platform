import { Link } from "react-router-dom";
import type { PaperPortfolioResponse } from "../../api/client";
import { resolveSemanticState } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { EmptyState } from "../imp-ui/FeedbackStates";
import { StatePill } from "../imp-ui/StatePill";
import { PortfolioPositionsTable } from "../paper-portfolio/PortfolioPositionsTable";
import {
  PORTFOLIO_SECTIONS,
  buildPortfolioAttention,
  buildPortfolioGlanceMetrics,
  buildPortfolioPositions,
  exposureAvailable,
  formatShareCount,
  marksDecay,
  paperCapitalHonesty,
  type SignedAmountPresentation,
} from "../paper-portfolio/paperPortfolioPresentation";

type Props = {
  data: PaperPortfolioResponse;
  viewMode: "DEMO" | "PAPER";
  onTraceOrder?: (intentId?: string, orderId?: string) => void;
  hideOrdersSection?: boolean;
  /**
   * Which blocks to render, in the order given. Omit for the full default
   * sequence. The Paper page renders only the primary operator surface and
   * places account/technical detail behind its own disclosure.
   */
  sections?: readonly PortfolioSectionId[];
};

export const PORTFOLIO_SECTION_IDS = [
  "honesty",
  "glance",
  "positions",
  "attention",
  "account",
  "exposure",
  "fills",
] as const;

export type PortfolioSectionId = (typeof PORTFOLIO_SECTION_IDS)[number];

function SignedAmount({ amount }: { amount: SignedAmountPresentation }) {
  return (
    <span className="portfolio-signed" data-direction={amount.direction}>
      {amount.text}
    </span>
  );
}

/**
 * One glance row answering "what exposure and active execution state do I have
 * right now?". Every figure is canonical account/risk state already on the
 * payload; nothing is derived from a frontend guess.
 */
export function PortfolioGlanceStrip({ data }: { data: PaperPortfolioResponse }) {
  const metrics = buildPortfolioGlanceMetrics(data);
  return (
    <section className="portfolio-glance-panel" aria-label="Exposure at a glance">
      <dl className="portfolio-glance" data-testid="portfolio-glance">
        {metrics.map((metric) => (
          <div
            key={metric.id}
            className={metric.available ? undefined : "unavailable"}
            data-lead={metric.emphasis === "lead" ? "true" : undefined}
          >
            <dt>{metric.label}</dt>
            <dd>{metric.signed ? <SignedAmount amount={metric.signed} /> : metric.value}</dd>
          </div>
        ))}
      </dl>
      <p className="portfolio-glance-limits">
        <span>Risk limits</span>
        <span>
          Position {formatShareCount(data.risk.limits.max_position_shares)} sh · Order{" "}
          {formatShareCount(data.risk.limits.max_order_shares)} sh ·{" "}
          {formatShareCount(data.risk.limits.max_open_orders)} working
        </span>
      </p>
    </section>
  );
}

/** Open simulated exposure. The primary Portfolio table. */
export function PortfolioPositionsSection({
  data,
  viewMode: _viewMode,
  canTrade = false,
}: {
  data: PaperPortfolioResponse;
  viewMode?: "DEMO" | "PAPER";
  canTrade?: boolean;
}) {
  const positions = buildPortfolioPositions(data);
  const decayMarks = marksDecay(data.account.data_mode);
  const activeInstrument = data.active_instrument?.trim();
  const workspaceHref = activeInstrument
    ? `/workspace/${encodeURIComponent(activeInstrument)}`
    : "/workspace";

  return (
    <section
      className="panel portfolio-section portfolio-primary-section"
      id={PORTFOLIO_SECTIONS.positions}
      aria-labelledby="portfolio-positions-heading"
    >
      <div className="portfolio-section-head">
        <h2 id="portfolio-positions-heading">Positions</h2>
        <span className="portfolio-section-count">
          {positions.length} open
        </span>
      </div>
      <PortfolioPositionsTable
        positions={positions}
        marksDecay={decayMarks}
        workspaceHref={workspaceHref}
        canTrade={canTrade}
        maxOrderShares={data.risk.limits.max_order_shares}
      />
    </section>
  );
}

export function PortfolioAttentionSection({ data }: { data: PaperPortfolioResponse }) {
  const attention = buildPortfolioAttention(data);
  if (attention.length === 0) return null;
  return (
    <section
      className="panel portfolio-section"
      id={PORTFOLIO_SECTIONS.attention}
      aria-labelledby="portfolio-attention-heading"
    >
      <h2 id="portfolio-attention-heading">Needs attention</h2>
      <div className="portfolio-attention-stack">
        {attention.map((item) => (
          <AttentionBanner key={item.code} tone={item.tone} affects={item.affects} action={item.action}>
            {item.message}
          </AttentionBanner>
        ))}
      </div>
    </section>
  );
}

export function PaperPortfolioObservability({
  data,
  viewMode,
  onTraceOrder,
  hideOrdersSection = false,
  sections = PORTFOLIO_SECTION_IDS,
}: Props) {
  const { account, risk, data_health, fills } = data;
  const honesty = paperCapitalHonesty(viewMode);
  const show = (id: PortfolioSectionId) => sections.includes(id);
  const killSwitch = resolveSemanticState("portfolio", risk.kill_switch_active ? "ACTIVE" : "OFF");
  const reconciliation = resolveSemanticState(
    "portfolio",
    data.reconciliation_status ?? risk.reconciliation_status,
  );
  const dataHealth = resolveSemanticState("dataHealth", data_health.state);
  const execution = resolveSemanticState("executionAuthority", account.execution_authority);
  const executionMode = resolveSemanticState("executionAuthority", account.execution_mode);
  const dataMode = resolveSemanticState("session", account.data_mode);
  const activeInstrument = data.active_instrument?.trim();
  const workspaceHref = activeInstrument
    ? `/workspace/${encodeURIComponent(activeInstrument)}`
    : "/workspace";

  return (
    <div className="portfolio-operator">
      {show("honesty") ? (
        <AttentionBanner tone={honesty.tone} affects={honesty.affects}>
          {honesty.sentence}
        </AttentionBanner>
      ) : null}

      {show("glance") ? <PortfolioGlanceStrip data={data} /> : null}

      {show("positions") ? <PortfolioPositionsSection data={data} viewMode={viewMode} /> : null}

      {show("attention") ? <PortfolioAttentionSection data={data} /> : null}

      {show("account") ? (
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
          <Link to={workspaceHref}>{activeInstrument ? `${activeInstrument} Workspace` : "Workspace"}</Link>
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
      ) : null}

      {show("exposure") && exposureAvailable(data.exposure) ? (
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

      {show("fills") ? (
      <section
        className="panel portfolio-section"
        id={PORTFOLIO_SECTIONS.activity}
        aria-labelledby="portfolio-activity-heading"
      >
        <h2 id="portfolio-activity-heading">Fills</h2>
        {hideOrdersSection ? (
          <p className="muted">
            Snapshot fills only. Full order lifecycle is under{" "}
            <a href={`#${PORTFOLIO_SECTIONS.orderHistory}`}>Order history</a> above — not in this
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
      ) : null}
    </div>
  );
}

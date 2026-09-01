import { useProviderHealthQuery } from "../../api/hooks";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";

function channelState(entitled: boolean, verified: boolean): string {
  if (!entitled) return "UNAVAILABLE";
  return verified ? "HEALTHY" : "DEGRADED";
}

export function ProviderHealthPanel() {
  const healthQuery = useProviderHealthQuery();
  const health = healthQuery.data;
  if (!health?.available) {
    return (
      <section className="provider-health-panel capability-panel unavailable page">
        <h1>Provider diagnostics</h1>
        <p>{health?.reason ?? "Live observational mode disabled."}</p>
      </section>
    );
  }
  const lifecycle = health.lifecycle ?? {};
  const summary = health.provider_summary ?? {};
  const registry = health.capability_registry;
  const capabilities = registry?.capabilities ?? {};
  const l1 = capabilities.US_EQUITY_L1;
  const trades = capabilities.US_EQUITY_TICKER;
  const depth = capabilities.US_EQUITY_DEPTH;
  const executionUse =
    lifecycle.execution_use === "INTERNAL_PAPER_ELIGIBLE" ? "INTERNAL_PAPER_ELIGIBLE" : "DISPLAY_ONLY";
  return (
    <section className="provider-health-panel page">
      <h1>Provider diagnostics</h1>
      <h2>MOOMOO · {String(lifecycle.connection_state ?? "UNKNOWN")}</h2>
      <dl className="metric-list">
        <div>
          <dt>Provider</dt>
          <dd>{String(summary.provider ?? "MOOMOO")}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{String(lifecycle.provider_role ?? "MARKET_DATA")}</dd>
        </div>
        <div>
          <dt>OpenD</dt>
          <dd>{String(lifecycle.connection_state ?? summary.opend ?? "—")}</dd>
        </div>
        <div>
          <dt>Generation</dt>
          <dd>{String(lifecycle.provider_generation_id ?? summary.provider_generation ?? "—")}</dd>
        </div>
        <div>
          <dt>Market session</dt>
          <dd>{String(lifecycle.market_session ?? "—")}</dd>
        </div>
        <div>
          <dt>Basic quote</dt>
          <dd>{channelState(Boolean(l1?.account_entitled), Boolean(l1?.runtime_tested))}</dd>
        </div>
        <div>
          <dt>Trades</dt>
          <dd>{channelState(Boolean(trades?.account_entitled), Boolean(trades?.runtime_tested))}</dd>
        </div>
        <div>
          <dt>L2 depth</dt>
          <dd>{channelState(Boolean(depth?.account_entitled), Boolean(depth?.runtime_tested))}</dd>
        </div>
        <div>
          <dt>Execution eligibility</dt>
          <dd>{String(summary.execution_eligibility ?? executionUse)}</dd>
        </div>
        <div>
          <dt>Quote lag p50 / p95</dt>
          <dd>
            {String(summary.quote_lag_ms_p50 ?? "—")} / {String(summary.quote_lag_ms_p95 ?? "—")} ms
          </dd>
        </div>
        <div>
          <dt>Trade lag p50 / p95</dt>
          <dd>
            {String(summary.trade_lag_ms_p50 ?? "—")} / {String(summary.trade_lag_ms_p95 ?? "—")} ms
          </dd>
        </div>
        <div>
          <dt>Book lag p50 / p95</dt>
          <dd>
            {String(summary.book_lag_ms_p50 ?? "—")} / {String(summary.book_lag_ms_p95 ?? "—")} ms
          </dd>
        </div>
        <div>
          <dt>Queue high-water</dt>
          <dd>{String(summary.queue_high_water ?? "—")}</dd>
        </div>
        <div>
          <dt>Dropped events</dt>
          <dd>{String(summary.dropped ?? 0)}</dd>
        </div>
        <div>
          <dt>Duplicates</dt>
          <dd>{String(summary.duplicates ?? 0)}</dd>
        </div>
        <div>
          <dt>Reconnect count</dt>
          <dd>{String(lifecycle.reconnect_count ?? 0)}</dd>
        </div>
        <div>
          <dt>Quota</dt>
          <dd>
            {health.quota?.active_count ?? 0} / {health.quota?.max_quota ?? "?"}
          </dd>
        </div>
        <div>
          <dt>Last error</dt>
          <dd>{String(lifecycle.last_error ?? "—")}</dd>
        </div>
      </dl>
      <h3>Active subscriptions</h3>
      <ul>
        {(lifecycle.active_subscriptions ?? []).map((row) => (
          <li key={`${row.instrument_id}:${row.capability}`}>
            {row.instrument_id} · {row.capability} · refs {row.consumer_count}
          </li>
        ))}
      </ul>
      {health.execution_gate ? (
        <JsonDetailPanel title="Internal simulation gate" value={health.execution_gate} />
      ) : null}
      {health.finviz ? (
        <>
          <h2>FINVIZ ELITE · {String((health.finviz as { connection?: string }).connection ?? "UNKNOWN")}</h2>
          <dl className="metric-list">
            <div>
              <dt>Role</dt>
              <dd>{String((health.finviz as { role?: string }).role ?? "DISCOVERY / CONTEXT")}</dd>
            </div>
            <div>
              <dt>Authentication</dt>
              <dd>{String((health.finviz as { authentication?: string }).authentication ?? "—")}</dd>
            </div>
            <div>
              <dt>Credential source</dt>
              <dd>{String((health.finviz as { credential_source?: string }).credential_source ?? "—")}</dd>
            </div>
            <div>
              <dt>Credential generation</dt>
              <dd>{String((health.finviz as { finviz_credential_generation?: number }).finviz_credential_generation ?? "—")}</dd>
            </div>
            <div>
              <dt>Recovery mode</dt>
              <dd>{String((health.finviz as { recovery_mode?: string }).recovery_mode ?? "—")}</dd>
            </div>
            <div>
              <dt>Last auth error</dt>
              <dd>{String((health.finviz as { last_auth_error?: string }).last_auth_error ?? "NONE")}</dd>
            </div>
          </dl>
          {(health.finviz as { authentication?: string }).authentication?.startsWith("AUTH_") ? (
            <p className="auth-repair-hint">
              Finviz authentication requires operator action. Run: python tools/finviz/auth.py repair
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

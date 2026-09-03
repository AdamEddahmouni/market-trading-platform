import type { WorkspaceFuturesResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  futures: WorkspaceFuturesResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FuturesWorkspacePanel({
  instrumentId,
  futures,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading futures depth evidence…</div>;
  }

  if (!futures?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Futures / ES Depth</h2>
        <p>UNAVAILABLE — {futures?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Futures depth fixture is entitled for ES only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const snapshots = futures.snapshots ?? [];
  const latest = snapshots[snapshots.length - 1];
  const liquidity = futures.latest_liquidity_summary ?? {
    depth_withdrawal: latest?.depth_withdrawal,
    fragility_score: latest?.fragility_score,
    resiliency_score: latest?.resiliency_score,
    liquidity_method: latest?.liquidity_method,
  };
  const impact = futures.latest_impact_summary ?? {
    impact_regime: latest?.impact_regime,
    absorption_score: latest?.absorption_score,
    exhaustion_score: latest?.exhaustion_score,
    price_efficiency: latest?.price_efficiency,
    impact_method: latest?.impact_method,
    impact_quality_flags: latest?.impact_quality_flags,
  };
  const forecast = futures.latest_microstructure_forecast ?? {
    direction_bias: latest?.direction_bias,
    continuation_probability: latest?.continuation_probability,
    reversal_probability: latest?.reversal_probability,
    expected_mid_delta: latest?.expected_mid_delta,
    forecast_method: latest?.forecast_method,
    forecast_quality_flags: latest?.forecast_quality_flags,
  };
  const execution = futures.latest_execution_forecast ?? {
    aggressive_fill_probability: latest?.aggressive_fill_probability,
    expected_slippage_spread_fraction: latest?.expected_slippage_spread_fraction,
    adverse_selection_risk: latest?.adverse_selection_risk,
    execution_method: latest?.execution_method,
  };
  const curve = futures.curve_snapshot;
  const carry = futures.carry_observation;
  const positioning = futures.positioning_snapshot;
  const oiHypothesis = futures.oi_velocity_hypothesis;
  const trendBaseline = futures.trend_baseline_snapshot;
  const carryBaseline = futures.carry_baseline;
  const curveMomentum = futures.curve_momentum;
  const familyContext = futures.family_context_snapshot;
  const macroEvent = futures.macro_event_snapshot;
  const leverageStress = futures.leverage_stress_snapshot;

  return (
    <section className="futures-panel">
      <header className="panel-header">
        <h2>Futures / ES Depth</h2>
        <p>{futures.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:futures:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:futures:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>
          Research-only {futures.provenance ?? "fixture"} projection
          {futures.synthetic ? " (synthetic)" : ""}
        </span>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>Contract month</dt>
          <dd>{futures.contract_month ?? latest?.contract_month ?? "—"}</dd>
        </div>
        <div>
          <dt>Exchange</dt>
          <dd>{futures.exchange ?? latest?.exchange ?? "CME"}</dd>
        </div>
        <div>
          <dt>Session</dt>
          <dd>{futures.session_state ?? latest?.session_state ?? "—"}</dd>
        </div>
        <div>
          <dt>Imbalance signal</dt>
          <dd>{futures.latest_imbalance_signal ?? latest?.imbalance_signal ?? "—"}</dd>
        </div>
        <div>
          <dt>Imbalance ratio</dt>
          <dd>{String(futures.latest_imbalance_ratio ?? latest?.imbalance_ratio ?? "—")}</dd>
        </div>
        <div>
          <dt>OFI</dt>
          <dd>{String(futures.latest_ofi_value ?? latest?.ofi_value ?? "—")}</dd>
        </div>
        {liquidity.fragility_score != null ? (
          <div>
            <dt>Fragility score</dt>
            <dd>{String(liquidity.fragility_score)}</dd>
          </div>
        ) : null}
        {liquidity.depth_withdrawal != null && liquidity.depth_withdrawal > 0 ? (
          <div>
            <dt>Depth withdrawal</dt>
            <dd>{String(liquidity.depth_withdrawal)}</dd>
          </div>
        ) : null}
        {impact.impact_regime && impact.impact_regime !== "NEUTRAL" ? (
          <div>
            <dt>Book flow regime</dt>
            <dd>{String(impact.impact_regime)}</dd>
          </div>
        ) : null}
        {impact.impact_quality_flags?.includes("MISSING_TRADE_FLOW") ? (
          <div>
            <dt>Impact quality</dt>
            <dd>Trade flow missing — absorption not asserted</dd>
          </div>
        ) : null}
        {forecast.direction_bias && forecast.direction_bias !== "NEUTRAL" ? (
          <div>
            <dt>Micro forecast bias</dt>
            <dd>{String(forecast.direction_bias)}</dd>
          </div>
        ) : null}
        {forecast.continuation_probability != null ? (
          <div>
            <dt>Continuation prob</dt>
            <dd>{String(forecast.continuation_probability)}</dd>
          </div>
        ) : null}
        {forecast.reversal_probability != null ? (
          <div>
            <dt>Reversal prob</dt>
            <dd>{String(forecast.reversal_probability)}</dd>
          </div>
        ) : null}
        {forecast.forecast_quality_flags?.includes("MISSING_TRADE_FLOW") ? (
          <div>
            <dt>Forecast quality</dt>
            <dd>Trade flow missing — book-only micro forecast</dd>
          </div>
        ) : null}
        {execution.aggressive_fill_probability != null ? (
          <div>
            <dt>Aggressive fill prob</dt>
            <dd>{String(execution.aggressive_fill_probability)}</dd>
          </div>
        ) : null}
        {execution.expected_slippage_spread_fraction != null ? (
          <div>
            <dt>Expected slippage</dt>
            <dd>{String(execution.expected_slippage_spread_fraction)}</dd>
          </div>
        ) : null}
        {execution.adverse_selection_risk != null ? (
          <div>
            <dt>Adverse selection risk</dt>
            <dd>{String(execution.adverse_selection_risk)}</dd>
          </div>
        ) : null}
        {execution.execution_method ? (
          <div>
            <dt>Execution method</dt>
            <dd>{execution.execution_method}</dd>
          </div>
        ) : null}
        {curve?.available && curve.regime ? (
          <div>
            <dt>Curve regime</dt>
            <dd>{curve.regime}</dd>
          </div>
        ) : null}
        {carry?.available && carry.annualized_carry != null ? (
          <div>
            <dt>Annualized carry</dt>
            <dd>{String(carry.annualized_carry)}</dd>
          </div>
        ) : null}
        {futures.futures_positioning_available && positioning?.net != null ? (
          <div>
            <dt>COT net ({positioning.participant_category ?? "managed_money"})</dt>
            <dd>{String(positioning.net)}</dd>
          </div>
        ) : null}
        {positioning?.net_percentile != null ? (
          <div>
            <dt>COT net percentile</dt>
            <dd>{String(positioning.net_percentile)}</dd>
          </div>
        ) : null}
        {futures.crowding_regime && futures.crowding_regime !== "NEUTRAL" ? (
          <div>
            <dt>Crowding regime</dt>
            <dd>{futures.crowding_regime}</dd>
          </div>
        ) : null}
        {positioning?.publication_time ? (
          <div>
            <dt>COT publication time</dt>
            <dd>{positioning.publication_time}</dd>
          </div>
        ) : null}
        {oiHypothesis?.label && oiHypothesis.label !== "UNAVAILABLE" ? (
          <div>
            <dt>OI velocity hypothesis</dt>
            <dd>{oiHypothesis.label}</dd>
          </div>
        ) : null}
        {futures.futures_baselines_available && trendBaseline?.trend_3m != null ? (
          <div>
            <dt>Vol-scaled trend (3m)</dt>
            <dd>{String(trendBaseline.trend_3m)}</dd>
          </div>
        ) : null}
        {trendBaseline?.trend_1m != null ? (
          <div>
            <dt>Vol-scaled trend (1m)</dt>
            <dd>{String(trendBaseline.trend_1m)}</dd>
          </div>
        ) : null}
        {carryBaseline?.carry_percentile != null ? (
          <div>
            <dt>Carry percentile</dt>
            <dd>{String(carryBaseline.carry_percentile)}</dd>
          </div>
        ) : null}
        {curveMomentum?.calendar_spread_momentum ? (
          <div>
            <dt>Curve momentum</dt>
            <dd>{curveMomentum.calendar_spread_momentum}</dd>
          </div>
        ) : null}
        {futures.trend_regime && futures.trend_regime !== "NEUTRAL" ? (
          <div>
            <dt>Trend regime</dt>
            <dd>{futures.trend_regime}</dd>
          </div>
        ) : null}
        {futures.futures_family_available && familyContext?.family ? (
          <div>
            <dt>Family model</dt>
            <dd>{familyContext.family}</dd>
          </div>
        ) : null}
        {familyContext?.curve_read ? (
          <div>
            <dt>Family curve read</dt>
            <dd>{familyContext.curve_read}</dd>
          </div>
        ) : null}
        {familyContext?.positioning_read ? (
          <div>
            <dt>Family positioning read</dt>
            <dd>{familyContext.positioning_read}</dd>
          </div>
        ) : null}
        {futures.futures_macro_available && macroEvent?.upcoming_event_type ? (
          <div>
            <dt>Upcoming macro event</dt>
            <dd>{macroEvent.upcoming_event_type}</dd>
          </div>
        ) : null}
        {futures.macro_risk_regime && futures.macro_risk_regime !== "UNAVAILABLE" ? (
          <div>
            <dt>Macro risk regime</dt>
            <dd>{futures.macro_risk_regime}</dd>
          </div>
        ) : null}
        {futures.event_window_active ? (
          <div>
            <dt>Macro event window</dt>
            <dd>Active</dd>
          </div>
        ) : null}
        {macroEvent?.surprise_zscore != null ? (
          <div>
            <dt>Macro surprise (z)</dt>
            <dd>{String(macroEvent.surprise_zscore)}</dd>
          </div>
        ) : null}
        {futures.futures_leverage_stress_available && leverageStress?.stress_regime ? (
          <div>
            <dt>Leverage stress regime</dt>
            <dd>{leverageStress.stress_regime}</dd>
          </div>
        ) : null}
        {leverageStress?.margin_percentile != null ? (
          <div>
            <dt>Margin percentile</dt>
            <dd>{String(leverageStress.margin_percentile)}</dd>
          </div>
        ) : null}
        {leverageStress?.effective_leverage != null ? (
          <div>
            <dt>Effective leverage</dt>
            <dd>{String(leverageStress.effective_leverage)}</dd>
          </div>
        ) : null}
        {futures.long_liquidation_risk ? (
          <div>
            <dt>Long liquidation risk</dt>
            <dd>Elevated</dd>
          </div>
        ) : null}
        {futures.short_liquidation_risk ? (
          <div>
            <dt>Short liquidation risk</dt>
            <dd>Elevated</dd>
          </div>
        ) : null}
        {futures.latest_futures_forecast?.futures_model_version ? (
          <div>
            <dt>F11 model</dt>
            <dd>{futures.latest_futures_forecast.futures_model_version}</dd>
          </div>
        ) : null}
        {futures.latest_futures_forecast?.outright_up_probability != null ? (
          <div>
            <dt>Outright up probability</dt>
            <dd>{String(futures.latest_futures_forecast.outright_up_probability)}</dd>
          </div>
        ) : null}
        {futures.latest_futures_forecast?.curve_steepen_probability != null ? (
          <div>
            <dt>Curve steepen probability</dt>
            <dd>{String(futures.latest_futures_forecast.curve_steepen_probability)}</dd>
          </div>
        ) : null}
        {futures.latest_futures_forecast?.direction_bias ? (
          <div>
            <dt>F11 direction bias</dt>
            <dd>{futures.latest_futures_forecast.direction_bias}</dd>
          </div>
        ) : null}
      </dl>

      {oiHypothesis?.disclaimer ? (
        <p className="workspace-hint">{oiHypothesis.disclaimer}</p>
      ) : null}
      {futures.futures_baselines_available ? (
        <p className="workspace-hint">
          Baseline features ≠ directional forecast; positive carry ≠ positive return.
        </p>
      ) : null}
      {futures.futures_positioning_available ? (
        <p className="workspace-hint">
          COT positioning is distinct from depth-derived whale family futures_positioning.
        </p>
      ) : null}
      {futures.futures_macro_available ? (
        <p className="workspace-hint">
          Macro calendar is Futures-owned event risk — distinct from equity public_catalyst whale family.
        </p>
      ) : null}
      {futures.futures_leverage_stress_available && leverageStress?.disclaimer ? (
        <p className="workspace-hint">{leverageStress.disclaimer}</p>
      ) : null}
      {futures.futures_family_available ? (
        <p className="workspace-hint">
          Family context is interpretive metadata — not a directional forecast or universal Futures Score.
        </p>
      ) : null}
      {futures.latest_futures_forecast?.research_only ? (
        <p className="workspace-hint">
          F11 engineered baseline is research-only and experimental — not a trade recommendation.
        </p>
      ) : null}

      {latest ? (
        <dl className="metric-grid">
          <div>
            <dt>Best bid</dt>
            <dd>{String(latest.best_bid)}</dd>
          </div>
          <div>
            <dt>Best ask</dt>
            <dd>{String(latest.best_ask)}</dd>
          </div>
          <div>
            <dt>RTH</dt>
            <dd>{latest.rth ? "Yes" : "No"}</dd>
          </div>
        </dl>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Best bid</th>
            <th>Best ask</th>
            <th>Imbalance</th>
            <th>Signal</th>
            <th>OFI</th>
            <th>Session</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.best_bid}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.best_bid ?? "—"}</td>
              <td>{row.best_ask ?? "—"}</td>
              <td>{row.imbalance_ratio ?? "—"}</td>
              <td>{row.imbalance_signal ?? "—"}</td>
              <td>{row.ofi_value ?? "—"}</td>
              <td>{row.session_state ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

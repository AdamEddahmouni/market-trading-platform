import type { WorkspaceOrderBookResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  orderBook: WorkspaceOrderBookResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderBookWorkspacePanel({
  instrumentId,
  orderBook,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading order-book evidence…</div>;
  }

  if (!orderBook?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Order Book / Depth</h2>
        <p>UNAVAILABLE — {orderBook?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Order-book fixture is entitled for NVDA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const snapshots = orderBook.snapshots ?? [];
  const latest = snapshots[snapshots.length - 1];
  const ofiMethod = orderBook.latest_ofi_method ?? latest?.ofi_method;
  const ofiVersion = orderBook.latest_ofi_version ?? latest?.ofi_version;
  const bookStateValid = orderBook.latest_book_state_valid ?? latest?.book_state_valid;
  const liquidity = orderBook.latest_liquidity_summary ?? {
    depth_withdrawal: latest?.depth_withdrawal,
    depth_replenishment: latest?.depth_replenishment,
    fragility_score: latest?.fragility_score,
    resiliency_score: latest?.resiliency_score,
    liquidity_method: latest?.liquidity_method,
  };
  const impact = orderBook.latest_impact_summary ?? {
    impact_regime: latest?.impact_regime,
    absorption_score: latest?.absorption_score,
    exhaustion_score: latest?.exhaustion_score,
    price_efficiency: latest?.price_efficiency,
    impact_method: latest?.impact_method,
  };
  const forecast = orderBook.latest_microstructure_forecast ?? {
    direction_bias: latest?.direction_bias,
    continuation_probability: latest?.continuation_probability,
    reversal_probability: latest?.reversal_probability,
    expected_mid_delta: latest?.expected_mid_delta,
    forecast_method: latest?.forecast_method,
  };
  const execution = orderBook.latest_execution_forecast ?? {
    aggressive_fill_probability: latest?.aggressive_fill_probability,
    passive_fill_probability: latest?.passive_fill_probability,
    expected_slippage_spread_fraction: latest?.expected_slippage_spread_fraction,
    adverse_selection_risk: latest?.adverse_selection_risk,
    execution_method: latest?.execution_method,
  };

  return (
    <section className="order-book-panel">
      <header className="panel-header">
        <h2>Order Book / Depth</h2>
        <p>{orderBook.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:order-book:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:order-book:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection — snapshot provenance retained</span>
      </div>

      {bookStateValid === false ? (
        <p className="workspace-hint workspace-warning">
          Book state invalid for latest OFI — metrics fail-closed per OF4 book validation.
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
            <dt>Imbalance ratio</dt>
            <dd>{String(latest.imbalance_ratio)}</dd>
          </div>
          <div>
            <dt>OFI</dt>
            <dd>{String(orderBook.latest_ofi_value ?? latest.ofi_value)}</dd>
          </div>
          {ofiMethod ? (
            <div>
              <dt>OFI method</dt>
              <dd>{ofiMethod}</dd>
            </div>
          ) : null}
          {ofiVersion ? (
            <div>
              <dt>OFI version</dt>
              <dd>{ofiVersion}</dd>
            </div>
          ) : null}
          {liquidity.depth_withdrawal != null && liquidity.depth_withdrawal > 0 ? (
            <div>
              <dt>Depth withdrawal</dt>
              <dd>{String(liquidity.depth_withdrawal)}</dd>
            </div>
          ) : null}
          {liquidity.depth_replenishment != null && liquidity.depth_replenishment > 0 ? (
            <div>
              <dt>Depth replenishment</dt>
              <dd>{String(liquidity.depth_replenishment)}</dd>
            </div>
          ) : null}
          {liquidity.fragility_score != null ? (
            <div>
              <dt>Fragility score</dt>
              <dd>{String(liquidity.fragility_score)}</dd>
            </div>
          ) : null}
          {liquidity.resiliency_score != null ? (
            <div>
              <dt>Resiliency</dt>
              <dd>{String(liquidity.resiliency_score)}</dd>
            </div>
          ) : null}
          {liquidity.liquidity_method ? (
            <div>
              <dt>Liquidity method</dt>
              <dd>{liquidity.liquidity_method}</dd>
            </div>
          ) : null}
          {impact.impact_regime && impact.impact_regime !== "NEUTRAL" ? (
            <div>
              <dt>Book flow regime</dt>
              <dd>{String(impact.impact_regime)}</dd>
            </div>
          ) : null}
          {impact.absorption_score != null ? (
            <div>
              <dt>Absorption score</dt>
              <dd>{String(impact.absorption_score)}</dd>
            </div>
          ) : null}
          {impact.exhaustion_score != null ? (
            <div>
              <dt>Exhaustion score</dt>
              <dd>{String(impact.exhaustion_score)}</dd>
            </div>
          ) : null}
          {impact.price_efficiency != null ? (
            <div>
              <dt>Price efficiency</dt>
              <dd>{String(impact.price_efficiency)}</dd>
            </div>
          ) : null}
          {impact.impact_method ? (
            <div>
              <dt>Impact method</dt>
              <dd>{impact.impact_method}</dd>
            </div>
          ) : null}
          <p className="workspace-hint">
            Book flow absorption/exhaustion — not Short Squeeze lifecycle exhaustion.
          </p>
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
          {forecast.expected_mid_delta != null ? (
            <div>
              <dt>Expected mid delta</dt>
              <dd>{String(forecast.expected_mid_delta)}</dd>
            </div>
          ) : null}
          {forecast.forecast_method ? (
            <div>
              <dt>Forecast method</dt>
              <dd>{forecast.forecast_method}</dd>
            </div>
          ) : null}
          <p className="workspace-hint">
            Short-horizon microstructure — not multi-day physical P (SHARED P2).
          </p>
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
          <p className="workspace-hint">
            Book-aware execution forecast — not Options O9 lifecycle simulation.
          </p>
          <div>
            <dt>Direction</dt>
            <dd>{String(latest.direction_label)}</dd>
          </div>
          <div>
            <dt>Levels</dt>
            <dd>{String(latest.level_count)}</dd>
          </div>
        </dl>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Best bid</th>
            <th>Bid size</th>
            <th>Best ask</th>
            <th>Ask size</th>
            <th>Imbalance</th>
            <th>OFI</th>
            <th>Direction</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.best_bid}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.best_bid ?? "—"}</td>
              <td>{row.bid_size ?? "—"}</td>
              <td>{row.best_ask ?? "—"}</td>
              <td>{row.ask_size ?? "—"}</td>
              <td>{row.imbalance_ratio ?? "—"}</td>
              <td>{row.ofi_value ?? "—"}</td>
              <td>{row.direction_label ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

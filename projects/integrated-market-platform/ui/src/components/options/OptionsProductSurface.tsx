import { lazy, Suspense } from "react";
import type { OptionsProductResponse } from "../../api/schemas";
import { canUsePaperActions } from "../mode-session/modeAuthority";
import type { Mode } from "../mode-session/types";

const DerivativePaperPreviewPanel = lazy(() =>
  import("../paper-derivative/DerivativePaperPreviewPanel").then((module) => ({
    default: module.DerivativePaperPreviewPanel,
  })),
);

type Props = {
  mode: Mode;
  instrumentId: string;
  product: OptionsProductResponse | null;
  loading?: boolean;
  paperActionsPermitted?: boolean;
};

function unknownMetric(value: number | null | undefined): string {
  if (value === null || value === undefined) return "unknown";
  return String(value);
}

export function OptionsProductSurface({
  mode,
  instrumentId,
  product,
  loading = false,
  paperActionsPermitted = false,
}: Props) {
  if (loading) return <p role="status">Loading options product surface…</p>;
  if (!product) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Options product</h2>
        <p>UNAVAILABLE — no payload</p>
      </aside>
    );
  }

  const analytics = product.analytics;
  const greeks = analytics?.greeks ?? {};
  const paperActionsAvailable = canUsePaperActions(mode, paperActionsPermitted, undefined);
  const chainStatus = product.chain_status ?? product.status;

  return (
    <section className="options-product-surface" aria-label="Options product surface">
      <header className="panel-header">
        <h2>Options · {instrumentId}</h2>
        <p>
          Status <strong>{product.status}</strong>
          {product.reason ? ` — ${product.reason}` : ""}
        </p>
        <p>
          Chain <strong>{chainStatus}</strong>
          {chainStatus === "EMPTY" ? " (zero contracts)" : ""}
        </p>
      </header>

      {product.identity ? (
        <dl className="metric-grid">
          <div><dt>Expiry</dt><dd>{String(product.identity.expiry ?? "—")}</dd></div>
          <div><dt>Strike</dt><dd>{String(product.identity.strike ?? "—")}</dd></div>
          <div><dt>Right</dt><dd>{String(product.identity.right ?? "—")}</dd></div>
          <div><dt>Multiplier</dt><dd>{String(product.identity.multiplier ?? "—")}</dd></div>
        </dl>
      ) : null}

      <dl className="metric-grid">
        <div><dt>IV</dt><dd>{unknownMetric(analytics?.iv)}</dd></div>
        <div><dt>Delta</dt><dd>{unknownMetric(greeks.delta)}</dd></div>
        <div><dt>Gamma</dt><dd>{unknownMetric(greeks.gamma)}</dd></div>
        <div><dt>OI</dt><dd>{unknownMetric(analytics?.open_interest)}</dd></div>
      </dl>

      {product.position ? (
        <aside className="paper-position-panel">
          <h3>Paper position (CanonicalPortfolio)</h3>
          <p>
            {String(product.position.quantity)} {String(product.position.quantity_unit ?? "CONTRACTS")}
          </p>
        </aside>
      ) : (
        <p className="muted">No canonical Paper position for this contract.</p>
      )}

      {product.short_open_risk ? (
        <p role="status">Short-open risk: {product.short_open_risk}</p>
      ) : null}

      {mode === "LIVE" ? (
        <p className="workspace-hint">Live mode is observational only — execution unavailable.</p>
      ) : null}

      {product.execution_available && paperActionsAvailable ? (
        <Suspense fallback={null}>
          <DerivativePaperPreviewPanel
            mode={mode}
            instrumentId={instrumentId}
            paperActionsAvailable={paperActionsAvailable}
          />
        </Suspense>
      ) : null}

      {product.orders.length > 0 ? (
        <ul>
          {product.orders.map((order) => (
            <li key={String(order.order_id ?? order.client_order_id ?? order.instrument_id)}>
              {String(order.state ?? "UNKNOWN")} · qty {String(order.quantity ?? "—")}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

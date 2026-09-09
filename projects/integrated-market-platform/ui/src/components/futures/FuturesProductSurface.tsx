import { lazy, Suspense } from "react";
import type { FuturesProductResponse } from "../../api/schemas";
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
  product: FuturesProductResponse | null;
  loading?: boolean;
  paperActionsPermitted?: boolean;
};

export function FuturesProductSurface({
  mode,
  instrumentId,
  product,
  loading = false,
  paperActionsPermitted = false,
}: Props) {
  if (loading) return <p role="status">Loading futures product surface…</p>;
  if (!product) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Futures product</h2>
        <p>UNAVAILABLE — no payload</p>
      </aside>
    );
  }

  const margin = product.exposure?.margin;
  const paperActionsAvailable = canUsePaperActions(mode, paperActionsPermitted, undefined);
  const nonActionable =
    product.status === "UNSUPPORTED_INSTRUMENT" ||
    product.identity?.instrument_kind === "FUTURE_FAMILY" ||
    product.identity?.instrument_kind === "CONTINUOUS_SERIES";

  return (
    <section className="futures-product-surface" aria-label="Futures product surface">
      <header className="panel-header">
        <h2>Futures · {instrumentId}</h2>
        <p>
          Status <strong>{product.status}</strong>
          {product.reason ? ` — ${product.reason}` : ""}
        </p>
      </header>

      {product.identity ? (
        <dl className="metric-grid">
          <div><dt>Kind</dt><dd>{String(product.identity.instrument_kind ?? "—")}</dd></div>
          <div><dt>Expiry</dt><dd>{String(product.identity.expiry ?? "—")}</dd></div>
          <div><dt>Venue</dt><dd>{String(product.identity.venue ?? "—")}</dd></div>
          <div><dt>Multiplier</dt><dd>{String(product.identity.multiplier ?? "—")}</dd></div>
        </dl>
      ) : null}

      <dl className="metric-grid">
        <div><dt>Notional exposure</dt><dd>{product.exposure?.notional ?? "unknown"}</dd></div>
        <div><dt>Margin state</dt><dd>{String(margin?.state ?? "NOT_APPLICABLE")}</dd></div>
        <div><dt>Cash semantics</dt><dd>{product.exposure?.cash_debit_semantics ?? "—"}</dd></div>
      </dl>

      {margin?.state === "AVAILABLE" ? (
        <p className="workspace-hint">
          Margin facts from {String(margin.provider)} ({margin.fixture_semantics ? "fixture/demo" : "explicit"}).
        </p>
      ) : null}
      {margin?.state === "MARGIN_MISSING" ? (
        <p role="status">Margin facts missing — submit blocked until authoritative facts exist.</p>
      ) : null}

      {nonActionable ? (
        <p role="status">Reference identity — not executable in Paper workflow.</p>
      ) : null}

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

      {mode === "LIVE" ? (
        <p className="workspace-hint">Live mode is observational only — execution unavailable.</p>
      ) : null}

      {product.execution_available && !nonActionable && paperActionsAvailable ? (
        <Suspense fallback={null}>
          <DerivativePaperPreviewPanel
            mode={mode}
            instrumentId={instrumentId}
            paperActionsAvailable={paperActionsAvailable}
          />
        </Suspense>
      ) : null}
    </section>
  );
}

import type { DealerSnapshot } from "../../api/schemas";

type Props = {
  snapshot: DealerSnapshot | null | undefined;
  onExplain?: (ref: string) => void;
};

export function DealerPositioningBlock({ snapshot, onExplain }: Props) {
  if (!snapshot) {
    return null;
  }

  if (!snapshot.available) {
    return (
      <section className="dealer-positioning-block unavailable">
        <h3>Dealer positioning (O6)</h3>
        <p>{snapshot.reason ?? "DEALER_POSITION_UNKNOWN"}</p>
      </section>
    );
  }

  const gammaAmplification =
    snapshot.estimated_dealer_gamma !== undefined &&
    Math.abs(snapshot.estimated_dealer_gamma) >= 0.5;

  return (
    <section className="dealer-positioning-block available">
      <h3>Dealer positioning (O6)</h3>
      <p className="dealer-disclaimer">
        Estimated dealer gamma proxy — not confirmed dealer positioning.
      </p>
      <dl className="metric-grid">
        <div>
          <dt>Gamma regime</dt>
          <dd>{snapshot.gamma_regime ?? "—"}</dd>
        </div>
        <div>
          <dt>Est. dealer gamma</dt>
          <dd>{snapshot.estimated_dealer_gamma ?? "—"}</dd>
        </div>
        <div>
          <dt>Est. dealer delta</dt>
          <dd>{snapshot.estimated_dealer_delta ?? "—"}</dd>
        </div>
        <div>
          <dt>Hedging pressure</dt>
          <dd>{snapshot.hedging_pressure_estimate ?? "—"}</dd>
        </div>
        <div>
          <dt>Gamma amplification</dt>
          <dd>{gammaAmplification ? "elevated" : "normal"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{snapshot.confidence ?? "—"}</dd>
        </div>
        <div>
          <dt>OI-backed contracts</dt>
          <dd>{snapshot.oi_backed_contract_count ?? "—"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{snapshot.dealer_version ?? snapshot.method ?? "—"}</dd>
        </div>
      </dl>
      {snapshot.quality_flags && snapshot.quality_flags.length > 0 ? (
        <p className="dealer-quality">Flags: {snapshot.quality_flags.join(", ")}</p>
      ) : null}
      {onExplain ? (
        <button type="button" onClick={() => onExplain("options:dealer:gamma")}>
          Trace dealer estimate
        </button>
      ) : null}
    </section>
  );
}

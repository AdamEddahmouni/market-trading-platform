import type { OpportunitySnapshot } from "../../api/schemas";

type Props = {
  snapshot: OpportunitySnapshot | null | undefined;
  onExplain?: (ref: string) => void;
};

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

function ComponentPanel({
  title,
  component,
  onExplain,
}: {
  title: string;
  component: Record<string, unknown> | undefined;
  onExplain?: (ref: string) => void;
}) {
  if (!component) {
    return null;
  }

  const entries = Object.entries(component).filter(
    ([key]) => !["available", "source_ref", "quality_flags", "reason"].includes(key),
  );
  const sourceRef = typeof component.source_ref === "string" ? component.source_ref : undefined;

  return (
    <div className="opportunity-component-panel">
      <h4>{title}</h4>
      <dl className="metric-grid compact">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{key.replace(/_/g, " ")}</dt>
            <dd>{value === null || value === undefined ? "—" : String(value)}</dd>
          </div>
        ))}
      </dl>
      {component.quality_flags && Array.isArray(component.quality_flags) && component.quality_flags.length > 0 ? (
        <p className="opportunity-quality">Flags: {component.quality_flags.join(", ")}</p>
      ) : null}
      {sourceRef && onExplain ? (
        <button type="button" onClick={() => onExplain(sourceRef)}>
          Trace {title.toLowerCase()}
        </button>
      ) : null}
    </div>
  );
}

export function OpportunityFusionBlock({ snapshot, onExplain }: Props) {
  if (!snapshot) {
    return null;
  }

  if (!snapshot.available) {
    return (
      <section className="opportunity-fusion-block unavailable">
        <h3>Cross-lane opportunity fusion (SHARED P4)</h3>
        <p className="opportunity-outcome">UNAVAILABLE</p>
        <p>{snapshot.reason ?? "FUSION_UNAVAILABLE"}</p>
        {snapshot.disclaimer ? <p className="opportunity-disclaimer">{snapshot.disclaimer}</p> : null}
      </section>
    );
  }

  const fusion = snapshot.fusion;
  const probability = snapshot.probability as Record<string, unknown> | undefined;
  const payoff = snapshot.payoff as Record<string, unknown> | undefined;
  const costs = snapshot.costs as Record<string, unknown> | undefined;
  const liquidity = snapshot.liquidity as Record<string, unknown> | undefined;

  return (
    <section className={`opportunity-fusion-block ${snapshot.outcome === "RANKED" ? "ranked" : "no-edge"}`}>
      <h3>Cross-lane opportunity fusion (SHARED P4)</h3>
      <p className="opportunity-disclaimer">
        {snapshot.disclaimer ??
          "Cross-lane EV fusion — research decomposition, not a trade recommendation."}
      </p>
      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Platform-owned fusion — lanes supply inputs only</span>
      </div>
      <dl className="metric-grid">
        <div>
          <dt>Outcome</dt>
          <dd className="opportunity-outcome">{snapshot.outcome ?? snapshot.status ?? "—"}</dd>
        </div>
        <div>
          <dt>Fused net EV</dt>
          <dd>{formatNumber(snapshot.fused_net_ev)}</dd>
        </div>
        <div>
          <dt>Occurrence weight</dt>
          <dd>{formatNumber(fusion?.occurrence_weight)}</dd>
        </div>
        <div>
          <dt>Liquidity factor</dt>
          <dd>{formatNumber(fusion?.liquidity_factor)}</dd>
        </div>
        <div>
          <dt>Gross EV (pre-weights)</dt>
          <dd>{formatNumber(fusion?.gross_ev_before_weights)}</dd>
        </div>
        <div>
          <dt>Template</dt>
          <dd>{fusion?.template ?? "—"}</dd>
        </div>
        <div>
          <dt>Squeeze aligned</dt>
          <dd>{fusion?.squeeze_aligned ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{snapshot.model_version ?? snapshot.method ?? "—"}</dd>
        </div>
      </dl>
      {snapshot.quality_flags && snapshot.quality_flags.length > 0 ? (
        <p className="opportunity-quality">Quality flags: {snapshot.quality_flags.join(", ")}</p>
      ) : null}
      {snapshot.replay_hash ? (
        <p className="opportunity-replay-hash">Replay hash: {snapshot.replay_hash}</p>
      ) : null}
      <div className="opportunity-components-grid">
        <ComponentPanel title="Probability" component={probability} onExplain={onExplain} />
        <ComponentPanel title="Payoff" component={payoff} onExplain={onExplain} />
        <ComponentPanel title="Costs" component={costs} onExplain={onExplain} />
        <ComponentPanel title="Liquidity" component={liquidity} onExplain={onExplain} />
      </div>
    </section>
  );
}

import type { WorkspaceSqueezeResponse } from "../../api/client";

type Props = {
  squeeze: WorkspaceSqueezeResponse;
};

export function CausalIntelligenceBlock({ squeeze }: Props) {
  const causal = squeeze.causal_intelligence;
  if (!causal) {
    return null;
  }

  return (
    <section className="squeeze-causal-block">
      <h3>Causal intelligence</h3>
      <p className="squeeze-causal-summary">{causal.explanation?.summary ?? "No summary."}</p>
      <dl className="squeeze-causal-grid">
        <div>
          <dt>Model</dt>
          <dd>{causal.model_version}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{causal.overall_confidence}</dd>
        </div>
        <div>
          <dt>Research status</dt>
          <dd>{causal.research_status ?? "EXPERIMENTAL"}</dd>
        </div>
        {causal.vulnerability != null ? (
          <div>
            <dt>Vulnerability</dt>
            <dd>{causal.vulnerability}</dd>
          </div>
        ) : null}
        {causal.ignition_strength != null ? (
          <div>
            <dt>Ignition</dt>
            <dd>{causal.ignition_strength}</dd>
          </div>
        ) : null}
        {causal.remaining_fuel != null ? (
          <div>
            <dt>Remaining fuel</dt>
            <dd>{causal.remaining_fuel}</dd>
          </div>
        ) : null}
      </dl>
      {causal.mechanism_labels && causal.mechanism_labels.length > 0 ? (
        <p className="squeeze-mechanisms">
          Mechanisms: {causal.mechanism_labels.join(", ")}
        </p>
      ) : null}
      {causal.missing_capabilities && causal.missing_capabilities.length > 0 ? (
        <p className="squeeze-missing-capabilities">
          Missing: {causal.missing_capabilities.slice(0, 5).join(", ")}
          {causal.missing_capabilities.length > 5 ? "…" : ""}
        </p>
      ) : null}
      {causal.horizon_probabilities && causal.horizon_probabilities.length > 0 ? (
        <p className="squeeze-horizons-note">
          Horizon probabilities are {causal.horizon_probabilities[0]?.status ?? "unavailable"} until
          calibrated models are validated.
        </p>
      ) : null}
    </section>
  );
}

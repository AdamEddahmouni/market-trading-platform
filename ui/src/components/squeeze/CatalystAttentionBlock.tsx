import type { WorkspaceSqueezeResponse } from "../../api/client";

type Props = {
  squeeze: WorkspaceSqueezeResponse;
};

export function CatalystAttentionBlock({ squeeze }: Props) {
  const catalyst = squeeze.catalyst_strength;
  const attention = squeeze.attention_feature;
  const thesis = squeeze.thesis_invalidation;
  const lending = squeeze.securities_lending_snapshot;
  const informationValue = squeeze.information_value;
  const reflexiveImpact = squeeze.reflexive_impact;

  if (!catalyst && !attention && !thesis && !lending) {
    return (
      <section className="squeeze-catalyst-block unavailable">
        <h3>Catalyst &amp; attention</h3>
        <p className="squeeze-catalyst-note">UNAVAILABLE — no PIT-eligible market-context signals at cutoff.</p>
      </section>
    );
  }

  return (
    <section className="squeeze-catalyst-block">
      <h3>Catalyst &amp; attention</h3>
      <dl className="squeeze-catalyst-grid">
        <div>
          <dt>Catalyst strength</dt>
          <dd>
            {catalyst?.strength != null
              ? `${catalyst.strength} (${catalyst.catalyst_type})`
              : "UNAVAILABLE"}
          </dd>
        </div>
        <div>
          <dt>Attention level</dt>
          <dd>{attention?.attention_score != null ? attention.attention_score : "UNAVAILABLE"}</dd>
        </div>
        <div>
          <dt>Attention acceleration</dt>
          <dd>
            {attention?.attention_acceleration != null
              ? attention.attention_acceleration
              : "UNAVAILABLE"}
          </dd>
        </div>
        <div>
          <dt>Information value</dt>
          <dd>{informationValue != null ? informationValue : "UNAVAILABLE"}</dd>
        </div>
        <div>
          <dt>Reflexive impact</dt>
          <dd>{reflexiveImpact != null ? reflexiveImpact : "UNAVAILABLE"}</dd>
        </div>
        <div>
          <dt>Short thesis invalidation</dt>
          <dd>
            {thesis?.invalidation_score != null ? thesis.invalidation_score : "UNAVAILABLE"}
          </dd>
        </div>
        <div>
          <dt>Securities lending</dt>
          <dd>
            {lending
              ? [
                  lending.fee_rate != null ? `fee ${lending.fee_rate}%` : null,
                  lending.shares_available != null
                    ? `shortable ${lending.shares_available}`
                    : null,
                  lending.utilization_rate == null ? "utilization UNAVAILABLE" : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "IBKR snapshot"
              : "UNAVAILABLE"}
          </dd>
        </div>
      </dl>
    </section>
  );
}

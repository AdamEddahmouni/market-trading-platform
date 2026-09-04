import { Link } from "react-router-dom";
import {
  ExploreObservability,
  type ExploreObservabilityProps,
} from "../explore-shared/ExploreObservability";

type Props = ExploreObservabilityProps;

export function LiveExplorePage({ onExplain }: Props) {
  return (
    <section className="page explore-page live-explore-page">
      <header className="live-explore-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>Explore</h1>
          <p>
            Monitor live provider scanner output alongside frozen research cohorts. All surfaces are
            read-only — use the live canary for operational safety review.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Bridge tables do not place orders. Execution controls remain on the live canary control plane.</p>
      </aside>

      <ExploreObservability onExplain={onExplain} showLivePanel />
    </section>
  );
}

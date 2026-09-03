import { Link } from "react-router-dom";
import {
  ExploreObservability,
  type ExploreObservabilityProps,
} from "../explore-shared/ExploreObservability";

type Props = ExploreObservabilityProps;

export function PaperExplorePage({ onExplain }: Props) {
  return (
    <section className="page explore-page paper-explore-page">
      <header className="paper-explore-header">
        <div>
          <span className="paper-eyebrow">Paper · Candidate discovery</span>
          <h1>Explore</h1>
          <p>
            Screen donor bridges for squeeze, catalyst, and futures context. Open workspace lanes to
            preview paper orders when Paper authority is available.
          </p>
        </div>
        <Link className="paper-explore-portfolio-link" to="/portfolio">
          Open paper portfolio
        </Link>
      </header>

      <ExploreObservability onExplain={onExplain} />
    </section>
  );
}

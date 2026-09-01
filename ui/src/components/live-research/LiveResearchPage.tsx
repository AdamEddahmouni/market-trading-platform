import { Link } from "react-router-dom";
import { ResearchObservability } from "../research-shared/ResearchObservability";

export function LiveResearchPage() {
  return (
    <section className="page research-page live-research-page">
      <header className="live-research-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>Research</h1>
          <p>
            Research projections remain replay-bound even in Live mode. No trade authority — monitor
            outputs alongside live canary safety signals.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Research artifacts do not mutate broker state. Operational controls stay on the live canary.</p>
      </aside>

      <ResearchObservability />
    </section>
  );
}

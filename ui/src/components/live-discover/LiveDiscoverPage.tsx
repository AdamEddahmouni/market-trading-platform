import { Link } from "react-router-dom";
import { DiscoverObservability } from "../discover-shared/DiscoverObservability";

export function LiveDiscoverPage() {
  return (
    <section className="page discover-page live-discover-page">
      <header className="live-discover-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>Discover</h1>
          <p>
            Monitor the mixed live screener without discovery mutations or workspace promotion. Use the live
            canary for operational safety review.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Refresh and promote controls are hidden. Workspace links navigate without changing live analysis subscriptions.</p>
      </aside>

      <DiscoverObservability />
    </section>
  );
}

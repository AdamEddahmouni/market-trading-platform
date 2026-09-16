import type { ReactNode } from "react";

type SectionProps = {
  children: ReactNode;
};

export function DiscoverRankedQueueSection({ children }: SectionProps) {
  return (
    <section
      className="imp-discover-section imp-discover-ranked imp-discover-contract-queue"
      aria-labelledby="imp-discover-ranked-title"
    >
      <header className="imp-discover-section-header">
        <div className="imp-discover-section-badges" aria-hidden="true">
          <span className="imp-discover-badge imp-discover-badge-contract">Opportunity contract</span>
        </div>
        <p className="imp-section-eyebrow">Opportunity contract</p>
        <h2 id="imp-discover-ranked-title">Ranked opportunity queue</h2>
        <p className="imp-discover-section-lead">
          Summaries from admitted screeners. Explain and inspect without leaving the radar.
        </p>
      </header>
      {children}
    </section>
  );
}

export function DiscoverMixedScreenerSection({ children }: SectionProps) {
  return (
    <section
      className="imp-discover-section imp-discover-screener imp-discover-investigation-only"
      aria-labelledby="imp-discover-screener-title"
      aria-describedby="imp-discover-screener-boundary"
    >
      <header className="imp-discover-section-header">
        <div className="imp-discover-section-badges" aria-hidden="true">
          <span className="imp-discover-badge imp-discover-badge-investigate">Investigation only</span>
          <span className="imp-discover-badge imp-discover-badge-not-contract">Not opportunity contract</span>
        </div>
        <p className="imp-section-eyebrow">Semi-live screener</p>
        <h2 id="imp-discover-screener-title">Mixed discovery desk</h2>
        <p id="imp-discover-screener-boundary" className="imp-discover-section-lead">
          Finviz and market captures for operator research. Candidates are INVESTIGATE only — not ranked
          opportunity summaries and not trade signals.
        </p>
      </header>
      {children}
    </section>
  );
}

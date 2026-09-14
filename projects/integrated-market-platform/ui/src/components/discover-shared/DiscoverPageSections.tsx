import type { ReactNode } from "react";

type SectionProps = {
  children: ReactNode;
};

export function DiscoverRankedQueueSection({ children }: SectionProps) {
  return (
    <section className="imp-discover-section imp-discover-ranked" aria-labelledby="imp-discover-ranked-title">
      <header className="imp-discover-section-header">
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
    <section className="imp-discover-section imp-discover-screener" aria-labelledby="imp-discover-screener-title">
      <header className="imp-discover-section-header">
        <p className="imp-section-eyebrow">Semi-live screener</p>
        <h2 id="imp-discover-screener-title">Mixed discovery desk</h2>
        <p className="imp-discover-section-lead">
          Finviz and market captures ranked for investigation. Candidates are INVESTIGATE only — not trade signals.
        </p>
      </header>
      {children}
    </section>
  );
}

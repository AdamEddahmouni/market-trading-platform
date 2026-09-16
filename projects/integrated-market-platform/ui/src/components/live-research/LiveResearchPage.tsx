import { Link } from "react-router-dom";
import { PageHeader } from "../shared/PageHeader";
import { ResearchSurface } from "../research-shared/ResearchSurface";
import type { ResearchSectionKey } from "../research-shared/researchPresentation";

type Props = {
  section: ResearchSectionKey;
};

export function LiveResearchPage({ section }: Props) {
  return (
    <section className="page research-page live-research-page">
      <PageHeader
        eyebrow="Live · Read-only observational"
        title="Research"
        subtitle="Research projections remain replay-bound even in Live mode. No trade authority — monitor outputs alongside live canary safety signals."
        actions={<Link to="/live-canary">Open live canary</Link>}
      />

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Research artifacts do not mutate broker state. Operational controls stay on the live canary.</p>
      </aside>

      <ResearchSurface mode="LIVE" section={section} />
    </section>
  );
}

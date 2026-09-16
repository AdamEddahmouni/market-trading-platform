import { PageHeader } from "../shared/PageHeader";
import { ResearchSurface } from "../research-shared/ResearchSurface";
import type { ResearchSectionKey } from "../research-shared/researchPresentation";

type Props = {
  section: ResearchSectionKey;
};

export function DemoResearchPage({ section }: Props) {
  return (
    <section className="page research-page demo-research-page">
      <PageHeader
        eyebrow="Demo · Historical research"
        title="Research"
        subtitle="What the replayed evidence shows, how it was produced, and how much to trust it. Research never grants trade authority."
        meta={<span className="demo-state-badge">Read-only research</span>}
      />

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Research surfaces never grant execution authority. Switch to Paper mode to connect findings to simulation.</p>
      </aside>

      <ResearchSurface mode="DEMO" section={section} />
    </section>
  );
}

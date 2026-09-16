import { PageHeader } from "../shared/PageHeader";
import { ResearchSurface } from "../research-shared/ResearchSurface";
import type { ResearchSectionKey } from "../research-shared/researchPresentation";

type Props = {
  section: ResearchSectionKey;
};

export function PaperResearchPage({ section }: Props) {
  return (
    <section className="page research-page paper-research-page">
      <PageHeader
        eyebrow="Paper · Research to simulation"
        title="Research"
        subtitle="What the evidence shows, how the strategy research is validated, and how the deterministic simulation behaved. Research informs paper review — it never places orders."
      />

      <ResearchSurface mode="PAPER" section={section} />
    </section>
  );
}

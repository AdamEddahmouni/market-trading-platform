import { LinkTabs } from "../imp-ui/LinkTabs";
import type { Mode } from "../mode-session/types";
import { ResearchOverviewSection } from "./ResearchOverviewSection";
import { ResearchEvidenceSection } from "./ResearchEvidenceSection";
import { ResearchValidationSection } from "./ResearchValidationSection";
import { ResearchSimulationSection } from "./ResearchSimulationSection";
import { RESEARCH_SECTION_TABS, type ResearchSectionKey } from "./researchPresentation";

type Props = {
  mode: Mode;
  section: ResearchSectionKey;
};

/**
 * Shared Research surface: routable section tabs plus the active section.
 * Each section fetches only its own endpoint(s); the Overview legitimately
 * reads all three research payloads to synthesize the current picture.
 */
export function ResearchSurface({ mode, section }: Props) {
  return (
    <>
      <LinkTabs label="Research sections" items={[...RESEARCH_SECTION_TABS]} />
      {section === "overview" ? <ResearchOverviewSection mode={mode} /> : null}
      {section === "evidence" ? <ResearchEvidenceSection /> : null}
      {section === "validation" ? <ResearchValidationSection mode={mode} /> : null}
      {section === "simulation" ? <ResearchSimulationSection /> : null}
    </>
  );
}

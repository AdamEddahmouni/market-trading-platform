import { PageHeader } from "../shared/PageHeader";
import { LabSurface } from "../lab-shared/LabSurface";
import type { LabSectionKey } from "../lab-shared/labPresentation";
import "../../styles/lab.css";

type Props = {
  section: LabSectionKey;
};

export function PaperLabPage({ section }: Props) {
  return (
    <section className="page lab-page paper-lab-page">
      <PageHeader
        eyebrow="Paper · Experimental workbench"
        title="Lab"
        subtitle="Inspect validation and simulation snapshots that inform Paper review. Order submit stays in Workspace — Lab does not gain mutations because Paper mode is on."
      />
      <aside className="panel mode-restriction-note" role="note">
        <strong>Paper execution stays in Workspace.</strong>
        <p>
          Lab remains an inspectable research/testing workbench. Paper mode does not unlock
          experiment-run mutations; none exist on the current UI API.
        </p>
      </aside>
      <LabSurface section={section} />
    </section>
  );
}

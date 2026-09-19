import { PageHeader } from "../shared/PageHeader";
import { LabSurface } from "../lab-shared/LabSurface";
import type { LabSectionKey } from "../lab-shared/labPresentation";
import "../../styles/lab.css";

type Props = {
  section: LabSectionKey;
};

export function DemoLabPage({ section }: Props) {
  return (
    <section className="page lab-page demo-lab-page">
      <PageHeader
        eyebrow="Demo · Experimental workbench"
        title="Lab"
        subtitle="Inspect how validation and simulation workflows are set up and what the current snapshot contains. Lab never grants trade authority."
        meta={<span className="demo-state-badge">Read-only workbench</span>}
      />
      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>
          Lab workflows are inspectable here. Demo mode does not start experiments, and nothing on
          this page is an execution authorization.
        </p>
      </aside>
      <LabSurface section={section} />
    </section>
  );
}

import { PageHeader } from "../shared/PageHeader";
import { LabSurface } from "../lab-shared/LabSurface";
import type { LabSectionKey } from "../lab-shared/labPresentation";
import "../../styles/lab.css";

type Props = {
  section: LabSectionKey;
};

export function LiveLabPage({ section }: Props) {
  return (
    <section className="page lab-page live-lab-page">
      <PageHeader
        eyebrow="Live · Observational workbench"
        title="Lab"
        subtitle="Live data mode does not imply Live experiment authority. Lab still inspects replay-bound validation and simulation projections."
      />
      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is observational here.</strong>
        <p>
          Lab does not start Live experiments and does not mutate broker state. Operational
          controls stay on Control and the live canary.
        </p>
      </aside>
      <LabSurface section={section} />
    </section>
  );
}

import { lazy, Suspense } from "react";
import { LinkTabs } from "../imp-ui/LinkTabs";
import { LabOverviewSection } from "./LabOverviewSection";
import { LabValidationSection } from "./LabValidationSection";
import { LabSimulationSection } from "./LabSimulationSection";
import { LAB_SECTION_TABS, type LabSectionKey } from "./labPresentation";

const ImpVelaChartLabPage = lazy(() =>
  import("../charts/ImpVelaChartLabPage").then((module) => ({
    default: module.ImpVelaChartLabPage,
  })),
);

type Props = {
  section: LabSectionKey;
};

function ChartLabSection() {
  return (
    <>
      <section className="lab-panel" aria-labelledby="lab-chart-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Local tooling</div>
            <h2 id="lab-chart-heading">Chart adapter playground</h2>
          </div>
        </div>
        <p className="lab-muted">
          Tick-sim and backfill change local state only. This playground is not a research finding,
          not validation evidence, not a simulation run, and not FTEP.
        </p>
      </section>
      <Suspense fallback={<p role="status">Loading chart lab…</p>}>
        <ImpVelaChartLabPage />
      </Suspense>
    </>
  );
}

export function LabSurface({ section }: Props) {
  return (
    <>
      <LinkTabs label="Lab sections" items={[...LAB_SECTION_TABS]} />
      {section === "overview" ? <LabOverviewSection /> : null}
      {section === "validation" ? <LabValidationSection /> : null}
      {section === "simulation" ? <LabSimulationSection /> : null}
      {section === "chart-lab" ? <ChartLabSection /> : null}
    </>
  );
}

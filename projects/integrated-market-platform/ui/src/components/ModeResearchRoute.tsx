import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import type { Mode } from "./mode-session/types";
import type { ResearchSectionKey } from "./research-shared/researchPresentation";

const DemoResearchPage = lazy(() =>
  import("./demo-research/DemoResearchPage").then((module) => ({
    default: module.DemoResearchPage,
  })),
);
const PaperResearchPage = lazy(() =>
  import("./paper-research/PaperResearchPage").then((module) => ({
    default: module.PaperResearchPage,
  })),
);
const LiveResearchPage = lazy(() =>
  import("./live-research/LiveResearchPage").then((module) => ({
    default: module.LiveResearchPage,
  })),
);
const ImpVelaChartLabPage = lazy(() =>
  import("./charts/ImpVelaChartLabPage").then((module) => ({
    default: module.ImpVelaChartLabPage,
  })),
);

type Props = {
  mode: Mode;
};

function ModeResearchHome({ mode, section }: Props & { section: ResearchSectionKey }) {
  if (mode === "DEMO") return <DemoResearchPage section={section} />;
  if (mode === "PAPER") return <PaperResearchPage section={section} />;
  return <LiveResearchPage section={section} />;
}

/**
 * Research sections are real routes (deep-linkable, one fetch per section):
 * Overview (default), Evidence, Validation, Simulation. The Vela chart lab
 * keeps its existing route. `/lab` continues to redirect to `/research` —
 * the Lab workbench is a separate future increment (see
 * docs/ui-redesign-v2/research-contract-map.md).
 */
export function ModeResearchRoute({ mode }: Props) {
  return (
    <Suspense fallback={<p role="status">Loading research…</p>}>
      <Routes>
        <Route path="vela-chart-lab" element={<ImpVelaChartLabPage />} />
        <Route path="evidence" element={<ModeResearchHome mode={mode} section="evidence" />} />
        <Route path="validation" element={<ModeResearchHome mode={mode} section="validation" />} />
        <Route path="simulation" element={<ModeResearchHome mode={mode} section="simulation" />} />
        <Route path="*" element={<ModeResearchHome mode={mode} section="overview" />} />
      </Routes>
    </Suspense>
  );
}

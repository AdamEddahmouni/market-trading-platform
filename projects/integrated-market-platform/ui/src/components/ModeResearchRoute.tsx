import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import type { Mode } from "./mode-session/types";

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

function ModeResearchHome({ mode }: Props) {
  if (mode === "DEMO") return <DemoResearchPage />;
  if (mode === "PAPER") return <PaperResearchPage />;
  return <LiveResearchPage />;
}

export function ModeResearchRoute({ mode }: Props) {
  return (
    <Suspense fallback={<p role="status">Loading research…</p>}>
      <Routes>
        <Route path="vela-chart-lab" element={<ImpVelaChartLabPage />} />
        <Route path="*" element={<ModeResearchHome mode={mode} />} />
      </Routes>
    </Suspense>
  );
}

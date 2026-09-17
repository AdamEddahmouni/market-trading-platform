import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import type { Mode } from "./mode-session/types";
import type { LabSectionKey } from "./lab-shared/labPresentation";

const DemoLabPage = lazy(() =>
  import("./demo-lab/DemoLabPage").then((module) => ({
    default: module.DemoLabPage,
  })),
);
const PaperLabPage = lazy(() =>
  import("./paper-lab/PaperLabPage").then((module) => ({
    default: module.PaperLabPage,
  })),
);
const LiveLabPage = lazy(() =>
  import("./live-lab/LiveLabPage").then((module) => ({
    default: module.LiveLabPage,
  })),
);

type Props = {
  mode: Mode;
};

function ModeLabHome({ mode, section }: Props & { section: LabSectionKey }) {
  if (mode === "DEMO") return <DemoLabPage section={section} />;
  if (mode === "PAPER") return <PaperLabPage section={section} />;
  return <LiveLabPage section={section} />;
}

/**
 * Lab workbench routes. Endpoints stay `/research/models` and
 * `/research/simulation`; this surface is process, not interpretation.
 */
export function ModeLabRoute({ mode }: Props) {
  return (
    <Suspense fallback={<p role="status">Loading lab…</p>}>
      <Routes>
        <Route path="validation" element={<ModeLabHome mode={mode} section="validation" />} />
        <Route path="simulation" element={<ModeLabHome mode={mode} section="simulation" />} />
        <Route path="chart-lab" element={<ModeLabHome mode={mode} section="chart-lab" />} />
        <Route path="*" element={<ModeLabHome mode={mode} section="overview" />} />
      </Routes>
    </Suspense>
  );
}

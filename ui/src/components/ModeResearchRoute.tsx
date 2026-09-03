import { lazy } from "react";
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

type Props = {
  mode: Mode;
};

export function ModeResearchRoute({ mode }: Props) {
  if (mode === "DEMO") return <DemoResearchPage />;
  if (mode === "PAPER") return <PaperResearchPage />;
  return <LiveResearchPage />;
}

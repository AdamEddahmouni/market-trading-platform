import { lazy } from "react";
import type { Mode } from "./mode-session/types";
import type { ExploreObservabilityProps } from "./explore-shared/ExploreObservability";

const DemoExplorePage = lazy(() =>
  import("./demo-explore/DemoExplorePage").then((module) => ({
    default: module.DemoExplorePage,
  })),
);
const PaperExplorePage = lazy(() =>
  import("./paper-explore/PaperExplorePage").then((module) => ({
    default: module.PaperExplorePage,
  })),
);
const LiveExplorePage = lazy(() =>
  import("./live-explore/LiveExplorePage").then((module) => ({
    default: module.LiveExplorePage,
  })),
);

type Props = ExploreObservabilityProps & {
  mode: Mode;
};

export function ModeExploreRoute({ mode, onExplain }: Props) {
  if (mode === "DEMO") return <DemoExplorePage onExplain={onExplain} />;
  if (mode === "PAPER") return <PaperExplorePage onExplain={onExplain} />;
  return <LiveExplorePage onExplain={onExplain} />;
}

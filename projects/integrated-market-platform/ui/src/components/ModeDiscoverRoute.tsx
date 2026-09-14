import { lazy } from "react";
import type { DiscoverInspectorActions } from "./discover-shared/discoverInspectorActions";
import type { Mode } from "./mode-session/types";

const DemoDiscoverPage = lazy(() =>
  import("./demo-discover/DemoDiscoverPage").then((module) => ({
    default: module.DemoDiscoverPage,
  })),
);
const PaperDiscoverPage = lazy(() =>
  import("./paper-discover/PaperDiscoverPage").then((module) => ({
    default: module.PaperDiscoverPage,
  })),
);
const LiveDiscoverPage = lazy(() =>
  import("./live-discover/LiveDiscoverPage").then((module) => ({
    default: module.LiveDiscoverPage,
  })),
);

type Props = DiscoverInspectorActions & {
  mode: Mode;
};

export function ModeDiscoverRoute({ mode, ...actions }: Props) {
  if (mode === "DEMO") return <DemoDiscoverPage {...actions} />;
  if (mode === "PAPER") return <PaperDiscoverPage {...actions} />;
  return <LiveDiscoverPage {...actions} />;
}

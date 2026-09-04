import { lazy } from "react";
import type { PaperOrderDraft } from "./paper-now/paperOrderDraft";
import type { Mode } from "./mode-session/types";
import type { WorkspaceObservabilityProps } from "./workspace-shared/WorkspaceObservability";

const DemoWorkspacePage = lazy(() =>
  import("./demo-workspace/DemoWorkspacePage").then((module) => ({
    default: module.DemoWorkspacePage,
  })),
);
const PaperWorkspacePage = lazy(() =>
  import("./paper-workspace/PaperWorkspacePage").then((module) => ({
    default: module.PaperWorkspacePage,
  })),
);
const LiveWorkspacePage = lazy(() =>
  import("./live-workspace/LiveWorkspacePage").then((module) => ({
    default: module.LiveWorkspacePage,
  })),
);

type Props = WorkspaceObservabilityProps & {
  mode: Mode;
  paperActionsPermitted: boolean;
  initialPaperOrderDraft?: PaperOrderDraft;
};

export function ModeWorkspacePage({
  mode,
  paperActionsPermitted,
  initialPaperOrderDraft,
  ...observabilityProps
}: Props) {
  if (mode === "DEMO") return <DemoWorkspacePage {...observabilityProps} />;
  if (mode === "PAPER") {
    return (
      <PaperWorkspacePage
        {...observabilityProps}
        paperActionsPermitted={paperActionsPermitted}
        initialPaperOrderDraft={initialPaperOrderDraft}
      />
    );
  }
  return <LiveWorkspacePage {...observabilityProps} />;
}

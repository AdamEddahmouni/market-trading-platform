import { lazy } from "react";
import { useLiveCanaryReconciliationQuery, useLiveCanarySnapshotQuery } from "../api/hooks";

const DemoPortfolioPage = lazy(() =>
  import("./demo-portfolio/DemoPortfolioPage").then((module) => ({
    default: module.DemoPortfolioPage,
  })),
);
const PaperPortfolioPage = lazy(() =>
  import("./paper-portfolio/PaperPortfolioPage").then((module) => ({
    default: module.PaperPortfolioPage,
  })),
);
const LivePortfolioPage = lazy(() =>
  import("./live-portfolio/LivePortfolioPage").then((module) => ({
    default: module.LivePortfolioPage,
  })),
);

type Props = {
  mode: import("./mode-session/types").Mode;
  paperActionsPermitted: boolean;
};

function LivePortfolioRoute() {
  const snapshotQuery = useLiveCanarySnapshotQuery("portfolio");
  const reconciliationQuery = useLiveCanaryReconciliationQuery();

  const state = snapshotQuery.isLoading
    ? "loading"
    : snapshotQuery.isError
      ? "error"
      : "ready";

  return (
    <LivePortfolioPage
      snapshot={snapshotQuery.data}
      reconciliation={reconciliationQuery.data}
      state={state}
    />
  );
}

export function ModePortfolioRoute({ mode, paperActionsPermitted }: Props) {
  if (mode === "DEMO") return <DemoPortfolioPage />;
  if (mode === "PAPER") return <PaperPortfolioPage paperActionsPermitted={paperActionsPermitted} />;
  return <LivePortfolioRoute />;
}

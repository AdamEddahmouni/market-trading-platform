import { useQuery } from "@tanstack/react-query";
import { lazy } from "react";
import { useLiveCanarySnapshotQuery } from "../api/hooks";

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

type ReconciliationPayload = {
  reconciliation_health: string;
  local_open_orders: string[];
  ambiguous_states: string[];
};

async function fetchLiveReconciliation(): Promise<ReconciliationPayload> {
  const response = await fetch("/canary/reconciliation");
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<ReconciliationPayload>;
}

type Props = {
  mode: import("./mode-session/types").Mode;
  paperActionsPermitted: boolean;
};

function LivePortfolioRoute() {
  const snapshotQuery = useLiveCanarySnapshotQuery("portfolio");
  const reconciliationQuery = useQuery({
    queryKey: ["canary-reconciliation"],
    queryFn: fetchLiveReconciliation,
    refetchInterval: 15000,
  });

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

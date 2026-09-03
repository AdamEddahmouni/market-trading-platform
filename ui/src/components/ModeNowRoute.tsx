import { lazy } from "react";
import { useContextQuery, useLiveCanarySnapshotQuery, usePaperPortfolioQuery, useProviderHealthQuery } from "../api/hooks";
import { DemoNowPage, type DemoNowPageProps } from "./demo-now/DemoNowPage";

const PaperNowPage = lazy(() =>
  import("./paper-now/PaperNowPage").then((module) => ({ default: module.PaperNowPage })),
);
const LiveNowPage = lazy(() =>
  import("./live-now/LiveNowPage").then((module) => ({ default: module.LiveNowPage })),
);

type SharedProps = Omit<DemoNowPageProps, "portfolio" | "portfolioState">;

type Props = SharedProps & {
  mode: import("./mode-session/types").Mode;
  paperActionsPermitted: boolean;
  tierSummary?: import("../lib/chartTransforms").ChartCountPoint[];
};

function DemoNowRoute(props: SharedProps) {
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolioState = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError || !portfolioQuery.data
      ? "error"
      : "ready";
  return <DemoNowPage {...props} portfolio={portfolioQuery.data} portfolioState={portfolioState} />;
}

function PaperNowRoute({ paperActionsPermitted, ...props }: SharedProps & { paperActionsPermitted: boolean }) {
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolioState = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError || !portfolioQuery.data
      ? "error"
      : "ready";
  return (
    <PaperNowPage
      items={props.items}
      attentionState={props.attentionState}
      portfolio={portfolioQuery.data}
      portfolioState={portfolioState}
      paperActionsPermitted={paperActionsPermitted}
      onWhy={props.onWhy}
      onExplain={props.onExplain}
      onInspect={props.onInspect}
    />
  );
}

function LiveNowRoute(props: SharedProps) {
  const contextQuery = useContextQuery();
  const providerQuery = useProviderHealthQuery();
  const canaryQuery = useLiveCanarySnapshotQuery("now");

  const providerState = providerQuery.isLoading
    ? "loading"
    : providerQuery.isError
      ? "error"
      : "ready";
  const safetyState = canaryQuery.isLoading ? "loading" : canaryQuery.isError ? "error" : "ready";
  const context = contextQuery.data?.as_of_context;

  return (
    <LiveNowPage
      items={props.items}
      attentionState={props.attentionState}
      dataMode={context?.data_mode}
      executionAuthority={context?.execution_authority}
      providerHealth={providerQuery.data}
      providerState={providerState}
      canarySnapshot={canaryQuery.data}
      safetyState={safetyState}
      onWhy={props.onWhy}
      onExplain={props.onExplain}
      onInspect={props.onInspect}
      onOpenWorkspace={props.onOpenWorkspace}
    />
  );
}

export function ModeNowRoute({ mode, tierSummary: _tierSummary, paperActionsPermitted, ...props }: Props) {
  if (mode === "DEMO") return <DemoNowRoute {...props} />;
  if (mode === "PAPER") return <PaperNowRoute {...props} paperActionsPermitted={paperActionsPermitted} />;
  return <LiveNowRoute {...props} />;
}

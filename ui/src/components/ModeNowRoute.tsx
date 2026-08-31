import { lazy } from "react";
import { useNavigate } from "react-router-dom";
import { usePaperPortfolioQuery } from "../api/hooks";
import type { ChartCountPoint } from "../lib/chartTransforms";
import type { Mode } from "./mode-session/types";
import { NowPage } from "./NowPage";
import { DemoNowPage, type DemoNowPageProps } from "./demo-now/DemoNowPage";

const PaperNowPage = lazy(() =>
  import("./paper-now/PaperNowPage").then((module) => ({ default: module.PaperNowPage })),
);

type SharedProps = Omit<DemoNowPageProps, "portfolio" | "portfolioState">;

type Props = SharedProps & {
  mode: Mode;
  paperActionsPermitted: boolean;
  tierSummary?: ChartCountPoint[];
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
  const navigate = useNavigate();
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
      onOpenWorkspace={props.onOpenWorkspace}
      onContinue={(draft) => navigate(`/workspace/${draft.instrumentId}`, { state: draft })}
    />
  );
}

export function ModeNowRoute({ mode, tierSummary, paperActionsPermitted, ...props }: Props) {
  if (mode === "DEMO") return <DemoNowRoute {...props} />;
  if (mode === "PAPER") return <PaperNowRoute {...props} paperActionsPermitted={paperActionsPermitted} />;
  return (
    <NowPage
      items={props.items}
      tierSummary={tierSummary}
      onWhy={props.onWhy}
      onExplain={props.onExplain}
      onInspect={props.onInspect}
      onOpenWorkspace={props.onOpenWorkspace}
    />
  );
}

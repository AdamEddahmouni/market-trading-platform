import { usePaperPortfolioQuery } from "../api/hooks";
import type { ChartCountPoint } from "../lib/chartTransforms";
import type { Mode } from "./mode-session/types";
import { NowPage } from "./NowPage";
import { DemoNowPage, type DemoNowPageProps } from "./demo-now/DemoNowPage";

type Props = Omit<DemoNowPageProps, "portfolio" | "portfolioState"> & {
  mode: Mode;
  tierSummary?: ChartCountPoint[];
};

function DemoNowRoute(props: Omit<Props, "mode" | "tierSummary">) {
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolioState = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError || !portfolioQuery.data
      ? "error"
      : "ready";
  return <DemoNowPage {...props} portfolio={portfolioQuery.data} portfolioState={portfolioState} />;
}

export function ModeNowRoute({ mode, tierSummary, ...props }: Props) {
  if (mode === "DEMO") return <DemoNowRoute {...props} />;
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

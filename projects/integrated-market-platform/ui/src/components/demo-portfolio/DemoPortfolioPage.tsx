import { Link } from "react-router-dom";
import { usePaperPortfolioQuery } from "../../api/hooks";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { PaperPortfolioObservability } from "../portfolio-shared/PaperPortfolioObservability";
import { LoadingState } from "../shared/LoadingState";
import { PageHeader } from "../shared/PageHeader";

export function DemoPortfolioPage() {
  const portfolioQuery = usePaperPortfolioQuery("DEMO");

  if (portfolioQuery.isLoading) {
    return (
      <section className="page portfolio-page demo-portfolio-page">
        <PageHeader
          eyebrow="Demo · exploration only"
          title="Demo Portfolio"
          subtitle="Simulated replay account — not live capital."
        />
        <LoadingState label="Loading simulated portfolio…" />
      </section>
    );
  }

  if (portfolioQuery.isError || !portfolioQuery.data) {
    return (
      <section className="page portfolio-page demo-portfolio-page">
        <PageHeader
          eyebrow="Demo · exploration only"
          title="Demo Portfolio"
          subtitle="Simulated replay account — not live capital."
        />
        <ErrorState
          title="Simulated portfolio is unavailable."
          affects="Demo positions and P&L cannot be shown."
          onRetry={() => void portfolioQuery.refetch()}
        />
      </section>
    );
  }

  return (
    <section className="page portfolio-page demo-portfolio-page">
      <PageHeader
        eyebrow="Demo · exploration only"
        title="Demo Portfolio"
        subtitle="Simulated account, positions, and fills for learning and replay context. Order and session controls are unavailable in Demo."
        actions={
          <Link className="portfolio-row-action" to="/workspace">
            Open Workspace
          </Link>
        }
        restriction={
          <aside className="panel mode-restriction-note" role="note">
            <strong>Demo is exploration only.</strong>
            <p>Order and session controls are unavailable. Switch to Paper mode to manage simulation sessions.</p>
          </aside>
        }
      />

      <PaperPortfolioObservability data={portfolioQuery.data} viewMode="DEMO" />
    </section>
  );
}

import { Link, useSearchParams } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import { usePaperPortfolioQuery } from "../../api/hooks";
import { PageHeader } from "../shared/PageHeader";
import { LinkTabs } from "../imp-ui/LinkTabs";
import { DiscoverObservability } from "../discover-shared/DiscoverObservability";
import { ExploreObservability } from "../explore-shared/ExploreObservability";
import type { Mode } from "../mode-session/types";
import { RadarOpportunitiesPanel } from "./RadarOpportunitiesPanel";

export type RadarTab = "opportunities" | "screeners";

export type RadarPageProps = {
  mode: Mode;
  tab: RadarTab;
  /** From `canUsePaperActions` at the shell — authority-gated, not mode-only. */
  paperActionsPermitted?: boolean;
  onExplain: (item: AttentionItem) => void;
  /** Ref-string explain channel used by the screener bridges. */
  onExplainRef: (ref: string) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

const RADAR_TABS = [
  { to: "/radar", label: "Opportunities", end: true },
  { to: "/radar/screeners", label: "Screeners" },
];

const MODE_COPY: Record<
  Mode,
  { eyebrow: string; subtitle: string; restriction?: { title: string; body: string } }
> = {
  DEMO: {
    eyebrow: "Demo replay",
    subtitle:
      "Inspect the ranked opportunity queue and discovery screeners on recorded data. Everything here is read-only.",
    restriction: {
      title: "Demo is exploration only.",
      body: "Discovery refresh and promote actions are unavailable. Switch to Paper mode to run the full discovery desk.",
    },
  },
  PAPER: {
    eyebrow: "Paper trading",
    subtitle:
      "Ranked opportunities, the mixed live screener, and donor research screens. Promote candidates into workspace lanes for paper simulation review.",
  },
  LIVE: {
    eyebrow: "Live observation",
    subtitle:
      "Read-only monitor over discovery surfaces. Live mode has no opportunity engine and no execution authority.",
    restriction: {
      title: "Live is read-only here.",
      body: "Refresh and promote controls are hidden. Workspace links navigate without changing live analysis subscriptions.",
    },
  },
};

/**
 * Radar — the canonical discovery queue (find → rank → investigate).
 * Opportunities tab: ranked OE queue + selected opportunity detail.
 * Screeners tab: mixed live screener + donor research bridges.
 * Mode honesty: Demo read-only, Paper full discovery mutations, Live
 * read-only monitor. No surface implies real-money action.
 */
export function RadarPage({
  mode,
  tab,
  paperActionsPermitted = false,
  onExplain,
  onExplainRef,
  onInspect,
  onOpenWorkspace,
}: RadarPageProps) {
  const copy = MODE_COPY[mode];
  const paper = mode === "PAPER";
  const live = mode === "LIVE";
  const paperActions = paper && paperActionsPermitted;
  const portfolioQuery = usePaperPortfolioQuery("PAPER", paperActions);
  const paperAccountId = paperActions
    ? portfolioQuery.data?.account.paper_account_id
    : undefined;
  const [searchParams] = useSearchParams();
  const filterQuery = tab === "screeners" ? (searchParams.get("q") ?? undefined) : undefined;

  return (
    <section className="page imp-radar-page" data-mode={mode}>
      <PageHeader
        eyebrow={copy.eyebrow}
        title="Radar"
        subtitle={copy.subtitle}
        actions={
          tab === "screeners" && paper ? (
            <Link to="/portfolio">Open paper portfolio</Link>
          ) : tab === "screeners" && live ? (
            <Link to="/live-canary">Open live canary</Link>
          ) : undefined
        }
      />

      {copy.restriction ? (
        <aside className="panel mode-restriction-note" role="note">
          <strong>{copy.restriction.title}</strong>
          <p>{copy.restriction.body}</p>
        </aside>
      ) : null}

      <LinkTabs label="Radar sections" items={RADAR_TABS} />

      {tab === "opportunities" ? (
        <RadarOpportunitiesPanel
          readOnly={!paper}
          paperAccountId={paperAccountId}
          paperActions={paperActions}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      ) : (
        <div className="imp-radar-screeners" data-testid="imp-radar-screeners">
          <section
            className="imp-radar-screener-section imp-radar-investigation-only"
            aria-label="Mixed live screener"
          >
            <p className="imp-radar-section-lead">
              Finviz finds the setup; connected market data confirms what is happening now.
              Candidates are investigation-only — not trade signals.
            </p>
            {paper ? (
              <DiscoverObservability allowMutations autoRefreshOnMount />
            ) : (
              <DiscoverObservability />
            )}
          </section>
          <section
            className="imp-radar-screener-section"
            aria-label="Research screens"
          >
            <header className="imp-radar-section-header">
              <h2>Research screens</h2>
              <p className="imp-radar-section-lead">
                Donor screener bridges with provenance — squeeze cohort, scanner, futures, and
                catalyst screens.
              </p>
            </header>
            <ExploreObservability
              onExplain={onExplainRef}
              showLivePanel={live}
              filterQuery={filterQuery}
            />
          </section>
        </div>
      )}
    </section>
  );
}

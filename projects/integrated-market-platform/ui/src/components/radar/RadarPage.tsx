import { Link, useSearchParams } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import { useContextQuery, usePaperPortfolioQuery } from "../../api/hooks";
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

const CONTROLLED_REPLAY_ACCOUNT_ID = "controlled-replay-operator";

const MODE_COPY: Record<
  Mode,
  { eyebrow: string; subtitle: string; restriction?: { title: string; body: string } }
> = {
  DEMO: {
    eyebrow: "Demo replay",
    subtitle:
      "Inspect the ranked opportunity queue and investigation screeners on recorded data. Everything here is read-only.",
    restriction: {
      title: "Demo is exploration only.",
      body: "Investigation refresh and promote actions are unavailable. Switch to Paper mode to run the full investigation desk.",
    },
  },
  PAPER: {
    eyebrow: "Paper trading",
    subtitle:
      "Ranked opportunities, the investigation screener, and donor research screens. Promote candidates into workspace lanes for paper simulation review.",
  },
  LIVE: {
    eyebrow: "Live observation",
    subtitle:
      "Read-only monitor over investigation surfaces. Live mode has no opportunity engine and no execution authority.",
    restriction: {
      title: "Live is read-only here.",
      body: "Refresh and promote controls are hidden. Workspace links navigate without changing live analysis subscriptions.",
    },
  },
};

const CONTROLLED_REPLAY_COPY = {
  eyebrow: "Controlled replay",
  subtitle:
    "Deterministic CONTROLLED_REPLAY scenarios through the real ingest → OE → Radar path. Watch and Dismiss persist learning records; never Live market data or Live trading authority.",
  restriction: {
    title: "CONTROLLED REPLAY · NOT LIVE MARKET DATA",
    body: "Watch/Dismiss exercise DecisionTrace and TradeReview only. No broker order submission. Reset with: python tools/imp.py controlled-replay reset",
  },
};

/**
 * Radar — the canonical discovery queue (find → rank → investigate).
 * Opportunities tab: ranked OE queue + selected opportunity detail.
 * Screeners tab: investigation screener + donor research bridges.
 * Mode honesty: Demo read-only, Paper full discovery mutations, Live
 * read-only monitor. Controlled replay (backend flag) enables Watch/Dismiss
 * learning acks without Paper or Live authority. No surface implies real-money action.
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
  const contextQuery = useContextQuery();
  const asOf = contextQuery.data?.as_of_context as
    | { controlled_replay?: boolean; evidence_class?: string }
    | undefined;
  const controlledReplay =
    Boolean(asOf?.controlled_replay) ||
    String(asOf?.evidence_class ?? "").toUpperCase() === "CONTROLLED_REPLAY";
  const copy = controlledReplay ? CONTROLLED_REPLAY_COPY : MODE_COPY[mode];
  const paper = mode === "PAPER";
  const live = mode === "LIVE";
  const paperActions = (paper && paperActionsPermitted) || controlledReplay;
  const portfolioQuery = usePaperPortfolioQuery("PAPER", paper && paperActionsPermitted);
  const paperAccountId = controlledReplay
    ? CONTROLLED_REPLAY_ACCOUNT_ID
    : paper && paperActionsPermitted
      ? portfolioQuery.data?.account.paper_account_id
      : undefined;
  const [searchParams] = useSearchParams();
  const filterQuery = tab === "screeners" ? (searchParams.get("q") ?? undefined) : undefined;
  // Deep link from the Command signal→opportunity bridge: `/radar?selected=<id>`
  // preselects the ranked row (and opens the detail sheet on narrow layouts).
  const selectedParam = tab === "opportunities" ? searchParams.get("selected") : null;
  // Controlled replay allows Watch/Dismiss; other Demo/Live surfaces stay read-only.
  const readOnly = controlledReplay ? false : !paper;

  return (
    <section
      className="page imp-radar-page"
      data-mode={mode}
      data-controlled-replay={controlledReplay ? "1" : "0"}
    >
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
          mode={mode}
          readOnly={readOnly}
          paperAccountId={paperAccountId}
          paperActions={paperActions}
          initialSelectedKey={selectedParam}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      ) : (
        <div className="imp-radar-screeners" data-testid="imp-radar-screeners">
          <section
            className="imp-radar-screener-section imp-radar-investigation-only"
            aria-label="Investigation-only screener"
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
          <section className="imp-radar-screener-section" aria-label="Research screens">
            <header className="imp-radar-section-header">
              <h2>Research screens</h2>
              <p className="imp-radar-section-lead">
                Donor screener bridges with provenance — squeeze cohort, scanner, futures, and
                catalyst screens.
              </p>
              <p className="imp-radar-section-lead">
                <Link to="/research/evidence?panel=squeeze_outcomes">
                  Open the research evidence behind these screens
                </Link>
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

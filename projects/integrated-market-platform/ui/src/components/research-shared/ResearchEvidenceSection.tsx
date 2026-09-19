import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useResearchAnalyticsQuery } from "../../api/hooks";
import type { ResearchAnalyticsResponse } from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { LoadingState } from "../shared/LoadingState";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { CountBarChartPanel, SignalTimelineChartPanel } from "../charts/ResearchChartPanels";
import type { Mode } from "../mode-session/types";
import { ResearchClaimHops } from "./ResearchClaimGraph";
import {
  RESEARCH_FINDINGS,
  claimHopsForFinding,
  parseClaimFindingParam,
  presentFindingAvailability,
  researchPanel,
  sectionClaimHops,
  type ResearchFindingDescriptor,
} from "./researchPresentation";

/**
 * Research Evidence — the findings layer. Each analytics panel is presented
 * as a first-class research finding: the claim in words first, then state,
 * then the distribution with a mandatory tabular summary, then provenance.
 * `?panel=<key>` deep-links (e.g. from Radar research screens) scroll to and
 * highlight the finding.
 */
type AvailabilityFilter = "all" | "available" | "empty" | "unavailable";

type Props = {
  mode: Mode;
};

export function ResearchEvidenceSection({ mode }: Props) {
  const analyticsQuery = useResearchAnalyticsQuery();
  const [searchParams] = useSearchParams();
  const panelParam = searchParams.get("panel");
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityFilter>("all");

  const followedFinding =
    parseClaimFindingParam(searchParams.get("claim")) ?? parseClaimFindingParam(panelParam);
  const highlighted = RESEARCH_FINDINGS.find((finding) => finding.key === panelParam)?.anchor;
  const [settledHighlight, setSettledHighlight] = useState<string | null>(null);
  useEffect(() => {
    if (!highlighted || settledHighlight === highlighted) return;
    if (analyticsQuery.isLoading) return;
    const target = document.getElementById(highlighted);
    if (!target) return;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "start" });
    }
    setSettledHighlight(highlighted);
  }, [highlighted, settledHighlight, analyticsQuery.isLoading]);

  if (analyticsQuery.isLoading) {
    return <LoadingState label="Loading research evidence…" />;
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return (
      <ErrorState
        title="Research evidence is unavailable right now."
        affects="Findings cannot be displayed until the research analytics endpoint responds."
        rawDetail={
          analyticsQuery.error instanceof Error ? analyticsQuery.error.message : undefined
        }
        onRetry={() => void analyticsQuery.refetch()}
      />
    );
  }

  const analytics = analyticsQuery.data;
  const visibleFindings =
    availabilityFilter === "all"
      ? RESEARCH_FINDINGS
      : RESEARCH_FINDINGS.filter((finding) => {
          const label = presentFindingAvailability(researchPanel(analytics, finding.key)).label;
          if (availabilityFilter === "available") return label === "Available";
          if (availabilityFilter === "empty") return label === "Empty";
          return label === "Unavailable";
        });

  return (
    <section className="research-evidence" aria-labelledby="research-evidence-heading">
      <div className="research-panel-heading">
        <div>
          <div className="research-panel-kicker">Findings</div>
          <h2 id="research-evidence-heading">Evidence at the current cutoff</h2>
        </div>
        {analytics.as_of_context ? (
          <FreshnessIndicator asOf={analytics.as_of_context.as_of_time} decays={false} />
        ) : null}
      </div>
      <p className="research-muted">
        Each finding is a distribution over a replay-bound window with its source and method
        disclosed. These panels describe evidence — they do not rank opportunities, predict
        outcomes, or authorize any action. The contracts do not mark evidence as supporting or
        contradictory, so no such claim is made here.
      </p>
      <ResearchClaimHops
        hops={sectionClaimHops("evidence", mode, followedFinding ?? undefined)}
        label="From this evidence"
      />
      <div className="research-local-filter">
        <label htmlFor="research-finding-filter">Show findings</label>
        <select
          id="research-finding-filter"
          value={availabilityFilter}
          onChange={(event) =>
            setAvailabilityFilter(event.target.value as AvailabilityFilter)
          }
        >
          <option value="all">All findings</option>
          <option value="available">Available</option>
          <option value="empty">Empty in this window</option>
          <option value="unavailable">Unavailable</option>
        </select>
        <p className="research-muted">
          Filters this page only. There is no research catalog search API — availability comes
          from the current analytics payload.
        </p>
      </div>

      {visibleFindings.length === 0 ? (
        <p className="research-muted" role="status">
          No findings match this page-only filter.
        </p>
      ) : (
        visibleFindings.map((finding) => (
          <FindingArticle
            key={finding.key}
            finding={finding}
            analytics={analytics}
            highlighted={highlighted === finding.anchor}
            mode={mode}
          />
        ))
      )}
    </section>
  );
}

function FindingArticle({
  finding,
  analytics,
  highlighted,
  mode,
}: {
  finding: ResearchFindingDescriptor;
  analytics: ResearchAnalyticsResponse;
  highlighted: boolean;
  mode: Mode;
}) {
  const panel = researchPanel(analytics, finding.key);
  const availability = presentFindingAvailability(panel);
  const provenance = panel?.provenance;

  return (
    <article
      className="research-finding"
      id={finding.anchor}
      data-highlighted={highlighted ? "true" : undefined}
      aria-label={finding.title}
    >
      {finding.key === "strategy_outcomes" ? (
        <>
          <CountBarChartPanel
            title={finding.title}
            series={panel?.series ?? []}
            provenance={{
              source: String(provenance?.source ?? "Unavailable"),
              method: provenance?.method ? String(provenance.method) : undefined,
            }}
            emptyMessage={availability.detail}
            ariaLabel="Strategy interpretation outcome bar chart"
          >
            <FindingIntro finding={finding} tone={availability.tone} stateLabel={availability.label} />
          </CountBarChartPanel>
          {panel?.signal_timeline?.length ? (
            <SignalTimelineChartPanel
              title="Cumulative strategy signals (walk-forward)"
              timeline={panel.signal_timeline}
              provenance={{
                source: String(provenance?.source ?? "Unavailable"),
                method: "Cumulative signal count by observation index at cutoff",
              }}
              ariaLabel="Walk-forward signal timeline chart"
            />
          ) : null}
        </>
      ) : (
        <CountBarChartPanel
          title={finding.title}
          series={panel?.series ?? []}
          provenance={{
            source: String(provenance?.source ?? "Unavailable"),
            method: provenance?.method ? String(provenance.method) : undefined,
          }}
          emptyMessage={availability.detail}
          ariaLabel={`${finding.title} bar chart`}
        >
          <FindingIntro finding={finding} tone={availability.tone} stateLabel={availability.label} />
        </CountBarChartPanel>
      )}

      <ResearchClaimHops hops={claimHopsForFinding(finding.key, mode)} />

      <details className="research-methodology">
        <summary>Methodology</summary>
        <dl className="research-fact-grid">
          <div>
            <dt>Evidence class</dt>
            <dd>{finding.evidenceClass}</dd>
          </div>
          <div>
            <dt>Source (raw)</dt>
            <dd>{provenance?.source ? String(provenance.source) : "Unavailable"}</dd>
          </div>
          <div>
            <dt>Method (raw)</dt>
            <dd>{provenance?.method ? String(provenance.method) : "Unavailable"}</dd>
          </div>
          {panel?.reason ? (
            <div>
              <dt>Unavailable reason (raw)</dt>
              <dd>{panel.reason}</dd>
            </div>
          ) : null}
        </dl>
        {panel?.cohort_metadata ? (
          <JsonDetailPanel title="Cohort metadata" value={panel.cohort_metadata} />
        ) : null}
      </details>
    </article>
  );
}

function FindingIntro({
  finding,
  tone,
  stateLabel,
}: {
  finding: ResearchFindingDescriptor;
  tone: SemanticTone;
  stateLabel: string;
}) {
  return (
    <div className="research-finding-intro">
      <p className="research-finding-claim">{finding.claim}</p>
      <p className="research-finding-why">{finding.whyItMatters}</p>
      <p className="research-finding-meta">
        <StatePill tone={tone} label={stateLabel} size="sm" />
        <span className="research-evidence-class">{finding.evidenceClass}</span>
      </p>
    </div>
  );
}

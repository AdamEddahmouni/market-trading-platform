import { Link, useSearchParams } from "react-router-dom";
import {
  useResearchAnalyticsQuery,
  useResearchModelsQuery,
  useResearchSimulationQuery,
} from "../../api/hooks";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { LoadingState } from "../shared/LoadingState";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import type { Mode } from "../mode-session/types";
import { ResearchClaimGraph } from "./ResearchClaimGraph";
import {
  RESEARCH_FINDINGS,
  buildClaimLineage,
  buildEvidenceAvailability,
  buildResearchSynthesis,
  listFindingSources,
  resolveFollowedFinding,
  type ResearchSynthesisInput,
} from "./researchPresentation";

type Props = {
  mode: Mode;
};

/**
 * Research Overview — the default Research section. Answers "what does the
 * evidence currently show, how much should I trust it, and what is missing?"
 * Every number is derived from a research contract field; concepts the
 * contracts do not expose (hypotheses, domains, source catalog, contradiction
 * flags, FTEP campaign state) are stated as honest gaps, never fabricated.
 */
export function ResearchOverviewSection({ mode }: Props) {
  const [searchParams] = useSearchParams();
  const analyticsQuery = useResearchAnalyticsQuery();
  const modelsQuery = useResearchModelsQuery();
  const simulationQuery = useResearchSimulationQuery();

  const loading =
    analyticsQuery.isLoading || modelsQuery.isLoading || simulationQuery.isLoading;

  const input: ResearchSynthesisInput = {
    analytics: analyticsQuery.data ?? null,
    models: modelsQuery.data ?? null,
    simulation: simulationQuery.data ?? null,
  };
  const synthesis = buildResearchSynthesis(input);
  const availability = buildEvidenceAvailability(input);
  const followedFinding = resolveFollowedFinding(searchParams.get("claim"), input.analytics);
  const claimLineage = buildClaimLineage(input, mode, followedFinding);

  const epistemicClass =
    analyticsQuery.data?.epistemic_class ??
    modelsQuery.data?.epistemic_class ??
    simulationQuery.data?.epistemic_class;
  const authorityBoundary =
    analyticsQuery.data?.authority_boundary ??
    modelsQuery.data?.authority_boundary ??
    simulationQuery.data?.authority_boundary;
  const asOf = analyticsQuery.data?.as_of_context ?? modelsQuery.data?.as_of_context;
  const epistemic = resolveSemanticState("research", epistemicClass);
  const boundary = resolveSemanticState("research", authorityBoundary);

  return (
    <>
      <section className="research-panel research-synthesis" aria-labelledby="research-synthesis-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">What the evidence shows</div>
            <h2 id="research-synthesis-heading">Current research picture</h2>
          </div>
          {asOf ? (
            <FreshnessIndicator asOf={asOf.as_of_time} decays={false} />
          ) : null}
        </div>

        {loading ? (
          <LoadingState label="Loading research evidence…" />
        ) : (
          <>
            <div className="research-trust-row">
              {epistemicClass ? (
                <StatePill tone={epistemic.tone} label={epistemic.label} raw={epistemic.raw} />
              ) : null}
              {authorityBoundary ? (
                <StatePill tone={boundary.tone} label={boundary.label} raw={boundary.raw} />
              ) : null}
            </div>
            {synthesis.length ? (
              <ul className="research-synthesis-lines">
                {synthesis.map((line, index) => (
                  <li key={`${line.id}-${index}`}>
                    <Link to={line.href}>{line.text}</Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="research-muted">
                No research payloads responded — the sections below show what is missing.
              </p>
            )}
            {analyticsQuery.isError || modelsQuery.isError || simulationQuery.isError ? (
              <ErrorState
                title="Part of the research evidence could not be loaded."
                affects="The synthesis above only reflects the sources that responded."
                onRetry={() => {
                  void analyticsQuery.refetch();
                  void modelsQuery.refetch();
                  void simulationQuery.refetch();
                }}
              />
            ) : null}
          </>
        )}
      </section>

      <section className="research-panel" aria-labelledby="research-claim-graph-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Claim thread</div>
            <h2 id="research-claim-graph-heading">Navigate this claim</h2>
          </div>
        </div>
        <p className="research-muted">
          Follow one analytics finding through source, hypothesis, strategy, experiment, evidence,
          contradiction, implementation, and forward-test status. Choosing a finding scopes the
          path; it does not create a trade or a ranked opportunity.
        </p>
        <nav className="research-claim-picker" aria-label="Finding to follow">
          {RESEARCH_FINDINGS.map((finding) => (
            <Link
              key={finding.key}
              to={`/research?claim=${finding.key}`}
              aria-current={followedFinding === finding.key ? "page" : undefined}
              aria-label={`Follow finding ${finding.title}`}
            >
              {finding.title}
            </Link>
          ))}
        </nav>
        {loading ? (
          <LoadingState label="Loading claim navigation…" />
        ) : (
          <>
            <p className="research-finding-claim">{claimLineage.reading}</p>
            <ResearchClaimGraph nodes={claimLineage.nodes} activeKey="evidence" />
          </>
        )}
      </section>

      <section className="research-panel" aria-labelledby="research-availability-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Finding coverage</div>
            <h2 id="research-availability-heading">Evidence panels at this cutoff</h2>
          </div>
        </div>
        {loading ? (
          <LoadingState label="Loading coverage…" />
        ) : (
          <ul className="research-availability-list">
            {availability.map((row) => (
              <li key={row.id} className="research-availability-row">
                <StatePill tone={row.tone} label={row.stateLabel} size="sm" />
                <div className="research-availability-body">
                  <Link to={row.href}>{row.label}</Link>
                  <p className="research-muted">{row.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="research-panel" aria-labelledby="research-bridges-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Connected elsewhere</div>
            <h2 id="research-bridges-heading">How this relates to decisions</h2>
          </div>
        </div>
        <ul className="research-bridge-list">
          <li>
            <Link to="/radar">Radar opportunities</Link> — individual opportunities can carry
            attached research-artifact evidence (Edge Stats, options-flow replay). That evidence is
            EVIDENCE_NOT_PREDICTION: context, never a ranking input or an execution signal.
          </li>
          <li>
            <Link to="/radar/screeners">Radar research screens</Link> — the donor squeeze, futures,
            and catalyst screens draw on the same historical evidence summarized in the{" "}
            <Link to="/research/evidence">Evidence section</Link>.
          </li>
          {mode === "PAPER" ? (
            <li>
              <Link to="/research/validation">Strategy outcomes in Paper</Link> — the Paper session
              reconstructs strategy allocation lineage from the ledger; the ledger stays
              authoritative.
            </li>
          ) : null}
          {mode === "LIVE" ? (
            <li>
              Research stays replay-bound in Live mode. Operational safety signals live on the{" "}
              <Link to="/live-canary">live canary</Link>, not here.
            </li>
          ) : null}
        </ul>
      </section>

      <section className="research-panel" aria-labelledby="research-gaps-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Honest limits</div>
            <h2 id="research-gaps-heading">What stays off this graph</h2>
          </div>
        </div>
        <p className="research-muted">
          Hypothesis objects, supporting/contradictory flags, a source catalog, and FTEP campaign
          state have no Research UI contract. Off-path and gap nodes stay labeled — they are not
          filled in from program docs and they are not action buttons.
        </p>
      </section>

      <details className="research-panel research-methodology" id="research-sources">
        <summary>Sources on this payload</summary>
        <p className="research-muted">
          There is no research source catalog. Each finding discloses the source and method
          attached to its panel — listed here as they appear on the current analytics payload.
        </p>
        {analyticsQuery.data ? (
          <ul className="research-source-list">
            {listFindingSources(analyticsQuery.data).map((row) => (
              <li key={row.source}>
                <strong>{row.source}</strong>
                <span className="research-muted"> — {row.findings.join(", ")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="research-muted">Analytics payload not loaded — sources unavailable.</p>
        )}
      </details>

      <details className="research-panel research-methodology">
        <summary>Methodology and technical detail</summary>
        <dl className="research-fact-grid">
          <div>
            <dt>Epistemic class (raw)</dt>
            <dd>{epistemicClass ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Authority boundary (raw)</dt>
            <dd>{authorityBoundary ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Window (raw)</dt>
            <dd>{asOf?.as_of_time ?? "Unavailable"}</dd>
          </div>
          {asOf?.replay_session_id ? (
            <div>
              <dt>Replay session</dt>
              <dd>
                <CopyableIdentifier value={asOf.replay_session_id} chars={4} />
              </dd>
            </div>
          ) : null}
        </dl>
        {analyticsQuery.data?.disclaimer ? (
          <p className="research-muted">{analyticsQuery.data.disclaimer}</p>
        ) : null}
      </details>
    </>
  );
}

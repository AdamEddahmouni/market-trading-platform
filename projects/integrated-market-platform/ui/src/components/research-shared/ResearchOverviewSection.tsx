import { Link } from "react-router-dom";
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
import {
  buildEvidenceAvailability,
  buildResearchSynthesis,
  listFindingSources,
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
                  <li key={`${line.id}-${index}`}>{line.text}</li>
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

      <section className="research-panel" aria-labelledby="research-availability-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Coverage</div>
            <h2 id="research-availability-heading">Where the evidence stands</h2>
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
            <h2 id="research-gaps-heading">What this surface cannot tell you yet</h2>
          </div>
        </div>
        <ul className="research-gap-list">
          <li>
            <strong>Hypothesis tracking.</strong> The current contracts do not expose hypotheses as
            first-class objects with lifecycle states. The closest truth is the per-observation
            interpretation record in the{" "}
            <Link to="/research/validation">Validation section</Link>.
          </li>
          <li>
            <strong>Supporting vs contradictory flags.</strong> No contract marks evidence as
            supporting or contradictory, so nothing here is presented as contradiction or proof.
            The only conflict signal the backend emits is the{" "}
            <code>ABSTAIN_CONFLICTING_EVIDENCE</code> abstention reason on strategy
            interpretations.
          </li>
          <li>
            <strong>Research domains and source catalog.</strong> No domain taxonomy or source
            registry endpoint exists; each finding discloses its own source and method instead.
          </li>
          <li>
            <strong>Experiment campaigns (FTEP).</strong> Governed forward-test campaign state is
            not exposed to this surface. The{" "}
            <Link to="/lab">Lab workbench</Link> documents that gap; the deterministic simulation
            in the <Link to="/research/simulation">Simulation section</Link> is a research run — it
            is not a governed campaign result and not production readiness.
          </li>
        </ul>
      </section>

      <details className="research-panel research-methodology">
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

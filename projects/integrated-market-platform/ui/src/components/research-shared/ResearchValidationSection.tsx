import { Link, useSearchParams } from "react-router-dom";
import { useResearchModelsQuery } from "../../api/hooks";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { LoadingState } from "../shared/LoadingState";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { PaperStrategyProfitabilityObservability } from "../paper-strategy-profitability/PaperStrategyProfitabilityObservability";
import type { Mode } from "../mode-session/types";
import { ResearchClaimHops } from "./ResearchClaimGraph";
import {
  formatResearchTime,
  interpretationHasConflict,
  parseClaimFindingParam,
  presentAbstentionReason,
  presentPreregistration,
  sectionClaimHops,
} from "./researchPresentation";

type Props = {
  mode: Mode;
};

/**
 * Research Validation — which strategy/model the research comes from and how
 * validated it is: walk-forward folds, preregistration gate, and the
 * per-observation interpretation record (signal vs abstention, with abstention
 * reasons humanized). Identity hashes and raw specs stay in Methodology (L4).
 */
export function ResearchValidationSection({ mode }: Props) {
  const modelsQuery = useResearchModelsQuery();
  const [searchParams] = useSearchParams();
  const conflictOnly = searchParams.get("conflict") === "1";

  if (modelsQuery.isLoading) {
    return <LoadingState label="Loading strategy validation…" />;
  }

  if (modelsQuery.isError || !modelsQuery.data) {
    return (
      <ErrorState
        title="Strategy validation is unavailable right now."
        affects="The model and walk-forward record cannot be displayed until the research models endpoint responds."
        rawDetail={modelsQuery.error instanceof Error ? modelsQuery.error.message : undefined}
        onRetry={() => void modelsQuery.refetch()}
      />
    );
  }

  const payload = modelsQuery.data;
  const summary = payload.model_summary;
  const spec = payload.strategy_spec;
  const manifest = payload.dataset_manifest;
  const preregistration = presentPreregistration(payload.preregistration_status);
  const boundary = resolveSemanticState("research", payload.authority_boundary);
  const identityHash = summary.strategy_identity_hash ?? spec.strategy_identity_hash;
  const datasetFingerprint = summary.dataset_fingerprint ?? manifest.dataset_fingerprint;
  const visibleInterpretations = conflictOnly
    ? payload.interpretations.filter((row) => interpretationHasConflict(row))
    : payload.interpretations;

  return (
    <>
      <section className="research-panel" aria-labelledby="research-validation-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Strategy validation</div>
            <h2 id="research-validation-heading">How validated is this research?</h2>
          </div>
          {payload.as_of_context ? (
            <FreshnessIndicator asOf={payload.as_of_context.as_of_time} decays={false} />
          ) : null}
        </div>

        <p className="research-finding-claim">
          Model family {String(summary.model_family ?? "Unavailable")} · alignment{" "}
          {String(summary.alignment_type ?? spec.alignment_type ?? "Unavailable")} ·{" "}
          {payload.walk_forward_fold_count} walk-forward{" "}
          {payload.walk_forward_fold_count === 1 ? "fold" : "folds"} ·{" "}
          {payload.interpretation_summary.signal_count}{" "}
          {payload.interpretation_summary.signal_count === 1 ? "signal" : "signals"} /{" "}
          {payload.interpretation_summary.abstention_count}{" "}
          {payload.interpretation_summary.abstention_count === 1 ? "abstention" : "abstentions"}.
        </p>

        <dl className="research-fact-grid">
          <div>
            <dt>Preregistration</dt>
            <dd>
              <StatePill
                tone={preregistration.tone}
                label={preregistration.label}
                raw={preregistration.raw}
              />
            </dd>
          </div>
          <div>
            <dt>Walk-forward folds</dt>
            <dd>{payload.walk_forward_fold_count}</dd>
          </div>
          <div>
            <dt>Observations at cutoff</dt>
            <dd>{payload.interpretation_summary.total_at_cutoff}</dd>
          </div>
          <div>
            <dt>Authority boundary</dt>
            <dd>
              <StatePill tone={boundary.tone} label={boundary.label} raw={boundary.raw} />
            </dd>
          </div>
        </dl>

        <p className="research-muted">
          Walk-forward evaluation replays the strategy against historical observations in order;
          preregistration means the strategy was frozen before it saw the data. Neither makes the
          output a prediction or grants trade authority.
        </p>
        <p className="research-muted">
          <Link to="/lab/validation">Inspect this validation workflow in Lab</Link> — Lab is the
          process surface; this page stays the interpretation of the result.
        </p>
        <ResearchClaimHops
          hops={sectionClaimHops("validation", mode, parseClaimFindingParam(searchParams.get("claim")) ?? undefined)}
          label="From this strategy"
        />
      </section>

      <section className="research-panel" aria-labelledby="research-interpretations-heading">
        <div className="research-panel-heading">
          <div>
            <div className="research-panel-kicker">Record</div>
            <h2 id="research-interpretations-heading">Interpretation record</h2>
          </div>
        </div>
        {payload.interpretations.length === 0 ? (
          <p className="research-muted" role="status">
            No interpretations fall inside the current replay window — the strategy has not
            evaluated any observation yet at this cutoff.
          </p>
        ) : (
          <div className="research-table-wrap">
            {conflictOnly ? (
              <p className="research-muted" role="status">
                Showing only observations with ABSTAIN_CONFLICTING_EVIDENCE.{" "}
                <Link to="/research/validation">Show the full interpretation record</Link>.
              </p>
            ) : (
              <p className="research-muted">
                <Link to="/research/validation?conflict=1">Show contract-backed conflicts only</Link>.
              </p>
            )}
            {visibleInterpretations.length === 0 ? (
              <p className="research-muted" role="status">
                No ABSTAIN_CONFLICTING_EVIDENCE rows in this window.
              </p>
            ) : (
            <table className="data-table">
              <caption className="chart-data-caption">
                Per-observation strategy interpretations at the current cutoff
              </caption>
              <thead>
                <tr>
                  <th scope="col">Observation</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Why abstained</th>
                  <th scope="col">Cutoff</th>
                </tr>
              </thead>
              <tbody>
                {visibleInterpretations.map((row, index) => {
                  const outcome = resolveSemanticState(
                    "research",
                    row.outcome == null ? undefined : String(row.outcome),
                  );
                  const reasons = Array.isArray(row.abstention_reason_codes)
                    ? row.abstention_reason_codes.map((code) => String(code))
                    : [];
                  const observation = formatResearchTime(row.observation_time);
                  const cutoff = formatResearchTime(row.prediction_cutoff);
                  const conflicted = interpretationHasConflict(row);
                  return (
                    <tr
                      key={`${String(row.observation_time ?? index)}-${index}`}
                      data-conflicted={conflicted ? "true" : undefined}
                    >
                      <td>{observation ?? "Unavailable"}</td>
                      <td>
                        <StatePill tone={outcome.tone} label={outcome.label} raw={outcome.raw} size="sm" />
                      </td>
                      <td>
                        {reasons.length ? (
                          <ul className="research-reason-list">
                            {reasons.map((code) => (
                              <li key={code}>
                                <span title={code}>{presentAbstentionReason(code).label}</span>
                              </li>
                            ))}
                          </ul>
                        ) : outcome.raw === "signal" ? (
                          "—"
                        ) : (
                          "Not reported"
                        )}
                      </td>
                      <td>{cutoff ?? "Unavailable"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            )}
          </div>
        )}
      </section>

      <details className="research-panel research-methodology">
        <summary>Methodology and technical detail</summary>
        <dl className="research-fact-grid">
          <div>
            <dt>Strategy identity hash</dt>
            <dd>
              {identityHash ? (
                <CopyableIdentifier value={String(identityHash)} chars={6} />
              ) : (
                "Unavailable"
              )}
            </dd>
          </div>
          <div>
            <dt>Dataset fingerprint</dt>
            <dd>
              {datasetFingerprint ? (
                <CopyableIdentifier value={String(datasetFingerprint)} chars={6} />
              ) : (
                "Unavailable"
              )}
            </dd>
          </div>
          <div>
            <dt>Epistemic class (raw)</dt>
            <dd>{payload.epistemic_class ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Authority boundary (raw)</dt>
            <dd>{payload.authority_boundary}</dd>
          </div>
        </dl>
        {payload.disclaimer ? <p className="research-muted">{payload.disclaimer}</p> : null}
        <JsonDetailPanel title="Strategy specification" value={payload.strategy_spec} />
        <JsonDetailPanel title="Dataset manifest" value={payload.dataset_manifest} />
        <JsonDetailPanel title="Preregistration record" value={payload.preregistration} />
      </details>

      {mode === "PAPER" ? (
        <section className="research-panel" aria-labelledby="research-paper-strategy-heading">
          <div className="research-panel-heading">
            <div>
              <div className="research-panel-kicker">Strategy context</div>
              <h2 id="research-paper-strategy-heading">Strategy outcomes in Paper</h2>
            </div>
          </div>
          <p className="research-muted">
            Read-only reconstruction of strategy allocation lineage in the current Paper session.
            This is context for the research above — the portfolio ledger remains authoritative.
          </p>
          <PaperStrategyProfitabilityObservability />
        </section>
      ) : null}
    </>
  );
}

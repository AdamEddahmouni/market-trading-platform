import { Link } from "react-router-dom";
import { useResearchModelsQuery } from "../../api/hooks";
import { resolveSemanticState } from "../../state/semanticState";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { LoadingState } from "../shared/LoadingState";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import {
  formatResearchTime,
  interpretationHasConflict,
  presentAbstentionReason,
  presentPreregistration,
} from "../research-shared/researchPresentation";
import {
  datasetFingerprint,
  modelAlignment,
  modelFamily,
  strategyIdentityHash,
  validationResultSummary,
} from "./labPresentation";

/**
 * Lab Validation workbench — process, recorded configuration, and current
 * result. Interpretation of that result lives in Research.
 */
export function LabValidationSection() {
  const modelsQuery = useResearchModelsQuery();

  if (modelsQuery.isLoading) {
    return <LoadingState label="Loading validation workflow…" />;
  }

  if (modelsQuery.isError || !modelsQuery.data) {
    return (
      <ErrorState
        title="The validation workflow snapshot is unavailable."
        affects="Target, methodology, and current result cannot be inspected until /research/models responds."
        rawDetail={modelsQuery.error instanceof Error ? modelsQuery.error.message : undefined}
        onRetry={() => void modelsQuery.refetch()}
      />
    );
  }

  const payload = modelsQuery.data;
  const preregistration = presentPreregistration(payload.preregistration_status);
  const boundary = resolveSemanticState("research", payload.authority_boundary);
  const epistemic = resolveSemanticState("research", payload.epistemic_class);
  const identityHash = strategyIdentityHash(payload);
  const fingerprint = datasetFingerprint(payload);
  const family = modelFamily(payload);
  const alignment = modelAlignment(payload);

  return (
    <>
      <section className="lab-panel" aria-labelledby="lab-validation-heading">
        <div className="lab-panel-heading">
          <div>
            <div className="lab-panel-kicker">Validation workflow</div>
            <h2 id="lab-validation-heading">Walk-forward model validation</h2>
          </div>
          {payload.as_of_context ? (
            <FreshnessIndicator asOf={payload.as_of_context.as_of_time} decays={false} />
          ) : null}
        </div>
        <div className="lab-trust-row">
          <StatePill tone="research" label="Read-only" raw="inspectable" />
          <StatePill tone={preregistration.tone} label={preregistration.label} raw={preregistration.raw} />
          <StatePill tone={boundary.tone} label={boundary.label} raw={boundary.raw} />
          <StatePill tone={epistemic.tone} label={epistemic.label} raw={epistemic.raw} />
        </div>
        <p className="lab-claim">{validationResultSummary(payload)}</p>
        <p className="lab-muted">
          This workflow cannot be started, cancelled, or retried from Lab. There is no live run
          state in the contract — only the current projection at cutoff. A passing walk-forward
          does not make this an active production strategy or grant execution authority.
        </p>
        <div className="lab-actions">
          <Link to="/research/validation">View interpretation in Research</Link>
        </div>
      </section>

      <section className="lab-panel" aria-labelledby="lab-validation-before-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">Before run</div>
          <h2 id="lab-validation-before-heading">Target and recorded methodology</h2>
        </div>
        <dl className="lab-fact-grid">
          <div>
            <dt>Model family</dt>
            <dd>{family}</dd>
          </div>
          <div>
            <dt>Alignment</dt>
            <dd>{alignment}</dd>
          </div>
          <div>
            <dt>Walk-forward folds</dt>
            <dd>{payload.walk_forward_fold_count}</dd>
          </div>
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
        </dl>
        <p className="lab-muted">
          Configuration is recorded on the payload. Lab does not expose editor fields because the
          backend accepts no validation request body.
        </p>
      </section>

      <section className="lab-panel" aria-labelledby="lab-validation-during-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">During run</div>
          <h2 id="lab-validation-during-heading">Run state</h2>
        </div>
        <p className="lab-muted" role="status">
          Queued, running, cancelled, and progress fields are not on this contract. Lab will not
          invent them.
        </p>
      </section>

      <section className="lab-panel" aria-labelledby="lab-validation-after-heading">
        <div className="lab-stage">
          <div className="lab-panel-kicker">After run</div>
          <h2 id="lab-validation-after-heading">Current result</h2>
        </div>
        <dl className="lab-fact-grid">
          <div>
            <dt>Signals</dt>
            <dd>{payload.interpretation_summary.signal_count}</dd>
          </div>
          <div>
            <dt>Abstentions</dt>
            <dd>{payload.interpretation_summary.abstention_count}</dd>
          </div>
          <div>
            <dt>Observations at cutoff</dt>
            <dd>{payload.interpretation_summary.total_at_cutoff}</dd>
          </div>
        </dl>
        {payload.interpretations.length === 0 ? (
          <p className="lab-muted" role="status">
            No interpretations fall inside the current replay window — no result rows exist at this
            cutoff.
          </p>
        ) : (
          <div className="lab-table-wrap">
            <table className="data-table">
              <caption className="chart-data-caption">
                Current validation outcomes (process view). Full interpretation lives in Research.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Observation</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Why abstained</th>
                </tr>
              </thead>
              <tbody>
                {payload.interpretations.map((row, index) => {
                  const outcome = resolveSemanticState(
                    "research",
                    row.outcome == null ? undefined : String(row.outcome),
                  );
                  const reasons = Array.isArray(row.abstention_reason_codes)
                    ? row.abstention_reason_codes.map((code) => String(code))
                    : [];
                  return (
                    <tr
                      key={`${String(row.observation_time ?? index)}-${index}`}
                      data-conflicted={interpretationHasConflict(row) ? "true" : undefined}
                    >
                      <td>{formatResearchTime(row.observation_time) ?? "Unavailable"}</td>
                      <td>
                        <StatePill tone={outcome.tone} label={outcome.label} raw={outcome.raw} size="sm" />
                      </td>
                      <td>
                        {reasons.length
                          ? reasons.map((code) => presentAbstentionReason(code).label).join(", ")
                          : outcome.raw === "signal"
                            ? "—"
                            : "Not reported"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <details className="lab-panel lab-methodology">
        <summary>Methodology and technical detail</summary>
        <dl className="lab-fact-grid">
          <div>
            <dt>Strategy identity hash</dt>
            <dd>
              {identityHash ? <CopyableIdentifier value={identityHash} chars={6} /> : "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>Dataset fingerprint</dt>
            <dd>
              {fingerprint ? <CopyableIdentifier value={fingerprint} chars={6} /> : "Unavailable"}
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
        {payload.disclaimer ? <p className="lab-muted">{payload.disclaimer}</p> : null}
        <JsonDetailPanel title="Strategy specification" value={payload.strategy_spec} />
        <JsonDetailPanel title="Dataset manifest" value={payload.dataset_manifest} />
        <JsonDetailPanel title="Preregistration record" value={payload.preregistration} />
      </details>
    </>
  );
}

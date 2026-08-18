import type { WorkspaceSqueezeResponse } from "../../api/client";
import { CausalIntelligenceBlock } from "./CausalIntelligenceBlock";
import { HistoricalSqueezeContextBlock } from "./HistoricalSqueezeContextBlock";
import { StateTransitionBlock } from "./StateTransitionBlock";

type Props = {
  instrumentId: string;
  squeeze: WorkspaceSqueezeResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
  onOpenHistory?: (symbol: string) => void;
  compact?: boolean;
};

export function SqueezeWorkspacePanel({
  instrumentId,
  squeeze,
  loading = false,
  onExplain,
  onInspect,
  onOpenHistory,
  compact = false,
}: Props) {
  return (
    <aside
      className={`capability-panel squeeze-panel ${squeeze?.available ? "available" : "unavailable"}`}
    >
      <h2>{compact ? "Short Squeeze" : `${instrumentId} — Short Squeeze`}</h2>
      {loading || !squeeze ? (
        <p>Loading squeeze evidence…</p>
      ) : squeeze.available ? (
        <>
          <p className="squeeze-disclaimer">{squeeze.disclaimer}</p>
          {squeeze.readiness ? (
            <p className="squeeze-readiness">
              Readiness: freshness {squeeze.readiness.freshness_state}
              {squeeze.readiness.provenance_admissible ? " · provenance PASS" : " · provenance gated"}
              {squeeze.readiness.rule_outcome_totals
                ? ` · ${Object.entries(squeeze.readiness.rule_outcome_totals)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(", ")}`
                : ""}
            </p>
          ) : null}
          {squeeze.provenance ? (
            <p className="squeeze-provenance">
              Provenance:{" "}
              {Object.entries(squeeze.provenance)
                .map(([key, value]) => `${key}=${String(value)}`)
                .join(" · ")}
            </p>
          ) : null}
          <StateTransitionBlock squeeze={squeeze} />
          <CausalIntelligenceBlock squeeze={squeeze} />
          {squeeze.ignition_evidence && squeeze.ignition_evidence.length > 0 ? (
            <div className="ignition-evidence-grid">
              {squeeze.ignition_evidence.map((card) => (
                <div
                  key={card.label}
                  className={`ignition-card ${card.state === "UNAVAILABLE" ? "unavailable" : "available"}`}
                >
                  <h3>{card.label}</h3>
                  <p className="ignition-state">{card.state}</p>
                  <p className="ignition-detail">{card.detail}</p>
                  {card.explain_ref && onExplain ? (
                    <button type="button" onClick={() => onExplain(card.explain_ref!)}>
                      Explain
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          {!compact ? (
            <dl className="squeeze-detail-grid">
              <div>
                <dt>Outcome</dt>
                <dd>{squeeze.outcome_status ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Evidence coverage</dt>
                <dd>{squeeze.evidence_coverage ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Research detection</dt>
                <dd>{squeeze.research_detection ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Phase 3A</dt>
                <dd>{squeeze.phase3a_summary ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>{squeeze.mode_label ?? "FROZEN_RESEARCH"}</dd>
              </div>
              <div>
                <dt>Epistemic class</dt>
                <dd>{squeeze.epistemic_class ?? "OBSERVED"}</dd>
              </div>
            </dl>
          ) : null}
          {squeeze.rules && squeeze.rules.length > 0 ? (
            <div className="squeeze-rules">
              <h3>Phase 3A rules ({squeeze.rules.length})</h3>
              <table className="squeeze-rules-table">
                <thead>
                  <tr>
                    <th>Rule</th>
                    <th>Category</th>
                    <th>Outcome</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {squeeze.rules.map((rule) => (
                    <tr key={rule.rule_id}>
                      <td>{rule.rule_id}</td>
                      <td>{rule.category}</td>
                      <td>{rule.outcome}</td>
                      <td>{rule.reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <HistoricalSqueezeContextBlock context={squeeze.historical_context} />
          {squeeze.explanation_ref && onExplain && onInspect ? (
            <div className="card-actions squeeze-actions">
              <button type="button" onClick={() => onExplain(squeeze.explanation_ref!)}>
                Explain state
              </button>
              {onOpenHistory ? (
                <button type="button" onClick={() => onOpenHistory(instrumentId)}>
                  History
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onInspect(squeeze.explanation_ref!.replace("explain:", "inspect:"))}
              >
                Open Inspector
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p>{squeeze.reason ?? "Donor squeeze bridge unavailable."}</p>
          {squeeze.ignition_evidence && squeeze.ignition_evidence.length > 0 ? (
            <div className="ignition-evidence-grid">
              {squeeze.ignition_evidence.map((card) => (
                <div
                  key={card.label}
                  className={`ignition-card ${card.state === "UNAVAILABLE" ? "unavailable" : "available"}`}
                >
                  <h3>{card.label}</h3>
                  <p className="ignition-state">{card.state}</p>
                  <p className="ignition-detail">{card.detail}</p>
                  {card.explain_ref && onExplain ? (
                    <button type="button" onClick={() => onExplain(card.explain_ref!)}>
                      Explain
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          <HistoricalSqueezeContextBlock context={squeeze.historical_context} />
        </>
      )}
    </aside>
  );
}

import type { OperatorDiagnostics } from "../../api/schemas";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import {
  buildOperatorSituation,
  buildOperatorTruthRows,
  diagnosticsGovernance,
  diagnosticsRuntimeSection,
  explainTruthClass,
  humanDiagnosticsHeadline,
  mapSeverityTone,
} from "./operatorDiagnosticsPresentation";

type Props = {
  diagnostics: OperatorDiagnostics | null | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

export function OperatorSystemStatusSection({ diagnostics, isLoading, isError, onRetry }: Props) {
  if (isLoading) {
    return (
      <p className="control-checking" role="status" aria-live="polite" aria-busy="true">
        Loading operator diagnostics… this is a load wait, not a calendar wait.
      </p>
    );
  }
  if (isError || !diagnostics) {
    return (
      <ErrorState
        title="Operator diagnostics are unavailable."
        affects="This is a load failure, not a calendar wait. System status, Item 9 gates, and runtime SHA cannot be verified until GET /operator/diagnostics responds."
        rawDetail="GET /operator/diagnostics"
        onRetry={onRetry}
      />
    );
  }

  const governance = diagnosticsGovernance(diagnostics);
  const runtime = diagnosticsRuntimeSection(diagnostics);
  const resilience = runtime?.runtime_resilience ?? {};
  const expectedCycle = (resilience.expected_cycle ?? {}) as Record<string, unknown>;
  const receiptInventory = (expectedCycle.receipt_inventory ?? {}) as Record<string, unknown>;
  const truthRows = buildOperatorTruthRows(diagnostics);
  const situation = buildOperatorSituation(diagnostics);
  const severityTone = mapSeverityTone(diagnostics.severity);
  const corpusScope = String(runtime?.item9_corpus_status?.receipt_scope ?? "");

  return (
    <div className="control-system-status">
      <div
        className="control-situation"
        data-kind={situation.kind}
        role="status"
        aria-live="polite"
      >
        <p className="control-situation-title">{situation.title}</p>
        <p className="control-situation-body">{situation.explanation}</p>
      </div>

      <div className="control-system-status-headline">
        <StatePill tone={severityTone} label={diagnostics.severity} raw={diagnostics.severity} />
        <p className="control-system-status-lead">{humanDiagnosticsHeadline(diagnostics)}</p>
      </div>

      {runtime?.git_sha ? (
        <p className="control-muted">
          Runtime SHA{" "}
          <CopyableIdentifier value={String(runtime.git_sha)} chars={12} />
        </p>
      ) : null}

      {corpusScope === "FROZEN_COLLECTOR_WORKTREE_READ_ONLY" ? (
        <p className="control-muted" role="note">
          Item 9 corpus sample gate uses governed frozen-collector receipts (read-only scan — not this UI
          worktree’s empty receipt dir).
        </p>
      ) : null}

      <p className="control-sr-only" id="control-truth-legend">
        Each row shows a canonical truth class, a trader explanation, and the raw tokens. IDLE means
        waiting. DEGRADED means impaired. Color is not the only indicator.
      </p>

      <ul
        className="control-truth-list"
        aria-label="Operator truth hierarchy"
        aria-describedby="control-truth-legend"
      >
        {truthRows.map((row) => (
          <li
            key={row.id}
            className="control-truth-row"
            data-truth={row.truth}
            data-kind={row.kind}
          >
            <div className="control-truth-label">
              <span className="control-truth-class">{row.truth}</span>
              <strong>{row.label}</strong>
              <span className="control-truth-kind">{kindLabel(row.kind)}</span>
            </div>
            <div className="control-truth-value">
              <StatePill tone={row.tone} label={row.truth} raw={row.truth} size="sm" />
              <p className="control-truth-meaning">{row.meaning}</p>
              <p className="control-truth-detail">{row.detail}</p>
              <p className="control-truth-class-hint">{explainTruthClass(row.truth)}</p>
            </div>
          </li>
        ))}
      </ul>

      <details className="control-details">
        <summary>Runtime resilience (#287 / #289)</summary>
        <dl className="control-details-grid">
          <div>
            <dt>Receipt inventory</dt>
            <dd>
              {String(receiptInventory.availability ?? "NOT_OBSERVED")}
              {receiptInventory.receipt_file_count != null
                ? ` · ${String(receiptInventory.receipt_file_count)} files`
                : ""}
            </dd>
          </div>
          <div>
            <dt>Provider connectivity</dt>
            <dd>
              {String((resilience.provider_connectivity as Record<string, unknown> | undefined)?.state ?? "UNKNOWN")}
            </dd>
          </div>
          <div>
            <dt>Collector match summaries</dt>
            <dd>
              {(
                ((resilience.collector_process as Record<string, unknown> | undefined)
                  ?.active_collector_match_summaries as string[] | undefined) ?? []
              ).join(", ") || "NOT_OBSERVED"}
            </dd>
          </div>
        </dl>
      </details>

      {governance?.interventions?.length ? (
        <div className="control-interventions">
          <h3>Requires operator action</h3>
          <ul>
            {governance.interventions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {governance?.forbidden?.length ? (
        <details className="control-details">
          <summary>Forbidden actions (policy)</summary>
          <ul className="control-forbidden-list">
            {governance.forbidden.map((token) => (
              <li key={token}>
                <code>{token}</code>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {governance?.allowed_read_only?.length ? (
        <details className="control-details">
          <summary>Allowed read-only actions</summary>
          <ul className="control-forbidden-list">
            {governance.allowed_read_only.map((token) => (
              <li key={token}>
                <code>{token}</code>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function kindLabel(kind: string): string {
  switch (kind) {
    case "waiting":
      return "Waiting";
    case "policy":
      return "Policy lock";
    case "fault":
      return "Needs repair";
    case "ok":
      return "Working";
    default:
      return "Unverified";
  }
}

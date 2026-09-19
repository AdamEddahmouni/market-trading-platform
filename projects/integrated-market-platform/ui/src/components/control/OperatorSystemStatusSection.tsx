import type { OperatorDiagnostics } from "../../api/schemas";
import { StatePill } from "../imp-ui/StatePill";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import {
  buildOperatorTruthRows,
  diagnosticsGovernance,
  diagnosticsRuntimeSection,
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
      <p className="control-checking" role="status">
        Loading operator diagnostics…
      </p>
    );
  }
  if (isError || !diagnostics) {
    return (
      <ErrorState
        title="Operator diagnostics are unavailable."
        affects="System status, Item 9 gates, and runtime SHA cannot be verified until GET /operator/diagnostics responds."
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
  const severityTone = mapSeverityTone(diagnostics.severity);
  const corpusScope = String(runtime?.item9_corpus_status?.receipt_scope ?? "");

  return (
    <div className="control-system-status">
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

      <ul className="control-truth-list" aria-label="Operator truth hierarchy">
        {truthRows.map((row) => (
          <li key={row.id} className="control-truth-row" data-truth={row.truth}>
            <div className="control-truth-label">
              <span className="control-truth-class">{row.truth}</span>
              <strong>{row.label}</strong>
            </div>
            <div className="control-truth-value">
              <StatePill tone={row.tone} label={row.truth} raw={row.truth} size="sm" />
              <p className="control-truth-detail">{row.detail}</p>
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
    </div>
  );
}

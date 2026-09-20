import type { OperatorDiagnostics } from "../../api/schemas";
import { StatePill } from "../imp-ui/StatePill";
import { EmptyState, ErrorState } from "../imp-ui/FeedbackStates";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import {
  buildOperatorSituation,
  buildOperatorTruthRows,
  buildUnavailableHonestyRows,
  buildUnavailableOperatorSituation,
  diagnosticsGovernance,
  diagnosticsRuntimeSection,
  explainTruthClass,
  humanDiagnosticsHeadline,
  mapSeverityTone,
  type OperatorTruthRow,
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
  if (isError) {
    const honestyRows = buildUnavailableHonestyRows("error");
    const situation = buildUnavailableOperatorSituation("error");
    return (
      <div className="control-system-status">
        <ErrorState
          title="Operator diagnostics are unavailable."
          affects="This is a load failure, not a calendar wait. Item 9 dates stay UNAVAILABLE, not a minted 2/3. Live OFF. Full30 OFF."
          rawDetail="GET /operator/diagnostics"
          onRetry={onRetry}
        />
        <HonestySituation situation={situation} />
        <HonestyTruthList rows={honestyRows} />
      </div>
    );
  }
  if (!diagnostics) {
    const honestyRows = buildUnavailableHonestyRows("empty");
    const situation = buildUnavailableOperatorSituation("empty");
    return (
      <div className="control-system-status">
        <EmptyState
          title="Operator diagnostics snapshot was not included"
          reason="This is UNKNOWN, not a load crash and not an Item 9 calendar wait. Item 9 dates are not 2/3 until a snapshot says so. Live OFF. Full30 OFF."
        />
        <HonestySituation situation={situation} />
        <HonestyTruthList rows={honestyRows} />
      </div>
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
      <HonestySituation situation={situation} />

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

      <HonestyTruthList rows={truthRows} />

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

function HonestySituation({
  situation,
}: {
  situation: ReturnType<typeof buildOperatorSituation>;
}) {
  return (
    <div className="control-situation" data-kind={situation.kind} role="status" aria-live="polite">
      <p className="control-situation-title">{situation.title}</p>
      <p className="control-situation-body">{situation.explanation}</p>
      <p className="control-situation-body">Next safe action: {situation.nextSafeAction}</p>
    </div>
  );
}

function HonestyTruthList({ rows }: { rows: OperatorTruthRow[] }) {
  return (
    <>
      <p className="control-sr-only" id="control-truth-legend">
        Each row shows a canonical truth class, a trader explanation, and the raw tokens. IDLE means
        waiting. POLICY means an intentional safety lock. DEGRADED means impaired. BLOCKED is reserved
        for real gates. UNAVAILABLE is a missing snapshot, not a minted 2/3. Color is not the only
        indicator.
      </p>

      <ul
        className="control-truth-list"
        aria-label="Operator truth hierarchy"
        aria-describedby="control-truth-legend"
      >
        {rows.map((row) => (
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
              <p className="control-truth-class-hint">{explainTruthClass(row.truth, row.kind)}</p>
              <p className="control-truth-class-hint">Next safe action: {row.nextSafeAction}</p>
            </div>
          </li>
        ))}
      </ul>
    </>
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

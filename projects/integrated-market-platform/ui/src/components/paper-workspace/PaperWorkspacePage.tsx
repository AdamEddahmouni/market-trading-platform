import { usePaperPortfolioQuery } from "../../api/hooks";
import { canUsePaperActions } from "../mode-session/modeAuthority";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import {
  WorkspaceObservability,
  type WorkspaceObservabilityProps,
  useWorkspaceContext,
} from "../workspace-shared/WorkspaceObservability";
import { WorkspaceModuleNav } from "../WorkspaceModuleNav";
import { PaperDecisionCockpit } from "./PaperDecisionCockpit";
import type { EvidenceQueryPhase } from "./buildPaperDecisionSnapshot";

type Props = WorkspaceObservabilityProps & {
  paperActionsPermitted: boolean;
  initialPaperOrderDraft?: PaperOrderDraft;
};

function evidencePhase(
  isLoading: boolean,
  isError: boolean,
  hasData: boolean,
  errorMessage?: string,
): { phase: EvidenceQueryPhase; message?: string } {
  if (isLoading) return { phase: "loading" };
  if (isError) return { phase: "error", message: errorMessage ?? "Workspace evidence request failed." };
  if (!hasData) return { phase: "empty" };
  return { phase: "ready" };
}

export function PaperWorkspacePage({
  paperActionsPermitted,
  initialPaperOrderDraft,
  instrumentId,
  ...observabilityProps
}: Props) {
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolio = portfolioQuery.data;
  const { dataLabel, healthState, evidence, evidenceQuery } = useWorkspaceContext(instrumentId);

  const paperActionsAvailable = canUsePaperActions(
    "PAPER",
    paperActionsPermitted,
    portfolio?.account,
  );

  const evidenceState = evidencePhase(
    evidenceQuery.isLoading,
    evidenceQuery.isError,
    Boolean(evidence),
    evidenceQuery.error instanceof Error ? evidenceQuery.error.message : undefined,
  );

  const portfolioPhase = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError
      ? "error"
      : "ready";

  return (
    <section className="page workspace-page paper-workspace-page unified-workstation">
      <header className="paper-workspace-header">
        <div>
          <span className="paper-eyebrow">Paper-only simulation</span>
          <h1>{instrumentId}</h1>
          <p className="workspace-health-line">
            {dataLabel} · {healthState}
            {evidence?.evidence_mix_summary && evidence.evidence_mix_summary !== "UNKNOWN"
              ? ` · ${evidence.evidence_mix_summary.replace(/_/g, " ")} evidence`
              : ""}
          </p>
          <p>
            Review lane handoff context, cross-lane evidence, and Paper risk before previewing a simulated
            order.
          </p>
        </div>
      </header>

      <WorkspaceModuleNav instrumentId={instrumentId} active="overview" />

      <PaperDecisionCockpit
        instrumentId={instrumentId}
        initialPaperOrderDraft={initialPaperOrderDraft}
        portfolio={portfolio}
        portfolioPhase={portfolioPhase}
        paperActionsAvailable={paperActionsAvailable}
        evidence={evidence}
        evidencePhase={evidenceState.phase}
        evidencePhaseMessage={evidenceState.message}
        dataLabel={dataLabel}
      />

      <WorkspaceObservability instrumentId={instrumentId} {...observabilityProps} />
    </section>
  );
}

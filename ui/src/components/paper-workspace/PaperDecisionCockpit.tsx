import { useState } from "react";
import type { PaperPortfolioResponse } from "../../api/client";
import type { WorkspaceEvidenceResponse } from "../../api/schemas";
import { ExecutionTracePanel } from "../paper/ExecutionTracePanel";
import { OrderTicket } from "../paper/OrderTicket";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import { buildPaperDecisionSnapshot, type EvidenceQueryPhase } from "./buildPaperDecisionSnapshot";
import { buildPaperHandoffModel } from "./buildPaperHandoffModel";
import { buildPaperRiskContext } from "./buildPaperRiskContext";
import { PaperHandoffPanel } from "./PaperHandoffPanel";
import { PaperDecisionSnapshotPanel } from "./PaperDecisionSnapshot";
import { PaperPreviewStatus } from "./PaperPreviewStatus";
import { PaperRiskContext } from "./PaperRiskContext";
import { PaperWhatMattersNow } from "./PaperWhatMattersNow";
import type { PaperPreviewPresentationState } from "./paperPreviewPresentation";

type Props = {
  instrumentId: string;
  initialPaperOrderDraft?: PaperOrderDraft;
  portfolio: PaperPortfolioResponse | undefined;
  portfolioPhase: "loading" | "ready" | "error";
  paperActionsAvailable: boolean;
  evidence: WorkspaceEvidenceResponse | undefined;
  evidencePhase: EvidenceQueryPhase;
  evidencePhaseMessage?: string;
  dataLabel?: string;
};

const DEFAULT_PREVIEW_STATE: PaperPreviewPresentationState = {
  status: "NOT_PREVIEWED",
  title: "Not previewed",
  message: "Preview against current Paper portfolio and risk state before submitting.",
  canSubmit: false,
};

export function PaperDecisionCockpit({
  instrumentId,
  initialPaperOrderDraft,
  portfolio,
  portfolioPhase,
  paperActionsAvailable,
  evidence,
  evidencePhase,
  evidencePhaseMessage,
  dataLabel,
}: Props) {
  const [traceIntentId, setTraceIntentId] = useState<string | undefined>();
  const [previewState, setPreviewState] = useState<PaperPreviewPresentationState>(DEFAULT_PREVIEW_STATE);

  const handoff = buildPaperHandoffModel(initialPaperOrderDraft, instrumentId);
  const snapshot = buildPaperDecisionSnapshot(
    evidence,
    evidencePhase,
    handoff.sourceLane,
    evidencePhaseMessage,
  );
  const riskContext = buildPaperRiskContext(
    portfolio,
    instrumentId,
    paperActionsAvailable,
    portfolioPhase,
  );
  const evidenceAsOf = evidence?.as_of_context?.as_of_time ?? null;

  return (
    <div className="paper-decision-cockpit">
      <div className="paper-cockpit-context">
        <PaperHandoffPanel handoff={handoff} evidenceAsOf={evidenceAsOf} />
        <PaperDecisionSnapshotPanel snapshot={snapshot} handoff={handoff} />
        <PaperWhatMattersNow
          instrumentId={instrumentId}
          lanes={evidence?.what_matters_now ?? []}
          mixSummary={evidence?.evidence_mix_summary}
          dataLabel={dataLabel}
          evidenceAsOf={evidenceAsOf}
          phase={evidencePhase}
          phaseMessage={evidencePhaseMessage}
        />
        <PaperRiskContext model={riskContext} />
      </div>

      <div className="paper-cockpit-action">
        <PaperPreviewStatus state={previewState} />
        {portfolio && paperActionsAvailable ? (
          <OrderTicket
            symbol={instrumentId}
            initialDraft={initialPaperOrderDraft}
            executionAuthority={portfolio.account.execution_authority}
            executionMode={portfolio.account.execution_mode}
            dataMode={portfolio.account.data_mode}
            maxOrderShares={portfolio.risk.limits.max_order_shares}
            showLaneBanner={false}
            onPreviewStateChange={setPreviewState}
            onSubmitted={(intentId) => {
              if (intentId) setTraceIntentId(intentId);
            }}
          />
        ) : portfolio ? (
          <aside className="panel mode-restriction-note" role="note">
            <strong>Paper authority unavailable.</strong>
            <p>Order and paper-session controls are unavailable for this context. Decision context remains readable.</p>
          </aside>
        ) : portfolioPhase === "loading" ? (
          <aside className="panel mode-restriction-note" role="status">
            <p>Loading Paper portfolio context…</p>
          </aside>
        ) : null}
        {paperActionsAvailable && traceIntentId ? (
          <ExecutionTracePanel intentId={traceIntentId} onClose={() => setTraceIntentId(undefined)} />
        ) : null}
      </div>
    </div>
  );
}

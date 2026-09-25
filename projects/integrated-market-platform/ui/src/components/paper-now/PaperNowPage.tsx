import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { ApiRequestError, formatApiRequestError } from "../../api/errors";
import { usePreviewPaperOrderMutation } from "../../api/hooks";
import { useOpportunitiesSummaryQuery, useOpportunityAckMutation } from "../../api/opportunityClient";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import { resolveSemanticState } from "../../state/semanticState";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { StatePill } from "../imp-ui/StatePill";
import { PaperCandidateQueue } from "./PaperCandidateQueue";
import { PaperExceptionsPanel } from "./PaperExceptionsPanel";
import { PaperPreviewComposer } from "./PaperPreviewComposer";
import { PaperRiskRibbon } from "./PaperRiskRibbon";
import { nextPaperCandidateId } from "./paperDashboardViewModel";
import { ImpOverviewBoard } from "../imp-product/ImpOverviewBoard";
import { overviewDecisionKpis } from "../imp-product/impOverviewMetrics";
import { buildPaperOrderRequest, createAttentionPaperOrderDraft, createPaperOrderDraft, createPaperPreviewAttemptKey, paperOrderDraftFingerprint, type PaperOrderDraft, type PaperOrderSide, attentionSourceContextFromItem } from "./paperOrderDraft";
import type { NowDeskVariant } from "../now/nowDeskVariant";

export type PaperNowPageProps = {
  items: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  portfolio?: PaperPortfolioResponse;
  portfolioState: "loading" | "ready" | "error";
  paperActionsPermitted: boolean;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  /** Retries the shell-owned attention query (invalidation flows from App). */
  onAttentionRetry?: () => void;
  desk?: NowDeskVariant;
};

type ConfirmedPreview = { fingerprint: string; value: PaperOrderPreviewResponse["preview"] };

export function PaperNowPage({ items, attentionState, portfolio, portfolioState, paperActionsPermitted, onWhy, onExplain, onInspect, onAttentionRetry, desk = "overview" }: PaperNowPageProps) {
  const navigate = useNavigate();
  const opportunitiesQuery = useOpportunitiesSummaryQuery(true);
  const opportunityState = opportunitiesQuery.isLoading
    ? "loading"
    : opportunitiesQuery.isError || !opportunitiesQuery.data
      ? "error"
      : "ready";
  const opportunityItems = opportunitiesQuery.data?.items ?? [];
  const [selectedAttentionId, setSelectedAttentionId] = useState<string | null>(null);
  const replayContext = [portfolio?.account.data_mode, portfolio?.as_of_context.data_mode].some(
    (mode) => mode === "FIXTURE_REPLAY" || mode === "CONTROLLED_REPLAY",
  );
  const [side, setSide] = useState<PaperOrderSide | null>(null);
  const [quantityText, setQuantityText] = useState("");
  const [confirmedPreview, setConfirmedPreview] = useState<ConfirmedPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewGeneration = useRef(0);
  const previewMutation = usePreviewPaperOrderMutation();
  const opportunityAck = useOpportunityAckMutation();

  useEffect(() => {
    if (portfolioState !== "ready" || replayContext) {
      if (selectedAttentionId && !items.some((item) => item.attention_id === selectedAttentionId)) {
        previewGeneration.current += 1;
        setConfirmedPreview(null);
        setPreviewError(null);
        setSelectedAttentionId(null);
      }
      return;
    }
    const next = nextPaperCandidateId(items, selectedAttentionId);
    if (next !== selectedAttentionId) {
      previewGeneration.current += 1;
      setConfirmedPreview(null);
      setPreviewError(null);
      setSelectedAttentionId(next);
    }
  }, [items, portfolioState, replayContext, selectedAttentionId]);
  const selected = items.find((item) => item.attention_id === selectedAttentionId && item.instrument_id?.trim()) ?? null;
  const quantity = /^\d+$/.test(quantityText) ? Number(quantityText) : null;
  const authorized = Boolean(paperActionsPermitted && portfolio && portfolio.account.execution_mode === "INTERNAL_SIMULATION" && portfolio.account.execution_authority === "PAPER_ONLY");
  const draft = selected?.instrument_id && portfolio ? createPaperOrderDraft({
    instrumentId: selected.instrument_id,
    side,
    quantity,
    maxOrderShares: portfolio.risk.limits.max_order_shares,
    sourceAttentionId: selected.attention_id,
    sourceContext: attentionSourceContextFromItem(selected),
  }) : null;
  const canOpenWorkspace = Boolean(authorized && portfolioState === "ready" && draft);
  const signalsDesk = desk === "signals";

  useEffect(() => {
    if (authorized && portfolioState === "ready") return;
    previewGeneration.current += 1;
    setConfirmedPreview(null);
    setPreviewError(null);
  }, [authorized, portfolioState]);

  function invalidatePreview() { previewGeneration.current += 1; setConfirmedPreview(null); setPreviewError(null); }
  async function previewDraft() {
    if (!draft) return;
    const generation = ++previewGeneration.current;
    const requestFingerprint = paperOrderDraftFingerprint(draft);
    setPreviewError(null); setConfirmedPreview(null);
    try {
      const response = await previewMutation.mutateAsync(buildPaperOrderRequest(draft, createPaperPreviewAttemptKey("paper-now")));
      if (previewGeneration.current === generation) setConfirmedPreview({ fingerprint: requestFingerprint, value: response.preview });
    } catch (error) {
      if (previewGeneration.current === generation) setPreviewError(error instanceof ApiRequestError ? formatApiRequestError(error) : "Preview failed. Retry when ready.");
    }
  }

  function openAttentionWorkspace(item: AttentionItem) {
    const draft = createAttentionPaperOrderDraft(item);
    if (draft) {
      navigate(workspacePathForInstrument(draft.instrumentId), { state: draft });
      return;
    }
    if (item.instrument_id) navigate(workspacePathForInstrument(item.instrument_id));
  }

  function continueToWorkspace(draft: PaperOrderDraft) {
    navigate(workspacePathForInstrument(draft.instrumentId), { state: draft });
  }

  const disabledReason = portfolioState === "loading" ? "Portfolio limits are loading." : portfolioState === "error" || !portfolio ? "Portfolio limits are unavailable." : !selected ? "Select an instrument-backed candidate." : !authorized ? "Paper authority is unavailable. Manage the simulation session in Portfolio." : !draft ? `Choose Buy or Sell and enter 1–${portfolio.risk.limits.max_order_shares} shares.` : undefined;

  const kpiCells = overviewDecisionKpis({
    opportunityState,
    feedStatus: opportunitiesQuery.data?.feed_status,
    unreadyReason: opportunitiesQuery.data?.unready_reason,
    opportunityItems,
    attentionState,
    attentionItems: items,
  });

  function openOpportunityWorkspace(item: AttentionItem) {
    openAttentionWorkspace(item);
  }

  const header = (
    <header className="paper-now-header">
      <div>
        <span className="paper-eyebrow">Paper-only simulation</span>
        <h1>{signalsDesk ? "Signals desk" : "Paper Command"}</h1>
        <p>
          {signalsDesk
            ? "Attention queue and reason codes for Paper simulation. Ranked opportunities and drafting stay on Overview; submit only from workspace."
            : "Review portfolio risk, draft intent, then revalidate in the instrument workspace before simulated submission."}
        </p>
      </div>
      <dl>
        <div>
          <dt>Account</dt>
          <dd>
            {portfolio?.account.paper_account_id ? (
              <CopyableIdentifier value={portfolio.account.paper_account_id} />
            ) : (
              "Unavailable"
            )}
          </dd>
        </div>
        <div>
          <dt>Session</dt>
          <dd>
            {portfolio?.account.session_id ? (
              <CopyableIdentifier value={portfolio.account.session_id} />
            ) : (
              "Unavailable"
            )}
          </dd>
        </div>
        <div>
          <dt>Execution</dt>
          <dd>
            {portfolio?.account.execution_mode
              ? resolveSemanticState("executionAuthority", portfolio.account.execution_mode).label
              : "Unavailable"}
          </dd>
        </div>
        <div>
          <dt>Authority</dt>
          <dd>
            {portfolio?.account.execution_authority ? (
              <StatePill
                tone={resolveSemanticState("executionAuthority", portfolio.account.execution_authority).tone}
                label={resolveSemanticState("executionAuthority", portfolio.account.execution_authority).label}
                raw={portfolio.account.execution_authority}
                size="sm"
              />
            ) : (
              "Unavailable"
            )}
          </dd>
        </div>
        <div>
          <dt>Data health</dt>
          <dd>
            {portfolio?.data_health.state ? (
              <StatePill
                tone={resolveSemanticState("dataHealth", portfolio.data_health.state).tone}
                label={resolveSemanticState("dataHealth", portfolio.data_health.state).label}
                raw={portfolio.data_health.state}
                size="sm"
              />
            ) : (
              "Unavailable"
            )}
          </dd>
        </div>
      </dl>
    </header>
  );

  const decisionGrid = (
    <div className="paper-decision-grid">
      <PaperCandidateQueue
        items={items}
        state={attentionState}
        selectedAttentionId={selectedAttentionId}
        onSelect={(id) => {
          invalidatePreview();
          setSelectedAttentionId(id);
        }}
        onWhy={onWhy}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={openAttentionWorkspace}
        onRetry={onAttentionRetry}
      />
      {!signalsDesk ? (
        <PaperPreviewComposer
          instrumentId={selected?.instrument_id ?? null}
          side={side}
          quantityText={quantityText}
          maxOrderShares={portfolio?.risk.limits.max_order_shares}
          disabledReason={disabledReason}
          pending={previewMutation.isPending}
          error={previewError}
          preview={confirmedPreview?.value ?? null}
          canOpenWorkspace={canOpenWorkspace}
          onSideChange={(value) => {
            invalidatePreview();
            setSide(value);
          }}
          onQuantityChange={(value) => {
            invalidatePreview();
            setQuantityText(value);
          }}
          onPreview={() => {
            void previewDraft();
          }}
          onOpenWorkspace={() => {
            if (draft && canOpenWorkspace) continueToWorkspace(draft);
          }}
        />
      ) : null}
      <PaperExceptionsPanel portfolio={portfolio} state={portfolioState} />
    </div>
  );

  return (
    <section className={`page paper-now-page${signalsDesk ? " paper-signals-desk" : ""}`}>
      {header}
      {signalsDesk ? (
        <>
          <PaperRiskRibbon portfolio={portfolio} state={portfolioState} />
          {decisionGrid}
        </>
      ) : (
      <ImpOverviewBoard
        kpiCells={kpiCells}
        attentionItems={items}
        attentionState={attentionState}
        opportunityItems={opportunityItems}
        opportunityState={opportunityState}
        feedStatus={opportunitiesQuery.data?.feed_status}
        unreadyReason={opportunitiesQuery.data?.unready_reason}
        nextAction={opportunitiesQuery.data?.next_action}
        mode="PAPER"
        paperAccountId={portfolio?.account.paper_account_id}
        defaultQueueFilter="ranked"
        onOpportunityRetry={() => void opportunitiesQuery.refetch()}
        onAttentionRetry={onAttentionRetry}
        onWhy={onWhy}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={openOpportunityWorkspace}
        onAck={(row, action) => {
          opportunityAck.mutate({ rowId: row.opportunity_id || row.summary_id, action });
        }}
      >
      <PaperRiskRibbon portfolio={portfolio} state={portfolioState} />
      {decisionGrid}
      </ImpOverviewBoard>
      )}
    </section>
  );
}

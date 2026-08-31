import { useEffect, useRef, useState } from "react";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { ApiRequestError } from "../../api/fetchJson";
import { usePreviewPaperOrderMutation } from "../../api/hooks";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import { PaperCandidateQueue } from "./PaperCandidateQueue";
import { PaperExceptionsPanel } from "./PaperExceptionsPanel";
import { PaperPreviewComposer } from "./PaperPreviewComposer";
import { PaperRiskRibbon } from "./PaperRiskRibbon";
import { nextPaperCandidateId } from "./paperDashboardViewModel";
import { buildPaperOrderRequest, createPaperOrderDraft, createPaperPreviewAttemptKey, paperOrderDraftFingerprint, type PaperOrderDraft, type PaperOrderSide } from "./paperOrderDraft";

export type PaperNowPageProps = {
  items: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  portfolio?: PaperPortfolioResponse;
  portfolioState: "loading" | "ready" | "error";
  paperActionsPermitted: boolean;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onContinue: (draft: PaperOrderDraft) => void;
};

type ConfirmedPreview = { fingerprint: string; value: PaperOrderPreviewResponse["preview"] };

export function PaperNowPage({ items, attentionState, portfolio, portfolioState, paperActionsPermitted, onWhy, onExplain, onInspect, onOpenWorkspace, onContinue }: PaperNowPageProps) {
  const [selectedAttentionId, setSelectedAttentionId] = useState<string | null>(() => nextPaperCandidateId(items, null));
  const [side, setSide] = useState<PaperOrderSide | null>(null);
  const [quantityText, setQuantityText] = useState("");
  const [confirmedPreview, setConfirmedPreview] = useState<ConfirmedPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const currentFingerprintRef = useRef("");
  const previewMutation = usePreviewPaperOrderMutation();

  useEffect(() => {
    const next = nextPaperCandidateId(items, selectedAttentionId);
    if (next !== selectedAttentionId) {
      currentFingerprintRef.current = "";
      setConfirmedPreview(null);
      setPreviewError(null);
      setSelectedAttentionId(next);
    }
  }, [items, selectedAttentionId]);
  const selected = items.find((item) => item.attention_id === selectedAttentionId && item.instrument_id?.trim()) ?? null;
  const quantity = /^\d+$/.test(quantityText) ? Number(quantityText) : null;
  const authorized = Boolean(paperActionsPermitted && portfolio && portfolio.account.execution_mode === "INTERNAL_SIMULATION" && portfolio.account.execution_authority === "PAPER_ONLY");
  const draft = selected?.instrument_id && portfolio ? createPaperOrderDraft({ instrumentId: selected.instrument_id, side, quantity, maxOrderShares: portfolio.risk.limits.max_order_shares, sourceAttentionId: selected.attention_id }) : null;
  const fingerprint = draft ? paperOrderDraftFingerprint(draft) : "";
  currentFingerprintRef.current = fingerprint;
  const canContinue = Boolean(draft && confirmedPreview?.fingerprint === fingerprint && confirmedPreview.value.risk_status === "PASS");

  function invalidatePreview() { currentFingerprintRef.current = ""; setConfirmedPreview(null); setPreviewError(null); }
  async function previewDraft() {
    if (!draft) return;
    const requestFingerprint = paperOrderDraftFingerprint(draft);
    setPreviewError(null); setConfirmedPreview(null);
    try {
      const response = await previewMutation.mutateAsync(buildPaperOrderRequest(draft, createPaperPreviewAttemptKey("paper-now")));
      if (currentFingerprintRef.current === requestFingerprint) setConfirmedPreview({ fingerprint: requestFingerprint, value: response.preview });
    } catch (error) {
      if (currentFingerprintRef.current === requestFingerprint) setPreviewError(error instanceof ApiRequestError ? `${error.code}: ${error.message}` : "Preview failed. Retry when ready.");
    }
  }

  const disabledReason = portfolioState === "loading" ? "Portfolio limits are loading." : portfolioState === "error" || !portfolio ? "Portfolio limits are unavailable." : !selected ? "Select an instrument-backed candidate." : !authorized ? "Paper authority is unavailable. Manage the simulation session in Portfolio." : !draft ? `Choose Buy or Sell and enter 1–${portfolio.risk.limits.max_order_shares} shares.` : undefined;

  return (
    <section className="page paper-now-page">
      <header className="paper-now-header"><div><span className="paper-eyebrow">Paper-only simulation</span><h1>Paper Command</h1><p>Review portfolio risk, validate a deliberate draft, then revalidate in the instrument workspace before simulated submission.</p></div><dl><div><dt>Session</dt><dd>{portfolio?.account.session_id ?? "Unavailable"}</dd></div><div><dt>Execution</dt><dd>{portfolio?.account.execution_mode ?? "Unavailable"}</dd></div><div><dt>Authority</dt><dd>{portfolio?.account.execution_authority ?? "Unavailable"}</dd></div><div><dt>Data health</dt><dd>{portfolio?.data_health.state ?? "Unavailable"}</dd></div></dl></header>
      <PaperRiskRibbon portfolio={portfolio} state={portfolioState} />
      <div className="paper-decision-grid">
        <PaperCandidateQueue items={items} state={attentionState} selectedAttentionId={selectedAttentionId} onSelect={(id) => { invalidatePreview(); setSelectedAttentionId(id); }} onWhy={onWhy} onExplain={onExplain} onInspect={onInspect} onOpenWorkspace={onOpenWorkspace} />
        <PaperPreviewComposer instrumentId={selected?.instrument_id ?? null} side={side} quantityText={quantityText} maxOrderShares={portfolio?.risk.limits.max_order_shares} disabledReason={disabledReason} pending={previewMutation.isPending} error={previewError} preview={confirmedPreview?.value ?? null} canContinue={canContinue} onSideChange={(value) => { invalidatePreview(); setSide(value); }} onQuantityChange={(value) => { invalidatePreview(); setQuantityText(value); }} onPreview={() => { void previewDraft(); }} onContinue={() => { if (draft && canContinue) onContinue(draft); }} />
        <PaperExceptionsPanel portfolio={portfolio} state={portfolioState} />
      </div>
    </section>
  );
}

import { useEffect, useRef, useState } from "react";
import { ApiRequestError } from "../../api/fetchJson";
import {
  useOpenPaperSessionMutation,
  usePaperPortfolioQuery,
  usePreviewPaperOrderMutation,
  useSubmitPaperOrderMutation,
} from "../../api/hooks";
import type { PaperOrderPreviewResponse, PaperOrderRequest } from "../../api/schemas";
import {
  buildPaperOrderRequest,
  createPaperOrderDraft,
  createPaperPreviewAttemptKey,
  formatPaperDraftSourceLabel,
  isLanePaperOrderDraft,
  isAttentionPaperOrderDraft,
  parseLaneProvenance,
  type PaperOrderDraft,
} from "../paper-now/paperOrderDraft";
import {
  derivePreviewPresentationState,
  type PaperPreviewPresentationState,
} from "../paper-workspace/paperPreviewPresentation";

type OrderTicketProps = {
  symbol: string | null;
  executionAuthority: string;
  executionMode: string;
  dataMode: string;
  maxOrderShares: number;
  initialDraft?: PaperOrderDraft;
  contextLanes?: Array<{ lane: string; relevance: string; summary: string }>;
  onSubmitted?: (intentId?: string) => void;
  onPreviewStateChange?: (state: PaperPreviewPresentationState) => void;
  showLaneBanner?: boolean;
};

export function OrderTicket({
  symbol,
  executionAuthority,
  executionMode,
  dataMode,
  maxOrderShares,
  initialDraft,
  contextLanes = [],
  onSubmitted,
  onPreviewStateChange,
  showLaneBanner = true,
}: OrderTicketProps) {
  const [side, setSide] = useState<"BUY" | "SELL">(() => initialDraft?.side ?? "BUY");
  const [quantity, setQuantity] = useState(() => initialDraft?.quantity ?? 1);
  const [explicitSymbol, setExplicitSymbol] = useState("");
  const [preview, setPreview] = useState<PaperOrderPreviewResponse["preview"] | null>(null);
  const [confirmedRequest, setConfirmedRequest] = useState<PaperOrderRequest | null>(null);
  const [previewOrigin, setPreviewOrigin] = useState<"manual" | "workspace" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const automaticPreviewAttempted = useRef(false);
  const previewGeneration = useRef(0);

  const previewMutation = usePreviewPaperOrderMutation();
  const submitMutation = useSubmitPaperOrderMutation();
  const sessionMutation = useOpenPaperSessionMutation();
  const portfolioQuery = usePaperPortfolioQuery();

  const authorized =
    (executionAuthority === "AUTHORIZED" || executionAuthority === "PAPER_ONLY") &&
    executionMode === "INTERNAL_SIMULATION";
  const override = explicitSymbol.trim().toUpperCase();
  const ticketSymbol = override || symbol || "";
  const previewInstrument =
    preview?.intent?.instrument_id ||
    preview?.intent?.instrument?.instrument_id ||
    preview?.instrument?.instrument_id ||
    ticketSymbol;
  const canPreview = Boolean(ticketSymbol) && quantity > 0 && quantity <= maxOrderShares;
  const confirmedRequestIsCurrent = Boolean(
    confirmedRequest &&
    confirmedRequest.instrument_id === ticketSymbol &&
    confirmedRequest.side === side &&
    confirmedRequest.quantity === quantity &&
    confirmedRequest.order_type === "MARKET" &&
    quantity > 0 &&
    quantity <= maxOrderShares,
  );

  function invalidatePreview() {
    previewGeneration.current += 1;
    setPreview(null);
    setConfirmedRequest(null);
    setPreviewOrigin(null);
    setError(null);
  }

  useEffect(() => {
    if (confirmedRequest && !confirmedRequestIsCurrent) invalidatePreview();
  }, [confirmedRequest, confirmedRequestIsCurrent]);

  useEffect(() => {
    onPreviewStateChange?.(
      derivePreviewPresentationState({
        authorized,
        preview,
        confirmedRequest,
        confirmedRequestIsCurrent,
        previewMutationPending: previewMutation.isPending,
        error,
        previewOrigin,
      }),
    );
  }, [
    authorized,
    preview,
    confirmedRequest,
    confirmedRequestIsCurrent,
    previewMutation.isPending,
    error,
    previewOrigin,
    onPreviewStateChange,
  ]);

  async function performPreview(origin: "manual" | "workspace") {
    const currentDraft = createPaperOrderDraft({
      instrumentId: ticketSymbol,
      side,
      quantity,
      maxOrderShares,
      sourceAttentionId: initialDraft?.sourceAttentionId,
      sourceContext: initialDraft?.sourceContext,
    });
    if (!currentDraft) {
      setError(ticketSymbol ? "ENTER A VALID QUANTITY" : "SELECT AN INSTRUMENT");
      return;
    }
    const generation = ++previewGeneration.current;
    const request = buildPaperOrderRequest(currentDraft, createPaperPreviewAttemptKey("workspace-ticket"));
    setError(null);
    setPreview(null);
    setConfirmedRequest(null);
    setPreviewOrigin(null);
    try {
      const response = await previewMutation.mutateAsync(request);
      if (previewGeneration.current !== generation) return;
      setPreview(response.preview);
      setConfirmedRequest(request);
      setPreviewOrigin(origin);
    } catch (err) {
      if (previewGeneration.current !== generation) return;
      setError(err instanceof ApiRequestError ? `${err.code}: ${err.message}` : "Preview failed");
    }
  }

  useEffect(() => {
    if (!initialDraft || !authorized || automaticPreviewAttempted.current) return;
    if (!createPaperOrderDraft({ instrumentId: initialDraft.instrumentId, side: initialDraft.side, quantity: initialDraft.quantity, maxOrderShares, sourceAttentionId: initialDraft.sourceAttentionId, sourceContext: initialDraft.sourceContext })) return;
    automaticPreviewAttempted.current = true;
    void performPreview("workspace");
  }, [authorized, initialDraft, maxOrderShares]);

  async function handleSubmit() {
    if (!preview || preview.risk_status !== "PASS" || !confirmedRequest || !confirmedRequestIsCurrent) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await submitMutation.mutateAsync(confirmedRequest);
      onSubmitted?.(response.submission.intent_id);
      setPreview(null);
      setConfirmedRequest(null);
      setPreviewOrigin(null);
    } catch (err) {
      setError(err instanceof ApiRequestError ? `${err.code}: ${err.message}` : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpenSession() {
    setError(null);
    try {
      await sessionMutation.mutateAsync(ticketSymbol || undefined);
      await portfolioQuery.refetch();
    } catch (err) {
      setError(err instanceof ApiRequestError ? `${err.code}: ${err.message}` : "Session open failed");
    }
  }

  const laneProvenance = parseLaneProvenance(initialDraft?.sourceAttentionId);
  const fromLane = isLanePaperOrderDraft(initialDraft);
  const fromAttention = isAttentionPaperOrderDraft(initialDraft);
  const draftSourceLabel = formatPaperDraftSourceLabel(initialDraft);

  return (
    <section className="panel order-ticket-panel">
      <h2>Order ticket</h2>
      {fromLane && laneProvenance && showLaneBanner ? (
        <aside className="lane-draft-arrival-banner" role="note">
          <strong>Draft from {laneProvenance.label} lane</strong>
          <p>Placeholder values — edit and re-preview before submit.</p>
        </aside>
      ) : null}
      {fromAttention && draftSourceLabel && showLaneBanner ? (
        <aside className="attention-draft-arrival-banner" role="note">
          <strong>Draft source: {draftSourceLabel}</strong>
          <p>Placeholder values — edit and re-preview before submit.</p>
        </aside>
      ) : null}
      <p className="simulation-banner">
        DATA: {dataMode.replace(/_/g, " ")} · EXEC: {executionMode.replace(/_/g, " ")} · AUTH:{" "}
        {executionAuthority === "AUTHORIZED" || executionAuthority === "PAPER_ONLY"
          ? "PAPER ONLY"
          : executionAuthority}
      </p>

      {!authorized ? (
        <div className="capability-panel unavailable">
          <p>Paper execution is gated. Set IMP_PAPER_EXECUTION=1 and open an internal simulation session.</p>
          <button type="button" onClick={() => void handleOpenSession()} disabled={sessionMutation.isPending}>
            Open simulation session
          </button>
        </div>
      ) : null}

      <dl className="metric-list">
        <div>
          <dt>Instrument</dt>
          <dd>{ticketSymbol || "SELECT AN INSTRUMENT"}</dd>
        </div>
        <div>
          <dt>Order type</dt>
          <dd>MARKET</dd>
        </div>
      </dl>
      <label className="order-ticket-symbol">
        Symbol override
        <input
          aria-label="Order ticket symbol"
          value={explicitSymbol}
          onChange={(event) => {
            invalidatePreview();
            setExplicitSymbol(event.target.value.toUpperCase());
          }}
          placeholder={symbol ?? "SELECT AN INSTRUMENT"}
        />
      </label>
      {preview && previewInstrument && symbol && previewInstrument !== symbol ? (
        <p className="muted">Preview locked to {previewInstrument}; submit will not switch with workspace.</p>
      ) : null}

      <div className="order-ticket-controls">
        <div className="side-toggle" role="group" aria-label="Order side">
          <button
            type="button"
            className={side === "BUY" ? "active long" : ""}
            aria-pressed={side === "BUY"}
            onClick={() => {
              invalidatePreview();
              setSide("BUY");
            }}
          >
            BUY
          </button>
          <button
            type="button"
            className={side === "SELL" ? "active short" : ""}
            aria-pressed={side === "SELL"}
            onClick={() => {
              invalidatePreview();
              setSide("SELL");
            }}
          >
            SELL
          </button>
        </div>
        <label className="order-ticket-quantity">
          Quantity
          <input
            type="number"
            min={1}
            max={maxOrderShares}
            value={quantity}
            onChange={(event) => {
              invalidatePreview();
              setQuantity(Number(event.target.value));
            }}
          />
        </label>
      </div>

      {contextLanes.length > 0 ? (
        <div className="ticket-context-lanes">
          <h3>Relevant context</h3>
          <ul>
            {contextLanes.map((row) => (
              <li key={row.lane}>
                {row.lane} · {row.relevance} · {row.summary}
              </li>
            ))}
          </ul>
          <p className="muted">Informational only — does not authorize execution.</p>
        </div>
      ) : null}

      <div className="order-ticket-actions">
        <button type="button" onClick={() => void performPreview("manual")} disabled={!canPreview || previewMutation.isPending}>
          Preview
        </button>
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={!authorized || !preview || preview.risk_status !== "PASS" || !confirmedRequestIsCurrent || submitting}
        >
          Submit
        </button>
      </div>

      {error ? <p className="order-ticket-error">{error}</p> : null}

      {preview ? (
        <div className={`order-preview ${preview.risk_status === "PASS" ? "pass" : "blocked"}`}>
          <h3>{previewOrigin === "workspace" ? "Revalidated in workspace" : "Preview"}</h3>
          <p>
            Risk: <strong>{preview.risk_status}</strong> ({preview.decision})
          </p>
          {preview.reason_codes && preview.reason_codes.length > 0 ? (
            <p>Reasons: {preview.reason_codes.join(", ")}</p>
          ) : null}
          <p>Projected position: {preview.projected_position_shares ?? "UNAVAILABLE"} sh</p>
          <p>Quality: {preview.quality_state ?? "UNKNOWN"}</p>
          {preview.fill_preview_available === false ? (
            <p className="muted">
              {preview.quality_state === "WAITING_FOR_ELIGIBLE_LIVE_EVENT"
                ? "WAITING FOR ELIGIBLE LIVE DATA — risk approved; waiting for fresh post-intent market evidence for internal simulation."
                : "No executable bar after replay cursor — scrub replay forward."}
            </p>
          ) : null}
          {preview.order_preview ? <p>Order state preview: {String(preview.order_preview.state)}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

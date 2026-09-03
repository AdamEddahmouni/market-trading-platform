import { useMemo, useState } from "react";
import { ApiRequestError } from "../../api/fetchJson";
import {
  useOpenPaperSessionMutation,
  usePaperPortfolioQuery,
  usePreviewPaperOrderMutation,
  useSubmitPaperOrderMutation,
} from "../../api/hooks";
import type { PaperOrderPreviewResponse } from "../../api/schemas";

type OrderTicketProps = {
  symbol: string | null;
  executionAuthority: string;
  executionMode: string;
  dataMode: string;
  maxOrderShares: number;
  contextLanes?: Array<{ lane: string; relevance: string; summary: string }>;
  onSubmitted?: (intentId?: string) => void;
};

export function OrderTicket({
  symbol,
  executionAuthority,
  executionMode,
  dataMode,
  maxOrderShares,
  contextLanes = [],
  onSubmitted,
}: OrderTicketProps) {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState(1);
  const [explicitSymbol, setExplicitSymbol] = useState("");
  const [preview, setPreview] = useState<PaperOrderPreviewResponse["preview"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const previewMutation = usePreviewPaperOrderMutation();
  const submitMutation = useSubmitPaperOrderMutation();
  const sessionMutation = useOpenPaperSessionMutation();
  const portfolioQuery = usePaperPortfolioQuery();

  const idempotencyKey = useMemo(
    () => `ticket-${side}-${quantity}-${Date.now()}`,
    [side, quantity, preview],
  );

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

  async function handlePreview() {
    if (!ticketSymbol) {
      setError("SELECT AN INSTRUMENT");
      return;
    }
    setError(null);
    setPreview(null);
    try {
      const response = await previewMutation.mutateAsync({
        side,
        quantity,
        order_type: "MARKET",
        instrument_id: ticketSymbol,
        symbol: ticketSymbol,
        client_order_id: idempotencyKey,
        idempotency_key: idempotencyKey,
      });
      setPreview(response.preview);
    } catch (err) {
      setError(err instanceof ApiRequestError ? `${err.code}: ${err.message}` : "Preview failed");
    }
  }

  async function handleSubmit() {
    if (!preview || preview.risk_status !== "PASS") return;
    if (!previewInstrument) {
      setError("SELECT AN INSTRUMENT");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await submitMutation.mutateAsync({
        side,
        quantity,
        order_type: "MARKET",
        instrument_id: previewInstrument,
        symbol: previewInstrument,
        client_order_id: idempotencyKey,
        idempotency_key: idempotencyKey,
      });
      onSubmitted?.(response.submission.intent_id);
      setPreview(null);
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

  return (
    <section className="panel order-ticket-panel">
      <h2>Order ticket</h2>
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
          onChange={(event) => setExplicitSymbol(event.target.value.toUpperCase())}
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
            onClick={() => setSide("BUY")}
          >
            BUY
          </button>
          <button
            type="button"
            className={side === "SELL" ? "active short" : ""}
            onClick={() => setSide("SELL")}
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
            onChange={(event) => setQuantity(Number(event.target.value))}
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
        <button type="button" onClick={() => void handlePreview()} disabled={!canPreview || previewMutation.isPending}>
          Preview
        </button>
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={!authorized || !preview || preview.risk_status !== "PASS" || submitting}
        >
          Submit
        </button>
      </div>

      {error ? <p className="order-ticket-error">{error}</p> : null}

      {preview ? (
        <div className={`order-preview ${preview.risk_status === "PASS" ? "pass" : "blocked"}`}>
          <h3>Preview</h3>
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

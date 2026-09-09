import { useState } from "react";
import { ApiRequestError } from "../../api/fetchJson";
import { usePaperPortfolioQuery, usePreviewPaperOrderMutation } from "../../api/hooks";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import type { Mode } from "../mode-session/types";

type Props = {
  mode: Mode;
  instrumentId: string;
  quantityUnitLabel?: string;
  paperActionsAvailable: boolean;
  disabledReason?: string | null;
};

export function DerivativePaperPreviewPanel({
  mode,
  instrumentId,
  quantityUnitLabel = "CONTRACTS",
  paperActionsAvailable,
  disabledReason,
}: Props) {
  const [quantityText, setQuantityText] = useState("1");
  const [preview, setPreview] = useState<PaperOrderPreviewResponse["preview"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previewMutation = usePreviewPaperOrderMutation();
  const portfolioQuery = usePaperPortfolioQuery("PAPER");

  if (mode === "LIVE") {
    return <p className="workspace-hint">Live mode is observational only — execution unavailable.</p>;
  }

  if (!paperActionsAvailable) {
    return disabledReason ? <p className="muted">{disabledReason}</p> : null;
  }

  async function runPreview() {
    const quantity = Number(quantityText);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setError("Quantity must be a positive number of contracts.");
      setPreview(null);
      return;
    }
    setError(null);
    try {
      const response = await previewMutation.mutateAsync({
        side: "BUY",
        quantity,
        instrument_id: instrumentId,
        order_type: "MARKET",
      });
      setPreview(response.preview);
    } catch (err) {
      setPreview(null);
      setError(err instanceof ApiRequestError ? err.message : err instanceof Error ? err.message : "Preview failed");
    }
  }

  return (
    <section className="paper-derivative-preview" aria-label="Paper preview">
      <header>
        <h3>Paper preview</h3>
        <p>Backend canonical preview — submit remains on Workspace order ticket.</p>
      </header>
      <label>
        Quantity ({quantityUnitLabel})
        <input
          type="number"
          min={1}
          value={quantityText}
          onChange={(event) => {
            setQuantityText(event.target.value);
            setPreview(null);
            setError(null);
          }}
        />
      </label>
      <button type="button" className="primary" disabled={previewMutation.isPending} onClick={() => void runPreview()}>
        {previewMutation.isPending ? "Previewing…" : "Preview Paper order"}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {preview ? (
        <div className="paper-preview-result">
          <p>
            Risk <strong>{preview.risk_status}</strong> · {preview.decision}
          </p>
          {preview.reason_codes?.length ? <p>Reasons: {preview.reason_codes.join(", ")}</p> : null}
          {preview.projected_position_shares !== undefined ? (
            <p>Projected position: {preview.projected_position_shares}</p>
          ) : null}
          {portfolioQuery.data?.account.paper_account_id ? (
            <p className="muted">Account {portfolioQuery.data.account.paper_account_id}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

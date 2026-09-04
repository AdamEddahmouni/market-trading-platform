import { useEffect, useRef } from "react";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import type { PaperOrderSide } from "./paperOrderDraft";

type Props = {
  instrumentId: string | null;
  side: PaperOrderSide | null;
  quantityText: string;
  maxOrderShares?: number;
  disabledReason?: string;
  pending: boolean;
  error: string | null;
  preview: PaperOrderPreviewResponse["preview"] | null;
  canContinue: boolean;
  onSideChange: (side: PaperOrderSide) => void;
  onQuantityChange: (value: string) => void;
  onPreview: () => void;
  onContinue: () => void;
};

function optionalRows(preview: PaperOrderPreviewResponse["preview"]) {
  const rows = [
    ["Current position", preview.current_position_shares],
    ["Projected position", preview.projected_position_shares],
    ["Current gross exposure", preview.current_gross_exposure_shares],
    ["Estimated gross exposure", preview.estimated_gross_exposure_shares],
    ["Current net exposure", preview.current_net_exposure_shares],
    ["Estimated net exposure", preview.estimated_net_exposure_shares],
  ] as const;
  return rows.filter((row) => row[1] !== undefined);
}

export function PaperPreviewComposer({ instrumentId, side, quantityText, maxOrderShares, disabledReason, pending, error, preview, canContinue, onSideChange, onQuantityChange, onPreview, onContinue }: Props) {
  const resultHeadingRef = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { if (preview) resultHeadingRef.current?.focus(); }, [preview]);
  return (
    <section className="paper-panel paper-preview-panel" aria-label="Order preview">
      <header><div><span className="paper-eyebrow">Review and preview</span><h2>{instrumentId ?? "No candidate selected"}</h2></div><code>MARKET</code></header>
      <p>Choose direction and size. Preview validates current Paper risk; it does not authorize submission.</p>
      <fieldset disabled={!instrumentId || pending}><legend>Order side</legend><label><input type="radio" name="paper-side" checked={side === "BUY"} onChange={() => onSideChange("BUY")} />BUY</label><label><input type="radio" name="paper-side" checked={side === "SELL"} onChange={() => onSideChange("SELL")} />SELL</label></fieldset>
      <label className="paper-quantity">Quantity<input type="number" inputMode="numeric" min={1} max={maxOrderShares} value={quantityText} onChange={(event) => onQuantityChange(event.target.value)} disabled={!instrumentId || pending} /></label>
      <dl className="paper-order-fixed"><div><dt>Order type</dt><dd>MARKET</dd></div>{maxOrderShares !== undefined ? <div><dt>Account limit</dt><dd>{maxOrderShares} sh</dd></div> : null}</dl>
      {disabledReason ? <p id="paper-preview-disabled" className="muted">{disabledReason}</p> : null}
      <button type="button" className="primary" onClick={onPreview} disabled={Boolean(disabledReason) || pending} aria-describedby={disabledReason ? "paper-preview-disabled" : undefined}>{error ? "Retry preview" : "Preview order"}</button>
      {pending ? <p role="status">Validating draft…</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {preview ? (
        <div className={`paper-preview-result ${preview.risk_status === "PASS" ? "pass" : "blocked"}`}>
          <h3 ref={resultHeadingRef} tabIndex={-1}>Preview result</h3>
          <p>Risk <strong>{preview.risk_status}</strong> · {preview.decision}</p>
          {preview.reason_codes?.length ? <p>Reasons: {preview.reason_codes.join(", ")}</p> : null}
          {optionalRows(preview).length ? <dl>{optionalRows(preview).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value} sh</dd></div>)}</dl> : null}
          {preview.risk_limits ? <p>Limits: order {preview.risk_limits.max_order_shares} · position {preview.risk_limits.max_position_shares} · open orders {preview.risk_limits.max_open_orders}</p> : null}
          {preview.risk_utilization ? <ul>{Object.entries(preview.risk_utilization).map(([key, value]) => <li key={key}><code>{key}</code> {typeof value === "object" ? JSON.stringify(value) : String(value)}</li>)}</ul> : null}
          <p>Quality {preview.quality_state ?? "UNKNOWN"} · Fill preview {preview.fill_preview_available === undefined ? "UNKNOWN" : preview.fill_preview_available ? "AVAILABLE" : "UNAVAILABLE"}</p>
          {preview.execution_model ? <p>Model {preview.execution_model}{preview.execution_model_version ? ` · ${preview.execution_model_version}` : ""}</p> : null}
          {canContinue ? <button type="button" className="primary" onClick={onContinue}>Open workspace and revalidate</button> : null}
        </div>
      ) : null}
    </section>
  );
}

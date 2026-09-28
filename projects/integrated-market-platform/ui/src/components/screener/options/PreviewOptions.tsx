import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ScreenerRow, ScreenerUniverse } from "../../../api/screener";
import { fetchScreenerOptions } from "../../../api/screenerOptions";
import { ago, contractLabel, count, etTime, expiry, hasChain, iv, OPTIONS_STATE_LABELS, ratio, snapshotAge, stateMessage } from "./optionsFormat";

/**
 * Rendered only while the Preview's Options tab is active, so row selection
 * alone never requests a chain. Arrowing through rows with the tab open waits
 * for the selection to settle before asking for one summary.
 */
export const PREVIEW_OPTIONS_SETTLE_MS = 400;

type Props = { row: ScreenerRow; universe: ScreenerUniverse; onOpenPanel: () => void };

export function PreviewOptions({ row, universe, onOpenPanel }: Props) {
  const id = row.instrument.instrument_id;
  const [settled, setSettled] = useState<string | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(id), PREVIEW_OPTIONS_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [id]);
  const snapshotId = row.snapshot_id ?? null;
  const query = useQuery({
    queryKey: ["screener-options", universe, settled, "summary", snapshotId],
    queryFn: ({ signal }) => fetchScreenerOptions(settled!, { universe, view: "summary", snapshotId, signal }),
    enabled: settled === id, staleTime: 30_000, refetchInterval: 60_000, retry: 1,
  });
  const data = query.data && query.data.instrument_id === id ? query.data : undefined;
  const open = <button type="button" className="screener-control" onClick={onOpenPanel}>Open Options Panel</button>;
  if (query.isError && !data) {
    return <div className="screener-preview-options"><p className="screener-preview-note" role="alert">Current option chain unavailable. <button type="button" onClick={() => void query.refetch()}>Retry</button></p></div>;
  }
  if (!data) return <div className="screener-preview-options"><p className="screener-preview-note" aria-live="polite">Loading {row.symbol} options…</p></div>;
  const age = snapshotAge(data, query.dataUpdatedAt);
  const source = <p className="screener-preview-meta">{data.provider?.label ?? "Provider"} · snapshot, not streaming · {OPTIONS_STATE_LABELS[data.state]}
    {data.clock ? ` · fetched ${etTime(data.clock.fetched_at)}${age != null ? ` (${ago(age)} ago)` : ""}` : ""}</p>;
  if (!hasChain(data.state) || !data.summary) {
    return <div className="screener-preview-options"><p className="screener-preview-note" role="status">{stateMessage(data)}</p>{source}</div>;
  }
  const summary = data.summary;
  const near = summary.nearest_strike;
  const top = summary.most_active[0];
  const nearestExpiry = data.expirations[0];
  return <div className="screener-preview-options">
    <h3>Options snapshot</h3>
    {data.state !== "CURRENT_SNAPSHOT" ? <p className="screener-preview-note" role="status">{stateMessage(data)}</p> : null}
    <dl className="screener-key-data">
      <div><dt>Nearest expiry</dt><dd>{expiry(summary.nearest_expiration, true)}{nearestExpiry ? ` · ${nearestExpiry.dte}d` : ""}</dd></div>
      <div><dt>Expiries</dt><dd>{count(summary.expirations)}</dd></div>
      <div><dt>Call volume</dt><dd>{count(summary.call_volume)}</dd></div>
      <div><dt>Put volume</dt><dd>{count(summary.put_volume)}</dd></div>
      <div title="Put volume ÷ call volume"><dt>P/C volume</dt><dd>{ratio(summary.put_call_volume_ratio)}</dd></div>
      <div title="Put open interest ÷ call open interest"><dt>P/C OI</dt><dd>{ratio(summary.put_call_oi_ratio)}</dd></div>
      <div><dt>Total OI</dt><dd>{count(summary.total_open_interest)}</dd></div>
      <div><dt>Contracts</dt><dd>{count(summary.contracts)}</dd></div>
      {near ? <div className="wide" title={`Listed strike closest to the underlying $${near.basis_price.toFixed(2)} in the nearest expiry; not an exact at-the-money claim`}>
        <dt>Nearest-strike IV ({near.strike})</dt><dd>C {iv(near.call_iv)} · P {iv(near.put_iv)}</dd></div> : null}
      {top ? <div className="wide" title="Highest observed volume among current contracts; volume may be opening or closing trades">
        <dt>Most active contract</dt><dd>{contractLabel(data.symbol, top)} · {count(top.volume)}{top.share_of_side_volume_pct != null ? ` · ${top.share_of_side_volume_pct.toFixed(1)}% of ${top.type === "CALL" ? "call" : "put"} volume` : ""}</dd></div> : null}
    </dl>
    {source}
    <p className="screener-preview-meta">Selected-instrument context only; it does not filter or rank the Screener.</p>
    <div className="screener-preview-options-actions">{open}</div>
  </div>;
}

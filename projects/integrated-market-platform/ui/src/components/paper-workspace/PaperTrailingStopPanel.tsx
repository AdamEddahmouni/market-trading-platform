import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { workspacePathForInstrument } from "../../api/instrumentIdentity";
import {
  configureSmaStop, evaluateSmaStop, smaStopConfig, smaStopEvaluation, smaStopHistory, smaStopStatus,
  type SmaStopConfig, type SmaStopEvaluation, type SmaStopEvent, type SmaStopStatus,
} from "../../api/paperRiskControl";
import { prepareAction } from "../../api/screenerAction";
import { buildPaperTrailingStopModel, formatStopPrice, formatStopTime } from "./buildPaperTrailingStopModel";
import { SmaStopEvaluationTable } from "./SmaStopEvaluationTable";

type Props = { instrumentId: string; paperActionsAvailable: boolean };

/** The existing explicit handoff: a draft for the Workspace ticket. Nothing is previewed or submitted here. */
function PrepareExit({ decisionId, disabled, onError }: { decisionId: string; disabled: boolean; onError: () => void }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  return (
    <button type="button" disabled={disabled || busy} onClick={() => {
      setBusy(true);
      void prepareAction(decisionId).then((draft) => {
        if (mounted.current) navigate(workspacePathForInstrument(draft.instrumentId), { state: draft });
      }).catch(() => { if (mounted.current) onError(); }).finally(() => { if (mounted.current) setBusy(false); });
    }}>Prepare Paper Exit</button>
  );
}

export function PaperTrailingStopPanel({ instrumentId, paperActionsAvailable }: Props) {
  const [status, setStatus] = useState<SmaStopStatus | null>(null);
  const [config, setConfig] = useState<SmaStopConfig | null>(null);
  const [events, setEvents] = useState<{ rows: SmaStopEvent[]; total: number } | null>(null);
  const [evaluation, setEvaluation] = useState<SmaStopEvaluation | null>(null);
  const [windowText, setWindowText] = useState("20");
  const [interval, setInterval_] = useState("1m");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = useRef(instrumentId); current.current = instrumentId;
  const controller = useRef<AbortController | null>(null);

  const request = async (task: (signal: AbortSignal) => Promise<void>, failure: string) => {
    const key = instrumentId;
    controller.current?.abort(); const c = new AbortController(); controller.current = c;
    setBusy(true); setError(null);
    try { await task(c.signal); } catch { if (current.current === key && !c.signal.aborted) setError(failure); }
    finally { if (current.current === key && controller.current === c) setBusy(false); }
  };

  // Read-only on open: the persisted stop state and policy. Reading never advances or triggers a stop.
  useEffect(() => {
    setStatus(null); setEvents(null); setEvaluation(null); setError(null);
    void request(async (signal) => {
      const [nextStatus, nextConfig] = await Promise.all([smaStopStatus(instrumentId, signal), smaStopConfig(signal)]);
      if (signal.aborted || current.current !== instrumentId) return;
      setStatus(nextStatus); setConfig(nextConfig);
      if (nextConfig.policy) { setWindowText(String(nextConfig.policy.sma_window_bars)); setInterval_(nextConfig.policy.bar_interval); }
    }, "Stop state unavailable. Nothing is assumed about the stop.");
    return () => controller.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instrumentId]);

  const model = status ? buildPaperTrailingStopModel(status) : null;
  const bounds = config?.bounds;
  const windowValue = Number(windowText);
  const windowValid = Number.isInteger(windowValue) && Boolean(bounds) && windowValue >= bounds!.sma_window_bars[0] && windowValue <= bounds!.sma_window_bars[1];
  const refresh = async (signal: AbortSignal) => { const next = await smaStopStatus(instrumentId, signal); if (!signal.aborted && current.current === instrumentId) setStatus(next); };

  return (
    <section className="panel paper-cockpit-panel sma-stop-panel" aria-labelledby="sma-stop-heading">
      <h2 id="sma-stop-heading">Risk control — SMA trailing stop</h2>
      <p className="muted">
        Deterministic stop monitor on completed bars. It is not a resting broker stop order, and a breach never submits a Paper or Live order.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {!status && !error ? <p role="status">Loading stop state…</p> : null}
      {model && status ? (
        <>
          <p role="status" data-testid="sma-stop-status">
            <strong>Status: {status.status.replace(/_/g, " ")}</strong> — {model.statusLabel}
            {model.directionLabel ? ` · ${model.directionLabel}` : ""}
          </p>
          <dl className="paper-cockpit-meta">
            {model.rows.map((row) => (
              <div key={row.id}>
                <dt>{row.label}</dt>
                <dd>{row.value}{row.detail ? <span className="muted"> · {row.detail}</span> : null}</dd>
              </div>
            ))}
          </dl>
          {model.messages.map((message) => <p key={message} className="paper-cockpit-warning" role="status">{message}</p>)}
          {model.breach ? (
            <section role="alert" aria-label="SMA stop breached" className="sma-stop-breach">
              <h3>SMA trailing stop breached</h3>
              <dl className="paper-cockpit-meta">
                <div><dt>Stop</dt><dd>{model.breach.stop}{model.directionLabel ? ` · ${model.directionLabel}` : ""}</dd></div>
                <div><dt>Observed</dt><dd>{model.breach.trigger} · last trade</dd></div>
                <div><dt>Observed at</dt><dd>{model.breach.observedAt}</dd></div>
                <div><dt>Decision</dt><dd>{model.breach.decision}{model.breach.decisionId ? <span className="muted"> · {model.breach.decisionId}</span> : null}</dd></div>
                <div><dt>Reason</dt><dd>Deterministic SMA trailing-stop risk condition — no model chose or can change this level</dd></div>
                <div><dt>Paper close</dt><dd>{model.breach.paperClose}</dd></div>
              </dl>
              {model.breach.blockers.length ? <p role="status">Paper preview blocked: {model.breach.blockers.join(", ")}</p> : null}
              {model.breach.decisionId ? (
                <PrepareExit decisionId={model.breach.decisionId} disabled={!paperActionsAvailable || !model.breach.canPrepareExit}
                  onError={() => setError("Paper exit draft could not be prepared. The position and decision must be revalidated.")} />
              ) : null}
              <p>Preparing an exit only fills the order ticket with the current ledger quantity. Preview and submit stay explicit in the ticket.</p>
            </section>
          ) : null}
          <div className="sma-stop-actions">
            <button type="button" disabled={busy || !model.canEvaluate} onClick={() => void request(async (signal) => {
              const next = await evaluateSmaStop(instrumentId, signal); if (!signal.aborted && current.current === instrumentId) setStatus(next);
            }, "Stop evaluation failed. The stored stop is unchanged.")}>{busy ? "Working…" : "Evaluate Stop Now"}</button>
          </div>
        </>
      ) : null}
      {config ? (
        <details>
          <summary>Stop policy</summary>
          <p>{config.reference_config.note} Reference: SMA {config.reference_config.sma_window_bars} on {config.reference_config.bar_interval} bars.</p>
          <label>SMA window (completed bars)
            <input type="number" inputMode="numeric" min={bounds?.sma_window_bars[0]} max={bounds?.sma_window_bars[1]} value={windowText} disabled={busy}
              onChange={(event) => setWindowText(event.target.value)} aria-describedby="sma-stop-window-help" />
          </label>
          <span id="sma-stop-window-help" className="muted"> {bounds ? `${bounds.sma_window_bars[0]}–${bounds.sma_window_bars[1]}` : ""}</span>
          <label>Bar interval
            <select value={interval} disabled={busy} onChange={(event) => setInterval_(event.target.value)}>
              {(bounds?.bar_interval ?? [interval]).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <button type="button" disabled={busy || !windowValid} onClick={() => void request(async (signal) => {
            const next = await configureSmaStop({ enabled: true, sma_window_bars: windowValue, bar_interval: interval }, signal);
            if (signal.aborted) return; setConfig(next); await refresh(signal);
          }, "Stop policy not changed. A working stop cannot be replaced; disable it or close the position first.")}>
            {config.enabled ? "Apply stop policy" : "Enable stop policy"}
          </button>
          {config.enabled ? (
            <button type="button" disabled={busy} onClick={() => void request(async (signal) => {
              const next = await configureSmaStop({ enabled: false }, signal); if (signal.aborted) return; setConfig(next); await refresh(signal);
            }, "Stop policy not changed.")}>Disable stop policy</button>
          ) : null}
          <p className="muted">Only the window and interval can be set. Stop levels are computed by the server and cannot be entered or moved.</p>
        </details>
      ) : null}
      <details>
        <summary>Stop history</summary>
        <button type="button" disabled={busy} onClick={() => void request(async (signal) => {
          const next = await smaStopHistory(instrumentId, 20, signal); if (!signal.aborted && current.current === instrumentId) setEvents({ rows: next.events, total: next.total });
        }, "Stop history unavailable.")}>Read stop history</button>
        {events ? (
          events.rows.length ? (
            <table>
              <caption>Latest {events.rows.length} of {events.total} stop events, newest first</caption>
              <thead><tr><th scope="col">Time</th><th scope="col">Event</th><th scope="col">SMA</th><th scope="col">Active stop</th><th scope="col">Previous stop</th><th scope="col">Reasons</th></tr></thead>
              <tbody>
                {events.rows.map((item) => (
                  <tr key={item.sequence}>
                    <td>{formatStopTime(item.at)}</td><th scope="row">{item.kind.replace(/_/g, " ")} · {item.side}</th><td>{formatStopPrice(item.sma_value)}</td>
                    <td>{formatStopPrice(item.active_stop)}</td><td>{item.previous_stop ? formatStopPrice(item.previous_stop) : "None"}</td><td>{item.reason_codes.join(", ") || "None"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p role="status">No stop events recorded.</p>
        ) : null}
      </details>
      <details>
        <summary>Replay evaluation</summary>
        <button type="button" disabled={busy} onClick={() => void request(async (signal) => {
          const next = await smaStopEvaluation(signal); if (!signal.aborted) setEvaluation(next);
        }, "Replay comparison unavailable.")}>Read replay comparison</button>
        {evaluation ? <SmaStopEvaluationTable evaluation={evaluation} /> : null}
      </details>
    </section>
  );
}

import type { AiStatus, SynthesisEngine } from "../../../api/screenerNews";

const compactTokens = (value: number) => value >= 1000 ? `${Math.round(value / 1000)}k` : String(value);

export type EngineFit = { engine: string; fits: boolean | null; packet_size: number | null; context_window: number | null };
export type PendingEngine = { engine: SynthesisEngine; model: string | null };

/** Why the picker is locked, or null when the engine may be changed. */
export function engineLockText(ai: AiStatus) {
  const lock = ai.engine_lock;
  if (!lock?.locked) return null;
  return lock.reason === "REEVALUATION_LOOP_RUNNING" ? "Locked while automatic passes are running. Stop them to change the engine."
    : `Locked: the state of automatic passes could not be read${lock.reason ? ` (${lock.reason})` : ""}.`;
}

/** "does not fit: needs ~37k tokens, model context 8k", "fits", or null when nothing is known either way. */
export function fitText(fit: EngineFit | undefined) {
  if (!fit || fit.fits === null || fit.packet_size === null || fit.context_window === null) return null;
  return fit.fits ? "current packet fits" : `current packet does not fit: needs ~${compactTokens(fit.packet_size)} tokens, model context ${compactTokens(fit.context_window)}`;
}

/**
 * The engine choice is saved for the whole machine and takes effect at once, so it is confirmed first. Nothing is
 * sent until the operator confirms.
 */
export function EngineSwitchConfirm({ pending, fit, busy, onConfirm, onCancel }: {
  pending: PendingEngine; fit?: EngineFit; busy: boolean; onConfirm: () => void; onCancel: () => void }) {
  const unfit = fit?.fits === false ? fitText(fit) : null;
  return <div className="engine-switch-confirm" role="alertdialog" aria-label="Confirm AI engine change">
    <p><strong>Switch the AI engine to {pending.engine.label}{pending.model ? ` · ${pending.model}` : ""}?</strong></p>
    <p>This applies to every AI panel on this machine (News synthesis, AI Screener, Action Decisions and automatic passes), starting with the next request. A call already in flight finishes on the current engine.</p>
    {pending.engine.runtime === "PAID_API" ? <p>This is a paid API: its calls count against the shared daily budget.</p> : <p>This is the local model: no API cost.</p>}
    {unfit && <p className="engine-switch-warning">The {unfit}. An AI Screener run on it would be refused or cut short.</p>}
    <div><button type="button" disabled={busy} onClick={onConfirm}>Switch engine</button> <button type="button" disabled={busy} onClick={onCancel}>Keep current engine</button></div>
  </div>;
}

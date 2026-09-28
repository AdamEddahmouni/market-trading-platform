/** Labels are presentation only; the Workspace and Screener keep separate data contracts. */
const LABELS: Record<string, string> = {
  BASELINE: "Baseline", VULNERABLE: "Vulnerable", ARMED: "Armed", IGNITION_WATCH: "Ignition watch",
  LIVE_CONFIRMATION: "Live confirmation", ACTIVE_SQUEEZE: "Active squeeze evidence",
  EXHAUSTION: "Exhaustion evidence", POST_SQUEEZE: "Post-squeeze", UNEVALUABLE: "Insufficient evidence",
};

export const squeezeStateLabel = (state: string) => LABELS[state] ?? state;

type Stage = { state: string; current: boolean; reachable: boolean; unreachable_reason: string | null };
export function SqueezeLifecycle({ state, stages }: { state: string; stages: Stage[] }) {
  return <section className="screener-squeeze-lifecycle" aria-label="Squeeze evidence lifecycle">
    <p className="screener-panel-note">Snapshot assessment · {squeezeStateLabel(state)}. This strip is context, not a transition history.</p>
    <ol>{stages.map((stage) => <li key={stage.state} className={`${stage.current ? "current" : ""} ${stage.reachable ? "" : "unreachable"}`}
      aria-current={stage.current ? "step" : undefined} title={stage.unreachable_reason ?? undefined}>
      <span>{squeezeStateLabel(stage.state)}</span>{!stage.reachable && <small>Unavailable</small>}</li>)}</ol>
    {state === "UNEVALUABLE" && <p className="screener-panel-note">Current inputs do not support a state assessment.</p>}
  </section>;
}

import { useEffect, useRef, useState } from "react";
import { draftNextSession, evaluateNextSession, lockNextSession, observeNextSession, type NextSessionView } from "../../../api/screenerReevaluation";

const shown = (value: number | string | null | undefined) => value ?? "Unavailable";

/** Freeze one action decision for the next market session. Reads and records only; never places an order. */
export default function NextSessionPanel({ decisionId, actionState }: { decisionId: string; actionState: string }) {
  const [view, setView] = useState<NextSessionView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = useRef(decisionId); current.current = decisionId;
  useEffect(() => { setView(null); setError(null); setBusy(false); }, [decisionId]);
  const request = (task: () => Promise<NextSessionView>) => {
    const key = decisionId; setBusy(true); setError(null);
    void task().then((value) => { if (current.current === key) setView(value); })
      .catch((reason: unknown) => { if (current.current === key) setError(reason instanceof Error ? reason.message : "Request failed"); })
      .finally(() => { if (current.current === key) setBusy(false); });
  };
  if (actionState === "REVALIDATION_REQUIRED") return <p>Next-session freeze unavailable: this evaluation requires revalidation.</p>;
  const snapshot = view?.snapshot;
  const comparison = view?.comparison;
  return <section className="next-session" aria-label="Next-session decision">
    {!snapshot && <button type="button" disabled={busy} onClick={() => request(() => draftNextSession(decisionId))}>Freeze for Next Session</button>}
    {error && <p role="alert">Next-session request rejected: {error}</p>}
    {snapshot && <>
      <h5>NEXT-SESSION DECISION</h5>
      <p>Lock state: <strong>{snapshot.lock_state === "LOCKED" ? "LOCKED — immutable. This snapshot cannot be changed." : "DRAFT — not yet frozen"}</strong> · lifecycle {snapshot.state}</p>
      <p>Target: {snapshot.target_session_date} · {snapshot.target_session_kind} · {snapshot.target_timezone} · session {snapshot.target_session_start} → {snapshot.target_session_end} · early-close metadata {snapshot.early_close_metadata}</p>
      <p>Decision cutoff: {snapshot.decision_cutoff} · Action: {snapshot.action_state} · Direction: {shown(snapshot.direction)} · Position at cutoff: {snapshot.position_state}</p>
      <p>Reference: {shown(snapshot.reference_price)} as of {shown(snapshot.reference_price_as_of)} ({snapshot.evaluation_policy.reference_price_basis})</p>
      <p>Evaluation: {snapshot.evaluation_policy.policy_id} · observe {snapshot.evaluation_policy.observation_start} → {snapshot.evaluation_policy.observation_end}</p>
      <p>Model: {shown(snapshot.provider_id)} · {shown(snapshot.model_id)} · {snapshot.prompt_id}</p>
      <p>Evidence snapshot {snapshot.evidence_snapshot_ref} · source decision {snapshot.action_decision_id} · {snapshot.validity_state} · integrity {view.integrity} · storage {view.durability}</p>
      {snapshot.lock_state === "DRAFT" && <button type="button" disabled={busy} onClick={() => request(() => lockNextSession(snapshot.snapshot_id))}>Lock</button>}
      {snapshot.lock_state === "LOCKED" && <>
        {snapshot.locked_at && <p>Locked at {snapshot.locked_at}. Later evidence appears only as observations or new decisions.</p>}
        {snapshot.state !== "EVALUATED" && snapshot.state !== "INSUFFICIENT_DATA" && <>
          <button type="button" disabled={busy} onClick={() => request(() => observeNextSession(snapshot.snapshot_id))}>Record observation</button>
          <button type="button" disabled={busy} onClick={() => request(() => evaluateNextSession(snapshot.snapshot_id))}>Evaluate outcome</button>
        </>}
        <h5>NEXT-SESSION OBSERVATION</h5>
        <p>Evaluation status: {snapshot.state} · {view.observation_count} observation{view.observation_count === 1 ? "" : "s"} recorded</p>
        {comparison ? <>
          <p>Frozen: {comparison.frozen_action_state} {comparison.frozen_direction ?? ""} · Decision reference {shown(comparison.decision_reference_price)}</p>
          <p>Observed in window: first {shown(comparison.first_observed_price)} · last {shown(comparison.last_observed_price)} at {shown(comparison.last_observed_at)} · change since decision {comparison.change_pct == null ? "Unavailable" : `${comparison.change_pct}%`}</p>
          <p>Current decision: {comparison.subsequent_action_state ?? "No later decision — the frozen decision is still the latest"} · Current position: {comparison.position_state_now}</p>
          <p>Signal comparison: {comparison.signal_outcome.quality} · Paper execution outcome: {comparison.execution_outcome.quality}</p>
          <p>This is an observation of market price after the decision. It is not profit and loss and not evidence of accuracy.</p>
        </> : <p>No later observation recorded yet.</p>}
      </>}
    </>}
  </section>;
}

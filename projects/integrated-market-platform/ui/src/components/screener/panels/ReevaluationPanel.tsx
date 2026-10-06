import { useEffect, useRef, useState } from "react";
import type { AiScreenerScope } from "../../../api/screenerAi";
import { configureReevaluation, reevaluationHistory, reevaluationStatus, runReevaluationOnce, startReevaluation, stopReevaluation,
  type ReevaluationCycle, type ReevaluationStatus } from "../../../api/screenerReevaluation";

const READINESS: Record<string, string> = { REEVALUATION_READY: "Ready", REEVALUATION_DEGRADED: "Degraded", REEVALUATION_BLOCKED: "Blocked" };
const text = (value: string | number | null | undefined) => value ?? "—";

function CycleRow({ cycle }: { cycle: ReevaluationCycle }) {
  if (cycle.not_observed) return <li>
    <strong>NOT OBSERVED</strong> · {cycle.not_observed.observed_from} → {cycle.not_observed.observed_to} · {cycle.not_observed.missed_scheduled_cycles} scheduled cycle{cycle.not_observed.missed_scheduled_cycles === 1 ? "" : "s"} missed · {cycle.not_observed.reason} · no decisions were reconstructed
  </li>;
  return <li>
    <strong>{cycle.cycle_status.replace(/_/g, " ")}</strong> · {cycle.trigger} · scheduled {cycle.scheduled_for} · started {cycle.started_at} (drift {cycle.start_drift_ms} ms) · duration {text(cycle.duration_ms)} ms · model calls {cycle.model_call_count} · avoided {cycle.counters.model_calls_avoided}
    {cycle.missed_ticks_before > 0 && <> · {cycle.missed_ticks_before} missed before this cycle</>}
    {cycle.reason_codes.length > 0 && <> · {cycle.reason_codes.join(", ")}</>}
    {cycle.transitions.length === 0 ? <> · Decision unchanged</> : <ul>{cycle.transitions.map((t, index) => <li key={index}>
      {t.instrument_id ?? "Candidate set"} · {t.classification.replace(/_/g, " ")}{t.prior_state || t.new_state ? ` · ${t.prior_state ?? "Initial"} → ${t.new_state ?? "no new decision"}` : ""} · model call: {t.model_call ? "yes" : "no"} · {t.reason_codes.join(", ")}
    </li>)}</ul>}
  </li>;
}

/** Operator-controlled recurring reevaluation. Opening this panel never starts anything. */
export default function ReevaluationPanel({ scope }: { scope: AiScreenerScope }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ReevaluationStatus | null>(null);
  const [cycles, setCycles] = useState<ReevaluationCycle[]>([]);
  const [cadence, setCadence] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The pre-start assessment from Configure; later cycles report their own.
  const [preview, setPreview] = useState<ReevaluationStatus["readiness"]>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const refresh = async () => {
    const [next, history] = [await reevaluationStatus(), await reevaluationHistory(20).catch(() => null)];
    if (mounted.current) { setStatus(next); if (history) setCycles(history.cycles); }
  };
  const request = (task: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    void task().then(refresh).catch((reason: unknown) => { if (mounted.current) setError(reason instanceof Error ? reason.message : "Request failed"); })
      .finally(() => { if (mounted.current) setBusy(false); });
  };
  const running = status?.worker_state === "RUNNING" || status?.worker_state === "DELAYED";
  // Display refresh only while a worker is running: it reads status and receipts, never evaluates.
  useEffect(() => { if (!open || !running) return; const timer = setInterval(() => { void refresh().catch(() => undefined); }, 5_000); return () => clearInterval(timer); }, [open, running]);
  const configured = Boolean(status?.loop_id);
  const readiness = status?.readiness ?? preview;
  return <section className="reevaluation" aria-label="Reevaluation">
    <button type="button" disabled={busy} onClick={() => { setOpen(true); request(async () => undefined); }}>Open reevaluation controls</button>
    {open && <>
      {error && <p role="alert">Reevaluation request rejected: {error}</p>}
      {status && <>
        <h4>REEVALUATION</h4>
        <p role="status">Worker: <strong>{status.worker_state}</strong> — {status.worker_label}</p>
        <label>Requested cadence (seconds) <input type="number" min={10} max={3600} value={cadence} disabled={busy || running} onChange={(event) => setCadence(Number(event.target.value))} /></label>
        <button type="button" disabled={busy || running} onClick={() => request(async () => { const next = await configureReevaluation(scope, cadence); if (mounted.current) setPreview(next.readiness ?? null); })}>Configure</button>
        {configured && <>
          <p>Scope: {status.scope?.universe} · Account: {status.account_id} · storage {status.durability}</p>
          <p>Requested: {status.requested_cadence_seconds} sec · Effective: {status.effective_cadence_seconds} sec{status.cadence?.degraded ? ` — slower than requested (limited by ${status.cadence.limiting_constraint})` : ""}</p>
          <p>AI engine: {text(status.engine.provider_id)} · {text(status.engine.model_id)} · {text(status.engine.runtime)} · {status.engine.state}{status.engine.reason ? ` (${status.engine.reason})` : ""}{status.engine.budget ? ` · budget ${status.engine.budget.requests}/${status.engine.budget.max_requests} requests` : ""}</p>
          {status.projection && <p>Model call caps: at most {status.projection.worst_case_model_calls} calls per {status.projection.session_minutes}-minute session ({status.projection.cycles} cycles). Projection of request volume, not a cost.</p>}
          <p>Paper execution remains manual: reevaluation never previews, hands off or submits an order.</p>
          {readiness ? <>
            <p>Provider readiness: <strong>{READINESS[readiness.readiness]}</strong>{readiness.reason_codes.length ? ` · ${readiness.reason_codes.join(", ")}` : ""}</p>
            <table><caption>Evidence clocks — a {status.requested_cadence_seconds}-second schedule does not make slower evidence {status.requested_cadence_seconds}-second fresh</caption>
              <thead><tr><th scope="col">Capability</th><th scope="col">Provider</th><th scope="col">Cadence semantics</th><th scope="col">State</th><th scope="col">As of / age</th><th scope="col">Within requested cadence</th></tr></thead>
              <tbody>{readiness.provider_states.map((row) => <tr key={row.capability}>
                <th scope="row">{row.capability}</th><td>{text(row.provider)}</td><td>{row.cadence_semantics.replace(/_/g, "-")}{row.delivery_mode ? ` · ${row.delivery_mode}` : ""}</td>
                <td>{text(row.state)}</td><td>{text(row.as_of)}{row.age_seconds != null ? ` · ${row.age_seconds}s old` : ""}</td><td>{row.within_requested_cadence ? "Yes" : "No"}</td>
              </tr>)}</tbody></table>
          </> : <p>Provider readiness: not yet assessed — configure or run a cycle.</p>}
          {running ? <button type="button" disabled={busy} onClick={() => request(() => stopReevaluation())}>Stop</button>
            : <button type="button" disabled={busy} onClick={() => request(() => startReevaluation())}>Start</button>}
          <button type="button" disabled={busy} onClick={() => request(() => runReevaluationOnce())}>Run Reevaluation Now</button>
          {status.liveness && <p>Last scheduled {text(status.liveness.last_scheduled)} · last started {text(status.liveness.last_started)} · last completed {text(status.liveness.last_completed)} · last result {text(status.liveness.last_status?.replace(/_/g, " "))} · next {text(status.next_scheduled)} · missed cycles {status.liveness.missed_ticks} · cycles run {status.liveness.cycle_count}{status.liveness.last_error ? ` · last error ${status.liveness.last_error.code} at ${status.liveness.last_error.at}` : ""}</p>}
          <h4>Cycle history (latest {cycles.length})</h4>
          {cycles.length ? <ol reversed>{cycles.map((cycle) => <CycleRow key={cycle.cycle_id} cycle={cycle} />)}</ol> : <p>No cycles recorded.</p>}
        </>}
      </>}
    </>}
  </section>;
}

import { msIso, stampText } from "../screenerText";
import { useEffect, useRef, useState } from "react";
import type { AiScreenerScope } from "../../../api/screenerAi";
import { armPaperAutomation, configurePaperAutomation, disarmPaperAutomation, emergencyStopPaperAutomation, paperAutomationHistory,
  paperAutomationReport, paperAutomationStatus, pausePaperAutomation, resumePaperAutomation, startPaperAutomation, stopPaperAutomation,
  type PaperAutomationEvent, type PaperAutomationPolicyInput, type PaperAutomationReport, type PaperAutomationStatus } from "../../../api/paperAutomation";

const text = (value: string | number | null | undefined) => value ?? "—";
const money = (minor: number | null | undefined) => minor == null ? "—" : `${minor < 0 ? "−" : ""}$${(Math.abs(minor) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const words = (value: string) => value.replace(/_/g, " ");
/** The server's four blocked primary states. Any other primary state can still carry open blockers. */
const BLOCKED_STATUS = ["BLOCKED_BY_AUTHORITY", "BLOCKED_BY_DATA", "BLOCKED_BY_RISK", "BLOCKED_BY_BUDGET"];

/** Every value is typed by the owner. Nothing is pre-filled, so nothing is activated that the owner did not choose. */
const NUMBERS = [
  ["cadence_seconds", "Evaluation cadence (seconds, 60–3600)"],
  ["universe_evaluation_interval_seconds", "Full-universe AI evaluation interval (seconds, 300–86400)"],
  ["no_new_entries_minutes_before_close", "No new entries in the last N minutes before the close"],
  ["max_position_notional", "Maximum position size ($)"],
  ["max_aggregate_exposure", "Maximum aggregate exposure ($)"],
  ["max_open_positions", "Maximum open positions"],
  ["max_daily_loss", "Maximum daily loss before entries halt ($)"],
  ["max_per_trade_risk", "Maximum risk per trade ($)"],
  ["assumed_adverse_move_bps", "Adverse move assumed when sizing per-trade risk (basis points)"],
  ["max_paid_requests_per_day", "Paid AI requests per day (0 when paid AI is not authorized)"],
  ["max_paid_tokens_per_day", "Paid AI tokens per day (0 when paid AI is not authorized)"],
  ["max_consecutive_failures", "Consecutive failed cycles before automatic emergency stop (1–20)"],
] as const;
const CHOICES = [
  ["allow_entries", "Automatic entries"],
  ["allow_long", "Long entries"],
  ["allow_short", "Short entries"],
  ["allow_exits", "Automatic exits"],
  ["on_stop_breach", "Exit automatically on a trailing-stop breach"],
  ["on_thesis_exit", "Exit automatically when the gated decision is EXIT"],
  ["allow_local_inference", "Unattended local AI inference"],
  ["allow_paid_inference", "Unattended paid AI inference"],
] as const;
/** Adaptive full-universe scheduling. Every one of these is optional: left blank, the owner keeps the fixed
 * minimum separation and nothing is defaulted into the saved policy. */
const OPTIONAL_NUMBERS = [
  ["universe_max_age_seconds", "Maximum useful age of a complete selection (seconds, 300–86400; blank = no maximum)"],
  ["universe_max_runs_per_day", "Maximum full-universe runs per UTC day (1–100; blank = not capped by this policy)"],
] as const;
const OPTIONAL_CHOICES = [
  ["universe_material_change_trigger", "Re-run when the evaluated universe materially changes"],
] as const;
const OPTIONAL_BOUNDS: Record<typeof OPTIONAL_NUMBERS[number][0], { min: number; max?: number; step: number }> = {
  universe_max_age_seconds: { min: 300, max: 86400, step: 1 },
  universe_max_runs_per_day: { min: 1, max: 100, step: 1 },
};
const OVERNIGHT_NUMBERS = [
  ["max_overnight_positions", "Maximum overnight positions (0–5)"],
  ["max_overnight_exposure", "Maximum overnight exposure ($, at most 25,000)"],
  ["max_hold_sessions", "Maximum holding period (1–5 trading days)"],
] as const;
type OvernightField = typeof OVERNIGHT_NUMBERS[number][0];
type OvernightDraft = Record<OvernightField, string>;
const EMPTY_OVERNIGHT = Object.fromEntries(OVERNIGHT_NUMBERS.map(([key]) => [key, ""])) as OvernightDraft;
type NumberField = typeof NUMBERS[number][0];
type ChoiceField = typeof CHOICES[number][0];
type AdaptiveNumberField = typeof OPTIONAL_NUMBERS[number][0];
type AdaptiveChoiceField = typeof OPTIONAL_CHOICES[number][0];
type Draft = Record<NumberField, string> & Record<ChoiceField, "" | "yes" | "no">;
type AdaptiveDraft = Record<AdaptiveNumberField, string> & Record<AdaptiveChoiceField, "" | "yes" | "no">;
const EMPTY = Object.fromEntries([...NUMBERS.map(([key]) => [key, ""]), ...CHOICES.map(([key]) => [key, ""])]) as Draft;
const EMPTY_ADAPTIVE = Object.fromEntries([...OPTIONAL_NUMBERS.map(([key]) => [key, ""]), ...OPTIONAL_CHOICES.map(([key]) => [key, ""])]) as AdaptiveDraft;
/** Browser-side range hints only. The server remains the authority for every bound; nothing here changes what is sent. */
const BOUNDS: Record<NumberField, { min: number; max?: number; step: number }> = {
  cadence_seconds: { min: 60, max: 3600, step: 1 },
  universe_evaluation_interval_seconds: { min: 300, max: 86400, step: 1 },
  no_new_entries_minutes_before_close: { min: 0, max: 1440, step: 1 },
  max_position_notional: { min: 0, step: 0.01 },
  max_aggregate_exposure: { min: 0, step: 0.01 },
  max_open_positions: { min: 0, step: 1 },
  max_daily_loss: { min: 0, step: 0.01 },
  max_per_trade_risk: { min: 0, step: 0.01 },
  assumed_adverse_move_bps: { min: 0, step: 1 },
  max_paid_requests_per_day: { min: 0, step: 1 },
  max_paid_tokens_per_day: { min: 0, step: 1 },
  max_consecutive_failures: { min: 1, max: 20, step: 1 },
};

function policyFrom(draft: Draft, adaptiveDraft: AdaptiveDraft, universe: string, overnightDraft: OvernightDraft): PaperAutomationPolicyInput | null {
  const number = (key: NumberField) => draft[key].trim() !== "" && Number.isFinite(Number(draft[key])) ? Number(draft[key]) : null;
  const dollars = (key: NumberField) => { const value = number(key); return value == null ? null : Math.round(value * 100); };
  const choice = (key: ChoiceField) => draft[key] === "" ? null : draft[key] === "yes";
  const values = { numbers: NUMBERS.map(([key]) => number(key)), choices: CHOICES.map(([key]) => choice(key)) };
  if (values.numbers.some((value) => value == null) || values.choices.some((value) => value == null)) return null;
  // A blank adaptive field is sent as nothing at all, never as a value the owner did not choose.
  const typed = (key: AdaptiveNumberField) => { const raw = adaptiveDraft[key].trim(); return raw === "" ? undefined : Number(raw); };
  if (OPTIONAL_NUMBERS.some(([key]) => { const raw = adaptiveDraft[key].trim(); return raw !== "" && !Number.isFinite(Number(raw)); })) return null;
  const adaptive: Record<string, number | boolean> = {};
  for (const [key] of OPTIONAL_NUMBERS) { const value = typed(key); if (value !== undefined) adaptive[key] = value; }
  for (const [key] of OPTIONAL_CHOICES) if (adaptiveDraft[key] !== "") adaptive[key] = adaptiveDraft[key] === "yes";
  const overnight: { max_overnight_positions?: number; max_overnight_exposure_minor?: number; max_hold_sessions?: number } = {};
  const overnightValues = OVERNIGHT_NUMBERS.map(([key]) => overnightDraft[key].trim());
  if (overnightValues.some(Boolean)) {
    if (overnightValues.some((value) => value === "" || !Number.isFinite(Number(value)))) return null;
    overnight.max_overnight_positions = Number(overnightDraft.max_overnight_positions);
    overnight.max_overnight_exposure_minor = Math.round(Number(overnightDraft.max_overnight_exposure) * 100);
    overnight.max_hold_sessions = Number(overnightDraft.max_hold_sessions);
  }
  return {
    schedule: { sessions: ["REGULAR"], cadence_seconds: number("cadence_seconds")!, universe_evaluation_interval_seconds: number("universe_evaluation_interval_seconds")!,
      no_new_entries_minutes_before_close: number("no_new_entries_minutes_before_close")!, ...adaptive },
    risk: { max_position_notional_minor: dollars("max_position_notional")!, max_aggregate_exposure_minor: dollars("max_aggregate_exposure")!,
      max_open_positions: number("max_open_positions")!, max_daily_loss_minor: dollars("max_daily_loss")!, max_per_trade_risk_minor: dollars("max_per_trade_risk")!,
      assumed_adverse_move_bps: number("assumed_adverse_move_bps")!, allowed_universes: [universe], order_types: ["MARKET"],
      allow_long: choice("allow_long")!, allow_short: choice("allow_short")!, allow_entries: choice("allow_entries")!, allow_exits: choice("allow_exits")!, ...overnight },
    exits: { on_stop_breach: choice("on_stop_breach")!, on_thesis_exit: choice("on_thesis_exit")! },
    ai: { allow_local_inference: choice("allow_local_inference")!, allow_paid_inference: choice("allow_paid_inference")!,
      max_paid_requests_per_day: number("max_paid_requests_per_day")!, max_paid_tokens_per_day: number("max_paid_tokens_per_day")! },
    emergency_stop: { max_consecutive_failures: number("max_consecutive_failures")! },
  };
}

function EventRow({ event }: { event: PaperAutomationEvent }) {
  const detail = event as Record<string, unknown>;
  const reasons = Array.isArray(detail.reason_codes) ? (detail.reason_codes as string[]).join(", ") : typeof detail.reason === "string" ? detail.reason : "";
  if (event.kind === "NOT_OBSERVED") return <li><strong>NOT OBSERVED</strong> · {text(detail.observed_from as string)} → {text(detail.observed_to as string)} · {text(detail.missed_scheduled_cycles as number)} scheduled cycles missed · {reasons} · nothing was evaluated or ordered for this period</li>;
  return <li><strong>{words(event.kind)}</strong> · {text(event.at_iso)}{typeof detail.instrument_id === "string" ? ` · ${detail.instrument_id}` : ""}{typeof detail.status === "string" ? ` · ${words(detail.status)}` : ""}{reasons ? ` · ${reasons}` : ""}</li>;
}

/** Owner controls for unattended internal Paper simulation. Opening this panel configures, arms and starts nothing. */
export default function PaperAutomationPanel({ scope }: { scope: AiScreenerScope }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<PaperAutomationStatus | null>(null);
  const [events, setEvents] = useState<PaperAutomationEvent[]>([]);
  const [report, setReport] = useState<PaperAutomationReport | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [adaptive, setAdaptive] = useState<AdaptiveDraft>(EMPTY_ADAPTIVE);
  const [overnight, setOvernight] = useState<OvernightDraft>(EMPTY_OVERNIGHT);
  const [phrase, setPhrase] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A failed read is not an absence of activity, so each section reports its own read failure.
  const [unread, setUnread] = useState({ history: false, report: false });
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const refresh = async () => {
    const next = await paperAutomationStatus();
    const configured = next.status !== "NOT_CONFIGURED";
    let history: { events: PaperAutomationEvent[] } | null = null;
    let summary: PaperAutomationReport | null = null;
    let historyFailed = false;
    let reportFailed = false;
    if (configured) {
      history = await paperAutomationHistory(30).catch(() => { historyFailed = true; return null; });
      summary = await paperAutomationReport().catch(() => { reportFailed = true; return null; });
    }
    if (!mounted.current) return;
    setStatus(next);
    if (!configured) { setEvents([]); setReport(null); setUnread({ history: false, report: false }); return; }
    // A failed read keeps the last good data and says so, instead of rendering as "nothing happened".
    if (!historyFailed) setEvents(history?.events ?? []);
    if (!reportFailed) setReport(summary);
    setUnread({ history: historyFailed, report: reportFailed });
  };
  const request = (task: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    void task().then(refresh).catch((cause: unknown) => { if (mounted.current) setError(cause instanceof Error ? cause.message : "Request failed"); })
      .finally(() => { if (mounted.current) setBusy(false); });
  };
  const scheduled = status?.desired_state === "RUNNING" || status?.desired_state === "PAUSED";
  // Display refresh only: reads status, history and the report. It never evaluates, previews or submits.
  useEffect(() => { if (!open || !scheduled) return; const timer = setInterval(() => { void refresh().catch(() => undefined); }, 5_000); return () => clearInterval(timer); }, [open, scheduled]);
  const policy = policyFrom(draft, adaptive, scope.universe, overnight);
  const configured = Boolean(status?.policy);
  const armed = Boolean(status?.armed);
  const emergency = Boolean(status?.emergency);
  const cycle = status?.last_cycle;
  const universe = status?.universe;
  const scheduling = status?.scheduling;
  return <section className="reevaluation paper-automation" aria-label="Paper automation">
    <button type="button" disabled={busy} onClick={() => { setOpen(true); request(async () => undefined); }}>Open Paper automation controls</button>
    {open && <>
      {error && <p role="alert">Paper automation request rejected: {error}</p>}
      {status && <>
        <h4>AUTONOMOUS PAPER OPERATIONS</h4>
        <p role="status">Automation: <strong>{status.status}</strong> — {status.status_label}</p>
        <p>Internal Paper simulation only ({status.boundary.execution_mode} · {status.boundary.execution_provider}). No real-money order route is reachable from this controller, and simulated fills are not market truth.</p>
        {(status.blockers?.length ?? 0) > 0 && (() => {
          // The server reports one primary status, and the other categories can be open at the same time (for
          // example the regular session is closed *and* spending is unauthorized). A primary label that is not
          // itself a blocked state must never read as "nothing else is wrong", so those blockers are named as
          // open alongside it. This is presentation only: the server's status remains the single authority.
          const open = status.blockers!.map((blocker) => `${blocker.category} · ${blocker.code}`).join("; ");
          return <p>{BLOCKED_STATUS.includes(status.status) ? `Blocked by: ${open}` : `Also open while the primary state is ${status.status}: ${open}`}</p>;
        })()}
        {(status.identity_blockers?.length ?? 0) > 0 && <p>Not available on this backend: {status.identity_blockers!.join(", ")}</p>}
        <p>Market session: {words(status.session.label)} · {status.session.session_date}{status.session.minutes_to_close != null ? ` · ${status.session.minutes_to_close} min to the regular close` : ""} · storage {status.durability}</p>

        {!armed && !emergency && <fieldset disabled={busy}>
          <legend>Owner policy — every field is required and nothing is pre-filled</legend>
          <p>Scope: {scope.universe} with the current Screener filters · regular session only · market orders only.{configured ? ` Current policy ${status.policy!.policy_id}; configuring again replaces it.` : ""}</p>
          {NUMBERS.map(([key, label]) => <label key={key}>{label} <input type="number" {...BOUNDS[key]} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>)}
          {CHOICES.map(([key, label]) => <label key={key}>{label} <select value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value as Draft[ChoiceField] })}>
            <option value="">Choose…</option><option value="yes">Allowed</option><option value="no">Not allowed</option></select></label>)}
          <p>Adaptive full-universe scheduling — optional. Leave every line blank to keep the fixed minimum separation above.</p>
          {OPTIONAL_NUMBERS.map(([key, label]) => <label key={key}>{label} <input type="number" {...OPTIONAL_BOUNDS[key]} value={adaptive[key]} onChange={(event) => setAdaptive({ ...adaptive, [key]: event.target.value })} /></label>)}
          {OPTIONAL_CHOICES.map(([key, label]) => <label key={key}>{label} <select value={adaptive[key]} onChange={(event) => setAdaptive({ ...adaptive, [key]: event.target.value as AdaptiveDraft[AdaptiveChoiceField] })}>
            <option value="">Not enabled</option><option value="yes">Enabled</option><option value="no">Disabled</option></select></label>)}
          <p>Overnight holds are optional. Leave all three blank to close every automation position before the bell.</p>
          {OVERNIGHT_NUMBERS.map(([key, label]) => <label key={key}>{label} <input type="number" min={key === "max_hold_sessions" ? 1 : 0}
            max={key === "max_overnight_exposure" ? 25000 : 5} step={key === "max_overnight_exposure" ? 0.01 : 1}
            value={overnight[key]} onChange={(event) => setOvernight({ ...overnight, [key]: event.target.value })} /></label>)}
          <button type="button" disabled={busy || !policy} onClick={() => request(() => configurePaperAutomation(scope, policy!))}>Save policy</button>
          {!policy && <p>Complete every field to save the policy. Saving a policy arms nothing.</p>}
        </fieldset>}

        {configured && <>
          <h4>Policy {status.policy!.policy_id}</h4>
          <p>Cadence {status.policy!.schedule.cadence_seconds}s · full-universe AI every {status.policy!.schedule.universe_evaluation_interval_seconds}s · no entries in the last {status.policy!.schedule.no_new_entries_minutes_before_close} min · sessions {status.policy!.schedule.sessions.join(", ")}</p>
          <p>Position ≤ {money(status.policy!.risk.max_position_notional_minor)} · exposure ≤ {money(status.policy!.risk.max_aggregate_exposure_minor)} · open positions ≤ {status.policy!.risk.max_open_positions} · daily loss halt {money(status.policy!.risk.max_daily_loss_minor)} · per-trade risk {money(status.policy!.risk.max_per_trade_risk_minor)} at {status.policy!.risk.assumed_adverse_move_bps} bps</p>
          <p>Entries {status.policy!.risk.allow_entries ? "on" : "off"} (long {status.policy!.risk.allow_long ? "yes" : "no"}, short {status.policy!.risk.allow_short ? "yes" : "no"}) · exits {status.policy!.risk.allow_exits ? "on" : "off"} (stop breach {status.policy!.exits.on_stop_breach ? "yes" : "no"}, thesis {status.policy!.exits.on_thesis_exit ? "yes" : "no"}) · local AI {status.policy!.ai.allow_local_inference ? "authorized" : "not authorized"} · paid AI {status.policy!.ai.allow_paid_inference ? `authorized up to ${status.policy!.ai.max_paid_requests_per_day} requests and ${status.policy!.ai.max_paid_tokens_per_day} tokens per day` : "not authorized"}</p>
          <p>A per-trade risk limit sizes the order; it does not guarantee the loss. A stop is not a guaranteed fill.</p>

          {!armed && !emergency && <>
            <label>Type {status.arm_acknowledgement} to arm this policy for Paper-only automation <input type="text" value={phrase} autoComplete="off" onChange={(event) => setPhrase(event.target.value)} /></label>
            <button type="button" disabled={busy || phrase !== status.arm_acknowledgement} onClick={() => request(async () => { await armPaperAutomation(status.policy!.policy_id, phrase); if (mounted.current) setPhrase(""); })}>Arm Paper automation</button>
          </>}
          {armed && <p>Armed {text(status.arming?.armed_at)}{status.arming?.operator ? ` by ${status.arming.operator}` : ""} · authorization {status.arming?.arming_id} · Paper-only</p>}
          {emergency && <p role="alert">Emergency stop latched {status.emergency!.at} · {status.emergency!.reason} ({status.emergency!.source}). Positions were not liquidated. Disarm to clear it.</p>}

          <div>
            {armed && !emergency && status.desired_state === "STOPPED" && <button type="button" disabled={busy} onClick={() => request(() => startPaperAutomation())}>Start</button>}
            {status.desired_state === "RUNNING" && <button type="button" disabled={busy} onClick={() => request(() => pausePaperAutomation())}>Pause</button>}
            {status.desired_state === "PAUSED" && <button type="button" disabled={busy} onClick={() => request(() => resumePaperAutomation())}>Resume</button>}
            {scheduled && <button type="button" disabled={busy} onClick={() => request(() => stopPaperAutomation())}>Stop</button>}
            {(armed || emergency) && <button type="button" disabled={busy} onClick={() => request(() => disarmPaperAutomation())}>Disarm</button>}
            <label>Emergency stop reason (optional) <input type="text" value={reason} maxLength={200} onChange={(event) => setReason(event.target.value)} /></label>
            <button type="button" disabled={busy || emergency} onClick={() => request(async () => { await emergencyStopPaperAutomation(reason); if (mounted.current) setReason(""); })}>Emergency stop</button>
          </div>

          {status.liveness && <p>Controller: {status.liveness.owner === "THIS_PROCESS" ? "owned by this server" : status.liveness.owner === "OTHER_PROCESS" ? "owned by another process" : "not scheduled"} · worker {status.liveness.worker_alive ? "alive" : "not alive"} · heartbeat {text(status.liveness.heartbeat_at)} · last scheduled {text(status.liveness.last_scheduled)} · cycles {text(status.liveness.cycle_count)} · consecutive failures {text(status.liveness.consecutive_failures)}{status.liveness.last_error ? ` · last error ${status.liveness.last_error.code} at ${status.liveness.last_error.at}` : ""}</p>}
          <p>Provider: {status.provider ? `${status.provider.state}${status.provider.reasons.length ? ` · ${status.provider.reasons.join(", ")}` : ""}` : "not yet read by a cycle"} · AI engine: {text(status.engine?.provider_id)} · {text(status.engine?.model_id)} · {text(status.engine?.runtime)} · {text(status.engine?.state)}{status.engine?.reason ? ` (${status.engine.reason})` : ""} · unattended model calls {status.spending?.allowed ? "permitted" : `withheld${status.spending?.reason ? ` (${status.spending.reason})` : ""}`}</p>

          {scheduling && <>
            <h4>Adaptive full-universe scheduling</h4>
            <p>{scheduling.adaptive ? "Adaptive" : "Fixed minimum separation only"} · minimum separation {scheduling.policy.min_separation_seconds}s{scheduling.policy.max_age_seconds != null ? ` · a selection stays useful for ${scheduling.policy.max_age_seconds}s` : ""}{scheduling.policy.material_change_trigger ? " · re-runs on a material universe change" : ""}{scheduling.policy.max_runs_per_day != null ? ` · at most ${scheduling.policy.max_runs_per_day} runs per UTC day` : ""} · runs today {scheduling.runs_today.started}{scheduling.runs_today.limit != null ? ` of ${scheduling.runs_today.limit}` : ""}</p>
            {scheduling.last_complete_fingerprint ? <p>Last complete selection from session {scheduling.last_complete_fingerprint.session_date}{scheduling.last_complete_fingerprint.universe_count != null ? ` (${scheduling.last_complete_fingerprint.universe_count} rows read)` : ""}.</p> : <p>No complete full-universe selection has been adopted yet.</p>}
            {scheduling.last_decision ? <p>Last decision <strong>{words(scheduling.last_decision.decision)}</strong> at {text(scheduling.last_decision.at_iso)} because {scheduling.last_decision.reason_codes.map(words).join(", ")}{scheduling.next_eligible ? ` · next eligible ${scheduling.next_eligible}` : ""}.</p> : <p>No scheduling decision has been recorded yet.</p>}
            {scheduling.failure ? <p>Last run was not adoptable ({scheduling.failure.code}), {scheduling.failure.count} in a row; the next attempt waits until {stampText(msIso(scheduling.failure.backoff_until * 1000))}.</p> : null}
          </>}

          <h4>AI evaluation</h4>
          {universe?.active_run_id ? <p>Full-universe AI run {universe.active_run_id} in progress.</p>
            : universe?.last_result ? <p>Last full-universe run {universe.last_result.run_id}: <strong>{words(universe.last_result.status)}</strong>{universe.last_result.reason ? ` (${universe.last_result.reason})` : ""} · AI evaluated {text(universe.last_result.ai_evaluated_count)} of {text(universe.last_result.universe_count)} ({text(universe.last_result.ai_coverage_pct)}%) · {universe.last_result.adopted ? `selection adopted: ${(universe.last_result.selected ?? []).join(", ") || "no candidates"}` : "not adopted — coverage incomplete; no candidates were taken from it"}</p>
            : <p>No full-universe AI run has finished{universe?.withheld ? ` — withheld: ${universe.withheld.reason}` : ""}.</p>}
          <p>Candidates quoted by the server: {(status.candidate_quotes ?? []).join(", ") || "none"}</p>

          <h4>Latest cycle</h4>
          {cycle ? <>
            <p>{text(cycle.status ? words(cycle.status) : null)} · scheduled {cycle.scheduled_for}{cycle.error ? ` · error ${cycle.error}` : ""}{cycle.missed_cycles_before > 0 ? ` · ${cycle.missed_cycles_before} cycles missed before it` : ""}{cycle.reevaluation ? ` · reevaluation ${words(cycle.reevaluation.cycle_status)} · positions ${cycle.reevaluation.position_count} · candidates ${cycle.reevaluation.candidate_count} · model calls ${cycle.reevaluation.model_call_count}` : " · no evaluation ran"}</p>
            {cycle.actions.length > 0 && <ul>{cycle.actions.map((action) => <li key={`${action.decision_id}-${action.outcome}`}>{action.instrument_id} · {action.action} · {words(action.outcome)}{action.side ? ` · ${action.side} ${text(action.quantity)}` : ""}{action.order_state ? ` · order ${action.order_state} · filled ${text(action.filled_quantity)}${action.fill_price_minor != null ? ` at ${money(action.fill_price_minor)} (simulated)` : ""}` : ""} · {action.reason_codes.join(", ")}</li>)}</ul>}
          </> : <p>No cycle has run.</p>}

          <h4>Overnight positions</h4>
          <p>Approved to hold: {Object.keys(status.carry?.approved ?? {}).join(", ") || "none"}.</p>
          <p>Last cycle carry snapshot: {Object.keys(status.carry?.pending ?? {}).join(", ") || "none"}. This is the saved controller cycle, not the current ledger.</p>
          {(status.carry_ledger?.pending_still_open.length ?? 0) > 0 && <p>Still open on the ledger: {status.carry_ledger!.pending_still_open.join(", ")}.</p>}
          {(status.carry_ledger?.pending_absent_from_ledger.length ?? 0) > 0 && <p>Recorded in that snapshot and absent from the current ledger: {status.carry_ledger!.pending_absent_from_ledger.join(", ")}.</p>}
          <h4>Risk and Paper account</h4>
          {status.risk && <p>Open positions {status.risk.open_positions}/{status.risk.max_open_positions} · exposure {money(status.risk.exposure_minor)} of {money(status.risk.max_aggregate_exposure_minor)} · day P&amp;L {money(status.risk.day_pnl_minor)} (halt at −{money(status.risk.max_daily_loss_minor)}) · equity {money(status.risk.equity_minor)} · realized {money(status.risk.realized_pnl_minor)} · unrealized {money(status.risk.unrealized_pnl_minor)} · valuation {text(status.risk.valuation_quality)}</p>}
          {(status.positions?.length ?? 0) > 0 ? <table><caption>Open Paper positions</caption>
            <thead><tr><th scope="col">Instrument</th><th scope="col">Side</th><th scope="col">Quantity</th><th scope="col">Average fill</th><th scope="col">Mark</th><th scope="col">Unrealized</th></tr></thead>
            <tbody>{status.positions!.map((position) => <tr key={position.instrument_id}><th scope="row">{position.instrument_id}</th><td>{text(position.side)}</td><td>{position.quantity}</td>
              <td>{money(position.average_fill_minor)}</td><td>{money(position.mark_minor)}</td><td>{money(position.unrealized_pnl_minor)}</td></tr>)}</tbody></table> : <p>No open Paper positions.</p>}
          {(status.working_orders?.length ?? 0) > 0 && <p>Working orders: {status.working_orders!.map((order) => `${order.instrument_id} ${order.side} ${order.state}`).join("; ")}</p>}

          <h4>Decisions and orders (latest {status.recent_intents?.length ?? 0})</h4>
          {(status.recent_intents?.length ?? 0) > 0 ? <ul>{status.recent_intents!.map((intent) => <li key={intent.intent_id}>{intent.updated_at} · {intent.instrument_id} · {intent.action} · <strong>{words(intent.state)}</strong>{intent.side ? ` · ${intent.side} ${text(intent.quantity)}` : ""}{intent.order_state ? ` · order ${intent.latest_order_state ?? intent.order_state}${intent.latest_order_state && intent.latest_order_state !== intent.order_state ? ` (${intent.order_state} when decided)` : ""} · filled ${text(intent.filled_quantity)}` : ""} · {intent.decision_origin === "DETERMINISTIC_RISK_CONTROL" ? "deterministic risk control" : "gated model proposal"} · {intent.reason_codes.join(", ")}</li>)}</ul> : <p>No automated decision has reached the Paper adapter.</p>}

          {unread.report && <p role="alert">Simulated results are unavailable: the report read failed. This says nothing about the account itself; reopen the panel to retry.</p>}
          {report && <>
            <h4>Simulated results</h4>
            <p>{report.statement}</p>
            <p>Fills {report.fills.count} ({report.fills.opening} opening, {report.fills.closing} closing) · costs {money(report.fills.costs_minor)} · realized {money(report.outcomes.realized_pnl_minor)} · wins {report.outcomes.wins} · losses {report.outcomes.losses} · equity {money(report.portfolio.equity_minor)} · total P&amp;L {money(report.portfolio.total_pnl_minor)} · drawdown over recent snapshots {money(report.portfolio.max_drawdown_minor_last_snapshots)}</p>
            <p>Decisions {report.decisions.intents}: {report.decisions.submitted} submitted, {report.decisions.refused_or_deferred} refused or deferred{Object.keys(report.decisions.refusal_reasons).length ? ` (${Object.entries(report.decisions.refusal_reasons).map(([code, count]) => `${code} ×${count}`).join(", ")})` : ""} · AI universe runs {report.ai.universe_runs} ({report.ai.incomplete_runs} incomplete) · tokens in {report.ai.tokens_input} / out {report.ai.tokens_output}</p>
            <p>{report.outcomes.sample_note}</p>
          </>}

          <h4>Audit history (latest {events.length})</h4>
          {unread.history && <p role="alert">Audit history is unavailable: the history read failed. This does not mean no events were recorded{events.length ? "; the rows below are the last successful read" : ""}.</p>}
          {events.length ? <ol reversed>{events.map((event) => <EventRow key={event.sequence} event={event} />)}</ol> : !unread.history && <p>No events recorded.</p>}
        </>}
      </>}
    </>}
  </section>;
}

import type { SmaStopStatus } from "../../api/paperRiskControl";

export type TrailingStopRow = { id: string; label: string; value: string; detail?: string };
export type TrailingStopModel = {
  status: SmaStopStatus["status"];
  statusLabel: string;
  /** Direction is always stated in words; it is never left to be inferred from an inequality. */
  directionLabel: string | null;
  rows: TrailingStopRow[];
  messages: string[];
  breach: { stop: string; trigger: string; observedAt: string; decision: string; decisionId: string | null; paperClose: string; canPrepareExit: boolean; blockers: string[] } | null;
  canEvaluate: boolean;
};

const STATUS_LABEL: Record<SmaStopStatus["status"], string> = {
  NOT_CONFIGURED: "Not configured",
  WARMING_UP: "Warming up",
  ACTIVE: "Active",
  STALE: "Stop update stale",
  BLOCKED: "Blocked",
  BREACHED: "SMA stop breached",
  CLOSED: "Closed",
};
const UNAVAILABLE = "Unavailable";

const eastern = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const easternDate = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" });

export function formatStopTime(value: string | null | undefined): string {
  if (!value) return UNAVAILABLE;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? UNAVAILABLE : `${easternDate.format(parsed)} ${eastern.format(parsed)} ET`;
}

/** Server prices arrive as exact decimal strings; this only pads cents and never recomputes a level. */
export function formatStopPrice(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return UNAVAILABLE;
  const [whole, fraction = ""] = value.split(".");
  return `$${whole}.${fraction.padEnd(2, "0")}`;
}

export function buildPaperTrailingStopModel(status: SmaStopStatus): TrailingStopModel {
  const { stop, policy, position, monitoring } = status;
  const side = stop?.side ?? (position && position.state !== "FLAT" ? position.state : null);
  const rows: TrailingStopRow[] = [];
  const messages: string[] = [];
  const window = stop?.sma_window_bars ?? policy?.sma_window_bars;
  const interval = stop?.bar_interval ?? policy?.bar_interval;
  const label = stop?.config_label ?? policy?.config_label;

  rows.push({ id: "position", label: "Position", value: position ? (position.state === "FLAT" ? "Flat" : `${position.state} ${position.quantity}`) : UNAVAILABLE,
    detail: "Paper ledger quantity" });
  if (policy || stop) {
    rows.push({ id: "policy", label: "Policy", value: "SMA trailing stop / v1", detail: stop?.policy_id ?? policy?.policy_id });
    rows.push({ id: "window", label: "Window", value: `${window} completed ${interval} bars`,
      detail: label === "REFERENCE_TEST_CONFIG" ? "reference test configuration — not optimized" : "operator-bounded configuration — not optimized" });
  }
  if (stop) {
    rows.push({ id: "sma", label: "Current SMA", value: formatStopPrice(stop.sma_value), detail: stop.bar_available_at ? `bar complete ${formatStopTime(stop.bar_available_at)}` : undefined });
    rows.push({ id: "candidate", label: "Candidate stop", value: formatStopPrice(stop.candidate_stop) });
    rows.push({ id: "active", label: "Active stop", value: formatStopPrice(stop.active_stop), detail: side ? `${side} stop` : undefined });
    rows.push({ id: "previous", label: "Previous stop", value: stop.previous_stop ? formatStopPrice(stop.previous_stop) : "None" });
    rows.push({ id: "distance", label: "Distance to stop", value: stop.distance_to_stop ? `${formatStopPrice(stop.distance_to_stop)} (${stop.distance_bps} bps)` : UNAVAILABLE,
      detail: stop.reference_price ? `last trade ${formatStopPrice(stop.reference_price)} as of ${formatStopTime(stop.reference_as_of)}` : "no admissible current price" });
    rows.push({ id: "updated", label: "Last updated", value: formatStopTime(stop.last_updated_at), detail: `activated ${formatStopTime(stop.activated_at)} · ${stop.activation_reason}` });
  }
  if (monitoring) {
    rows.push({ id: "monitoring", label: "Monitoring", value: monitoring.state === "RUNNING" ? "RUNNING" : "NOT RUNNING",
      detail: `last evaluated ${formatStopTime(monitoring.last_evaluated_at)} · ${monitoring.liveness}` });
  }

  if (status.status === "NOT_CONFIGURED") messages.push("No SMA trailing stop is configured for this Paper account. Nothing is being monitored.");
  if (status.status === "WARMING_UP" && status.reason_codes.includes("NOT_YET_EVALUATED")) {
    messages.push(`Not yet evaluated for this position${window ? ` — ${window} completed bars required` : ""}. No stop exists yet.`);
  } else if (status.status === "WARMING_UP") {
    messages.push(window ? `Warming up — ${window} completed bars required${stop ? `; ${stop.bars_available} available` : ""}. No stop exists yet.` : "Warming up. No stop exists yet.");
  }
  if (status.reason_codes.includes("MONOTONIC_CLAMP")) messages.push("Stop held at previous level — trailing rule does not loosen protection.");
  if (status.status === "STALE") {
    messages.push(`Stop update stale — last legitimate stop ${formatStopPrice(stop?.active_stop)}, last bar ${formatStopTime(stop?.bar_available_at)}. Reason: ${status.reason_codes.filter((code) => code !== "STOP_UPDATE_STALE").join(", ") || "unknown"}.`);
  }
  if (status.status === "BLOCKED") messages.push(`Stop cannot be computed: ${status.reason_codes.join(", ")}. No stop is in force.`);
  if (stop?.trigger_state === "TRIGGER_UNAVAILABLE") {
    messages.push(`Trigger unavailable — revalidation required (${stop.trigger_reason_codes.filter((code) => code !== "REVALIDATION_REQUIRED").join(", ") || "no admissible current price"}). The stop is neither confirmed breached nor confirmed safe.`);
  }
  if (stop?.activation_reason === "LATE_ACTIVATION") messages.push(`Late activation — this stop began ${formatStopTime(stop.activated_at)}, not at position entry.`);
  if (monitoring?.liveness === "NOT_OBSERVED") messages.push("Not observed — the stop was not evaluated for an interval. No protection is claimed for that time.");
  if (monitoring && monitoring.state !== "RUNNING" && stop && status.status !== "CLOSED") messages.push("Reevaluation is not running: the stop is checked only when you choose Evaluate Stop Now.");
  if (status.status === "CLOSED") messages.push(stop?.closed_reason ? `Stop episode closed: ${stop.closed_reason}.` : "No open position. No stop is in force.");
  if (status.exit_decision_error) messages.push(`Breach recorded, but the EXIT decision could not be written: ${status.exit_decision_error}.`);

  const decision = stop?.exit_decision ?? null;
  const breach = status.status === "BREACHED" && stop ? {
    stop: formatStopPrice(stop.active_stop),
    trigger: formatStopPrice(stop.trigger_price),
    observedAt: formatStopTime(stop.triggered_at),
    decision: decision ? decision.action_state : "EXIT decision not yet recorded",
    decisionId: decision?.decision_id ?? null,
    paperClose: "NOT SUBMITTED",
    canPrepareExit: Boolean(decision && decision.action_state === "EXIT" && decision.execution_readiness === "PREVIEW_ALLOWED"),
    blockers: decision?.blocker_codes ?? [],
  } : null;

  return {
    status: status.status,
    statusLabel: STATUS_LABEL[status.status],
    directionLabel: stop && side ? `${side} stop` : null,
    rows,
    messages,
    breach,
    canEvaluate: status.status !== "NOT_CONFIGURED" && position !== null && position.state !== "FLAT",
  };
}

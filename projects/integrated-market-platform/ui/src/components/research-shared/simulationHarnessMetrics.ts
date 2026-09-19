import type { ResearchSimulationResponse } from "../../api/schemas";

export type SimulationHarnessMetric = {
  id: string;
  label: string;
  value: string;
  evidenceClass: "simulation" | "historical_research" | "unavailable";
  detail?: string;
};

function readMetric(record: Record<string, unknown> | undefined, keys: string[]): string | null {
  if (!record) return null;
  for (const key of keys) {
    const value = record[key];
    if (value === null || value === undefined || value === "") continue;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return null;
}

/**
 * Surfaces drawdown, cost-sensitivity, and fill-price realism only when the
 * simulation contract carries them. Never implies production trading guarantees.
 */
export function extractSimulationHarnessMetrics(
  payload: ResearchSimulationResponse | null | undefined,
): SimulationHarnessMetric[] {
  if (!payload) return [];

  const ledger = payload.ledger_summary as Record<string, unknown>;
  const fillAudit = (payload.fill_audit ?? {}) as Record<string, unknown>;
  const reconciliation = (payload.reconciliation ?? {}) as Record<string, unknown>;

  const metrics: SimulationHarnessMetric[] = [];

  const drawdown =
    readMetric(ledger, ["max_drawdown", "drawdown"]) ??
    readMetric(fillAudit, ["max_drawdown", "drawdown"]) ??
    readMetric(reconciliation, ["max_drawdown"]);
  metrics.push({
    id: "drawdown",
    label: "Max drawdown (simulation)",
    value: drawdown ?? "UNAVAILABLE",
    evidenceClass: drawdown ? "simulation" : "unavailable",
    detail: drawdown
      ? "Replay-window simulator metric — not forward-test or live P&L."
      : "Not projected on /research/simulation yet (Lane C).",
  });

  const costSensitivity =
    readMetric(fillAudit, ["cost_sensitivity_status", "cost_sensitivity_v4_status"]) ??
    readMetric(reconciliation, ["cost_sensitivity_status"]);
  metrics.push({
    id: "cost-sensitivity",
    label: "Cost sensitivity harness",
    value: costSensitivity ?? "UNAVAILABLE",
    evidenceClass: costSensitivity ? "historical_research" : "unavailable",
    detail: "Historical research artifact — not a production cost guarantee.",
  });

  const fillRealism =
    readMetric(fillAudit, ["fill_price_realism_status", "fill_realism_status", "status"]) ??
    readMetric(fillAudit, ["fill_price_realism"]);
  metrics.push({
    id: "fill-realism",
    label: "Fill-price realism audit",
    value: fillRealism ?? displayFillAuditStatus(fillAudit),
    evidenceClass: fillRealism ? "simulation" : "unavailable",
    detail: "Bar-conservative fill audit for the current replay snapshot.",
  });

  return metrics;
}

function displayFillAuditStatus(fillAudit: Record<string, unknown>): string {
  const status = fillAudit.status;
  return status == null || status === "" ? "UNAVAILABLE" : String(status);
}

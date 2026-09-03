import { z } from "zod";
import { ProviderHealthResponseSchema } from "../../api/schemas";
import type { LiveCanarySnapshot } from "./liveCanarySnapshot";

export type ProviderHealthResponse = z.infer<typeof ProviderHealthResponseSchema>;

export type LiveMetric = {
  id: string;
  label: string;
  value: string;
  detail?: string;
};

export type LiveSafetyAlert = {
  severity: number;
  title: string;
  detail: string;
};

export function channelHealthLabel(entitled?: boolean, tested?: boolean): string {
  if (!entitled) return "UNAVAILABLE";
  return tested ? "HEALTHY" : "DEGRADED";
}

export function liveConnectionMetrics(health?: ProviderHealthResponse): LiveMetric[] {
  if (!health?.available) {
    return [
      {
        id: "observational",
        label: "Observational mode",
        value: "UNAVAILABLE",
        detail: health?.reason ?? "Live observational data is not enabled.",
      },
    ];
  }

  const lifecycle = health.lifecycle ?? {};
  const summary = health.provider_summary ?? {};
  const capabilities = health.capability_registry?.capabilities ?? {};
  const l1 = capabilities.US_EQUITY_L1;
  const trades = capabilities.US_EQUITY_TICKER;
  const depth = capabilities.US_EQUITY_DEPTH;
  const executionUse =
    lifecycle.execution_use === "INTERNAL_PAPER_ELIGIBLE" ? "INTERNAL_PAPER_ELIGIBLE" : "DISPLAY_ONLY";

  return [
    {
      id: "connection",
      label: "Connection",
      value: String(lifecycle.connection_state ?? summary.opend ?? "UNKNOWN"),
      detail: String(summary.provider ?? "MOOMOO"),
    },
    {
      id: "session",
      label: "Market session",
      value: String(lifecycle.market_session ?? "—"),
    },
    {
      id: "quota",
      label: "Subscription quota",
      value: `${health.quota?.active_count ?? 0} / ${health.quota?.max_quota ?? "?"}`,
    },
    {
      id: "quote",
      label: "Basic quote",
      value: channelHealthLabel(Boolean(l1?.account_entitled), Boolean(l1?.runtime_tested)),
    },
    {
      id: "trades",
      label: "Trades",
      value: channelHealthLabel(Boolean(trades?.account_entitled), Boolean(trades?.runtime_tested)),
    },
    {
      id: "depth",
      label: "L2 depth",
      value: channelHealthLabel(Boolean(depth?.account_entitled), Boolean(depth?.runtime_tested)),
    },
    {
      id: "execution",
      label: "Execution eligibility",
      value: String(summary.execution_eligibility ?? executionUse),
    },
    {
      id: "lag",
      label: "Quote lag p50 / p95",
      value: `${String(summary.quote_lag_ms_p50 ?? "—")} / ${String(summary.quote_lag_ms_p95 ?? "—")} ms`,
    },
  ];
}

export function liveSafetyAlerts(snapshot?: LiveCanarySnapshot): LiveSafetyAlert[] {
  if (!snapshot) return [];

  const alerts: LiveSafetyAlert[] = [];

  if (snapshot.live_blocked) {
    alerts.push({
      severity: 0,
      title: "Live execution blocked",
      detail: snapshot.block_reasons.length
        ? snapshot.block_reasons.join(" · ")
        : "Backend reports live execution is blocked.",
    });
  }

  for (const switchName of ["kill_switch_global", "kill_switch_program", "kill_switch_session"] as const) {
    const value = snapshot[switchName];
    if (value && value !== "OFF" && value !== "INACTIVE" && value !== "CLEAR") {
      alerts.push({
        severity: 0,
        title: `${switchName.replace(/_/g, " ")} active`,
        detail: value,
      });
    }
  }

  if (snapshot.broker_health && !["HEALTHY", "OK", "PASS"].includes(snapshot.broker_health.toUpperCase())) {
    alerts.push({
      severity: 1,
      title: "Broker health degraded",
      detail: snapshot.broker_health,
    });
  }

  if (
    snapshot.reconciliation_health &&
    !["HEALTHY", "OK", "PASS", "RECONCILED"].includes(snapshot.reconciliation_health.toUpperCase())
  ) {
    alerts.push({
      severity: 1,
      title: "Reconciliation attention required",
      detail: snapshot.reconciliation_health,
    });
  }

  if ((snapshot.incident_summary.critical_open ?? 0) > 0) {
    alerts.push({
      severity: 0,
      title: "Critical incidents open",
      detail: `${snapshot.incident_summary.critical_open} critical · ${snapshot.incident_summary.open ?? 0} total open`,
    });
  }

  for (const incidentId of snapshot.unresolved_critical_incidents.slice(0, 3)) {
    alerts.push({
      severity: 0,
      title: "Unresolved critical incident",
      detail: incidentId,
    });
  }

  return alerts.slice(0, 5);
}

export function liveSafetySummary(snapshot?: LiveCanarySnapshot): LiveMetric[] {
  if (!snapshot) return [];

  return [
    { id: "live-blocked", label: "Live blocked", value: snapshot.live_blocked ? "YES" : "NO" },
    { id: "broker", label: "Broker", value: snapshot.broker ?? "—" },
    { id: "environment", label: "Account environment", value: snapshot.account_environment ?? "—" },
    { id: "broker-health", label: "Broker health", value: snapshot.broker_health },
    { id: "reconciliation", label: "Reconciliation", value: snapshot.reconciliation_health },
    { id: "program", label: "Program state", value: snapshot.program_state ?? "—" },
    { id: "session", label: "Session state", value: snapshot.session_state ?? "—" },
    {
      id: "authorization",
      label: "Authorization",
      value: snapshot.authorization_status ?? "NONE",
    },
  ];
}

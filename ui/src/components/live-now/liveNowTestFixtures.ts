import { z } from "zod";
import { ProviderHealthResponseSchema } from "../../api/schemas";
import type { LiveCanarySnapshot } from "./liveCanarySnapshot";

export function providerHealth(
  overrides: Partial<z.infer<typeof ProviderHealthResponseSchema>> = {},
): z.infer<typeof ProviderHealthResponseSchema> {
  return {
    available: true,
    data_mode: "LIVE_OBSERVATIONAL",
    lifecycle: {
      connection_state: "CONNECTED",
      provider_role: "MARKET_DATA",
      execution_use: "DISPLAY_ONLY",
      market_session: "REGULAR",
      reconnect_count: 0,
      active_subscriptions: [{ instrument_id: "AAPL", capability: "BASIC_QUOTE", consumer_count: 1 }],
    },
    quota: { active_count: 2, max_quota: 50, remaining: 48 },
    provider_summary: {
      provider: "MOOMOO",
      execution_eligibility: "DISPLAY_ONLY",
      quote_lag_ms_p50: 12,
      quote_lag_ms_p95: 28,
    },
    capability_registry: {
      capabilities: {
        US_EQUITY_L1: { account_entitled: true, runtime_tested: true },
        US_EQUITY_TICKER: { account_entitled: true, runtime_tested: true },
        US_EQUITY_DEPTH: { account_entitled: false, runtime_tested: false },
      },
    },
    ...overrides,
  };
}

export function canarySnapshot(overrides: Partial<LiveCanarySnapshot> = {}): LiveCanarySnapshot {
  return {
    live_blocked: true,
    block_reasons: ["HUMAN_CONFIRMATION_REQUIRED"],
    execution_mode_label: "LIVE_CANARY",
    program_state: "ARMED",
    session_state: "IDLE",
    broker: "MOOMOO",
    account_environment: "PAPER_BROKER",
    broker_health: "HEALTHY",
    reconciliation_health: "RECONCILED",
    kill_switch_global: "OFF",
    kill_switch_program: "OFF",
    kill_switch_session: "OFF",
    authorization_status: null,
    incident_summary: { open: 0, critical_open: 0 },
    unresolved_critical_incidents: [],
    ...overrides,
  };
}

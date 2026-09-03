export type LiveCanarySnapshot = {
  live_blocked: boolean;
  block_reasons: string[];
  execution_mode_label: string;
  program_state: string | null;
  session_state: string | null;
  broker: string | null;
  account_environment: string | null;
  account_fingerprint?: string | null;
  broker_health: string;
  reconciliation_health: string;
  kill_switch_global: string;
  kill_switch_program: string;
  kill_switch_session: string;
  authorization_status: string | null;
  incident_summary: Record<string, number>;
  unresolved_critical_incidents: string[];
  live_positions?: Array<Record<string, unknown>>;
  open_broker_orders?: Array<Record<string, unknown>>;
  ambiguous_states?: string[];
  program_cap_usage?: Record<string, number>;
  program_cap_remaining?: Record<string, number>;
  as_of_ns?: number;
  snapshot_id?: string;
};

export type LiveCanaryReconciliation = {
  reconciliation_health: string;
  local_open_orders: string[];
  ambiguous_states: string[];
};

const DEFAULT_ACCOUNT = "fp-canary-local";

async function fetchCanaryJson<T>(path: string, accountId = DEFAULT_ACCOUNT): Promise<T> {
  const response = await fetch(`${path}?account_id=${encodeURIComponent(accountId)}`);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function fetchLiveCanarySnapshot(accountId = DEFAULT_ACCOUNT): Promise<LiveCanarySnapshot> {
  const payload = await fetchCanaryJson<{ snapshot: LiveCanarySnapshot }>("/canary/snapshot", accountId);
  return payload.snapshot;
}

export async function fetchLiveCanaryReconciliation(accountId = DEFAULT_ACCOUNT): Promise<LiveCanaryReconciliation> {
  return fetchCanaryJson<LiveCanaryReconciliation>("/canary/reconciliation", accountId);
}

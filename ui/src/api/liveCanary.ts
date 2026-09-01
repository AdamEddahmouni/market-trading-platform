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

type SnapshotPayload = {
  snapshot: LiveCanarySnapshot;
};

export async function fetchLiveCanarySnapshot(): Promise<LiveCanarySnapshot> {
  const response = await fetch("/canary/snapshot");
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  const payload = (await response.json()) as SnapshotPayload;
  return payload.snapshot;
}

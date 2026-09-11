import type { QueryMode } from "../../api/canonicalQueryKey";
import { canonicalQueryKey } from "../../api/canonicalQueryKey";

export type ForwardTestDecisionState =
  | "DRAFT"
  | "LOCKED"
  | "PAPER_SUBMITTED"
  | "PAPER_ACTIVE"
  | "OBSERVING"
  | "EVALUABLE"
  | "EVALUATED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "INVALID"
  | "INSUFFICIENT_DATA";

export type ForwardTestRecord = {
  forward_test_id: string;
  session_id: string | null;
  account_id: string;
  mode: string;
  run_kind: "FORWARD_TEST" | "BACKTEST";
  test_mode: "SIGNAL_ONLY" | "EXECUTION";
  symbol: string;
  decision_time_ns: number;
  source_time_ns: number;
  state: ForwardTestDecisionState;
  direction: string;
  quantity: number | null;
  strategy_id: string;
  strategy_version: string;
  evaluation_horizon_ns: number;
  paper_order_id: string | null;
  evaluation_state: string;
  signal_outcome?: {
    directional_correct: boolean | null;
    percentage_return: number | null;
    quality: string;
  } | null;
  execution_outcome?: {
    quality: string;
  } | null;
  failure_reason?: string | null;
};

export type ForwardTestPanelModel = {
  hasRecords: boolean;
  records: ForwardTestRecord[];
  pendingCount: number;
  evaluatedCount: number;
  rejectedCount: number;
  label: string;
  modeLabel: string;
  emptyMessage: string;
};

export function forwardTestQueryKey(mode: QueryMode, accountId?: string) {
  return canonicalQueryKey("pft", { mode, accountId: accountId ?? "unbound" });
}

export function buildForwardTestPanelModel(records: ForwardTestRecord[] | undefined): ForwardTestPanelModel {
  const rows = records ?? [];
  const pendingCount = rows.filter((row) =>
    ["DRAFT", "LOCKED", "PAPER_SUBMITTED", "PAPER_ACTIVE", "OBSERVING", "EVALUABLE"].includes(row.state),
  ).length;
  const evaluatedCount = rows.filter((row) => row.state === "EVALUATED").length;
  const rejectedCount = rows.filter((row) =>
    ["REJECTED", "INVALID", "INSUFFICIENT_DATA"].includes(row.state),
  ).length;
  return {
    hasRecords: rows.length > 0,
    records: rows,
    pendingCount,
    evaluatedCount,
    rejectedCount,
    label: "Forward Test",
    modeLabel: "PAPER",
    emptyMessage: "No forward-test decisions yet. Locked prospective decisions appear here after creation.",
  };
}

export function formatForwardTestState(state: ForwardTestDecisionState): string {
  if (state === "EVALUATED") return "Evaluated";
  if (state === "REJECTED") return "Rejected";
  if (state === "INSUFFICIENT_DATA") return "Insufficient data";
  if (state === "OBSERVING" || state === "EVALUABLE") return "Pending";
  if (state === "LOCKED") return "Locked";
  return state.replace(/_/g, " ").toLowerCase();
}

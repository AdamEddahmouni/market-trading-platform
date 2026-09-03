import type { Mode } from "../mode-session/types";
import type { WorkspaceModuleId } from "../WorkspaceModuleNav";

const PAPER_HINTS: Partial<Record<WorkspaceModuleId, string>> = {
  squeeze:
    "Preview squeeze ignition before drafting paper orders from the workspace overview.",
  "order-flow":
    "Use CVD evidence to inform paper order sizing from the workspace overview.",
  "order-book":
    "Review depth imbalance before paper order preview from the workspace overview.",
  futures: "Factor macro backdrop into paper simulation from the workspace overview.",
  catalyst: "Factor catalyst events into paper thesis from the workspace overview.",
  "fund-etf": "Use ETF flow proxies for cross-asset paper context from the workspace overview.",
  options: "Use unusual activity to inform paper sizing from the workspace overview.",
  "large-transactions":
    "Use size prints for paper context from the workspace overview.",
  disclosure: "Use filing events for paper research from the workspace overview.",
  "institutional-flow":
    "Use whale evidence for paper thesis from the workspace overview.",
};

const LIVE_HINTS: Partial<Record<WorkspaceModuleId, string>> = {
  squeeze: "Monitor broker-observed squeeze signals without execution authority.",
  "order-flow": "Observe broker-reported order flow — no trade authority on this lane.",
  "order-book": "Visible liquidity is broker-observed — read-only on this lane.",
  futures: "ES depth is observational — not live CFTC positioning.",
  catalyst: "Public catalyst bridge is read-only in live context.",
  "fund-etf": "Fund-flow proxies are observational in live mode.",
  options: "Options activity is broker-observed — no execution on this lane.",
  "large-transactions": "Large prints are observational — not directional intent.",
  disclosure: "Delayed filings remain read-only in live context.",
  "institutional-flow": "Institutional flow is observational — aggressor unknown.",
};

const DEFAULT_PAPER_HINT =
  "Route lane evidence into paper simulation from the workspace overview.";
const DEFAULT_LIVE_HINT =
  "Broker-observed context without execution authority on this lane.";

export function workspaceModuleModeDescription(
  base: string,
  mode: Mode,
  moduleId: WorkspaceModuleId,
): string {
  if (mode === "PAPER") {
    const hint = PAPER_HINTS[moduleId] ?? DEFAULT_PAPER_HINT;
    return `${base} ${hint}`;
  }
  if (mode === "LIVE") {
    const hint = LIVE_HINTS[moduleId] ?? DEFAULT_LIVE_HINT;
    return `${base} ${hint}`;
  }
  return base;
}

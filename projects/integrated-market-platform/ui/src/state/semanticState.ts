/**
 * Canonical semantic state adapter.
 * Binding design guidance: docs/ui-redesign-v2/semantic-state-system.md.
 *
 * THE single entry point for rendering backend enum/state vocabularies. The UI
 * translates, never invents: mapped values render the human language from the
 * domain tables below; unmapped/unknown values render `neutral` with the raw
 * string preserved (`state.raw`) and a dev-mode console warning — never a
 * guessed sentence, never a throw. (Presentation must not fail-closed on
 * *display*; fail-closed applies to *mutations*.)
 *
 * The adapter never computes operational state; it translates backend-emitted
 * state only. Authority gating stays in `mode-session/modeAuthority.ts`.
 */

export type SemanticTone =
  | "live"
  | "paper"
  | "replay"
  | "research"
  | "caution"
  | "critical"
  | "neutral";

export type SemanticState = {
  tone: SemanticTone;
  /** Short human label, e.g. "Paper orders only". */
  label: string;
  /** Full human sentence for banners/L1. */
  sentence?: string;
  /** 3-question rule: what it affects. */
  affects?: string;
  /** 3-question rule: what to do. */
  action?: { label: string; href?: string };
  /** Original backend value, always preserved for L4. */
  raw: string;
};

export type StateDomain =
  | "mode"
  | "session"
  | "executionAuthority"
  | "providerHealth"
  | "dataHealth"
  | "portfolio"
  | "research"
  | "platform"
  | "action"
  | "error";

export type SemanticStateParams = Record<string, string | number | null | undefined>;

export type ResolveOptions = {
  /** Payload values for {placeholder} interpolation in templates. */
  params?: SemanticStateParams;
};

type Entry = {
  tone: SemanticTone;
  label: string;
  sentence?: string;
  affects?: string;
  action?: { label: string; href?: string };
  /** Param-free rendering used when a {placeholder} value is missing. */
  fallback?: string;
};

/** Mechanical humanization of an enum string — not a guessed sentence. */
export function humanizeEnum(raw: string): string {
  const text = raw.trim().replace(/_/g, " ").replace(/\s+/g, " ");
  if (!text) return "Unknown";
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

function devWarn(message: string): void {
  if (typeof import.meta !== "undefined" && import.meta.env?.DEV) {
    console.warn(`[semanticState] ${message}`);
  }
}

function fill(template: string, params: SemanticStateParams): string | undefined {
  let missing = false;
  const out = template.replace(/\{(\w+)\}/g, (_match, key: string) => {
    const value = params[key];
    if (value === undefined || value === null || value === "") {
      missing = true;
      return "";
    }
    return String(value);
  });
  return missing ? undefined : out;
}

function renderEntry(entry: Entry, raw: string, params: SemanticStateParams): SemanticState {
  const label = fill(entry.label, params) ?? entry.fallback ?? humanizeEnum(raw);
  const sentence = entry.sentence
    ? (fill(entry.sentence, params) ?? entry.fallback ?? label)
    : undefined;
  const affects = entry.affects ? fill(entry.affects, params) : undefined;
  return {
    tone: entry.tone,
    label,
    sentence,
    affects,
    action: entry.action,
    raw,
  };
}

/* -------------------------------------------------------------------------- */
/* Domain tables (docs/ui-redesign-v2/semantic-state-system.md §3)             */
/* -------------------------------------------------------------------------- */

const MODE_TABLE: Record<string, Entry> = {
  DEMO: {
    tone: "replay",
    label: "Demo replay",
    sentence: "Demo replay — trading disabled. Recorded market data.",
  },
  PAPER: {
    tone: "paper",
    label: "Paper trading",
    sentence: "Paper trading active — simulated fills, no real money.",
  },
  LIVE: {
    tone: "live",
    label: "Live observation",
    sentence: "Live market data — read-only, execution locked.",
  },
  REPLAY: { tone: "replay", label: "Replay" },
  SIMULATION: { tone: "paper", label: "Simulation" },
  compatible: { tone: "live", label: "Backend aligned" },
  mismatch: {
    tone: "critical",
    label: "UI and backend disagree",
    sentence:
      "The selected UI mode and the backend context disagree. UI mode selection does not change backend authority. Switch mode or restart the backend session.",
  },
  unavailable: {
    tone: "caution",
    label: "Backend context unavailable",
    sentence: "Backend context unavailable. Execution controls remain locked.",
    action: { label: "Open Control", href: "/control#control-authority" },
  },
};

const SESSION_TABLE: Record<string, Entry> = {
  FIXTURE_REPLAY: { tone: "replay", label: "Demo replay (recorded data)" },
  HISTORICAL_CAPTURE: { tone: "replay", label: "Historical capture (recorded data)" },
  LIVE_OBSERVATIONAL: {
    tone: "live",
    label: "Live market data · {provider}",
    fallback: "Live market data",
  },
  BROKER_DELAYED: {
    tone: "caution",
    label: "Delayed broker data",
    sentence: "Delayed broker data — quotes may lag.",
  },
  OPEN_SESSION_DETECTED: {
    tone: "caution",
    label: "Previous paper session detected",
    sentence:
      "A previous paper session was restored. Positions rebuild from events; live marks wait for fresh data. No action needed.",
  },
  CORRUPT_DB: {
    tone: "critical",
    label: "Local state database failed integrity check",
    sentence:
      "The local state database failed an integrity check. The original file was preserved. Trading state may be incomplete.",
    action: { label: "Open Settings", href: "/settings" },
  },
  OPEN: { tone: "paper", label: "Paper session open · started {date}", fallback: "Paper session open" },
  CLOSED: { tone: "neutral", label: "Session closed {date}", fallback: "Session closed" },
};

const EXECUTION_AUTHORITY_TABLE: Record<string, Entry> = {
  NONE: { tone: "neutral", label: "No execution" },
  INTERNAL_SIMULATION: { tone: "paper", label: "Paper trading (simulated fills)" },
  BROKER_PAPER: { tone: "paper", label: "Broker paper trading" },
  LIVE: { tone: "critical", label: "LIVE EXECUTION — real money" },
  BLOCKED: { tone: "neutral", label: "No trading authority" },
  PAPER_ONLY: { tone: "paper", label: "Paper orders only" },
  AUTHORIZED: { tone: "caution", label: "Execution authorized" },
  DISPLAY_ONLY: { tone: "neutral", label: "Market data only — cannot route orders" },
  INTERNAL_PAPER_ELIGIBLE: { tone: "paper", label: "Eligible for paper simulation" },
  PASS: { tone: "live", label: "Preview passed risk checks" },
  APPROVE: { tone: "live", label: "Approved" },
  RESIZE: { tone: "caution", label: "Approved with reduced size" },
  REJECT: { tone: "critical", label: "Rejected" },
  WAITING_FOR_ELIGIBLE_LIVE_EVENT: {
    tone: "caution",
    label: "Waiting for a fresh market event — preview may be stale",
  },
  NO_EXECUTABLE_BAR: {
    tone: "caution",
    label: "No executable price bar — preview is indicative only",
  },
  PREVIEW_EXPIRED: { tone: "caution", label: "Preview expired — re-preview before submitting" },
  PREVIEW_INTENT_MISMATCH: {
    tone: "critical",
    label: "Order changed since preview — re-preview required",
  },
  PREVIEW_PORTFOLIO_STALE: {
    tone: "caution",
    label: "Portfolio changed since preview — re-preview required",
  },
  PREVIEW_POLICY_STALE: {
    tone: "caution",
    label: "Risk policy changed since preview — re-preview required",
  },
  PREVIEW_MARGIN_STALE: {
    tone: "caution",
    label: "Margin data changed since preview — re-preview required",
  },
  PREVIEW_REQUIRED: {
    tone: "critical",
    label: "A current preview is required before submitting",
  },
  NOT_PREVIEWED: { tone: "neutral", label: "Not previewed yet" },
  PREVIEWING: { tone: "neutral", label: "Previewing…" },
  ACCEPTED: { tone: "live", label: "Preview accepted — ready to submit" },
  REJECTED: { tone: "critical", label: "Preview rejected" },
  REVALIDATION_REQUIRED: { tone: "caution", label: "Re-preview required" },
  AUTHORITY_UNAVAILABLE: { tone: "critical", label: "Trading authority unavailable — ticket locked" },
  ERROR: { tone: "critical", label: "Preview failed" },
};

const PROVIDER_HEALTH_TABLE: Record<string, Entry> = {
  CONNECTED: { tone: "live", label: "{provider} — connected", fallback: "Connected" },
  CONNECTED_DEGRADED: {
    tone: "caution",
    label: "{provider} — connected with problems",
    fallback: "Connected with problems",
  },
  DEGRADED: { tone: "caution", label: "{provider} — degraded", fallback: "Degraded" },
  CONNECTING: { tone: "neutral", label: "{provider} — connecting…", fallback: "Connecting…" },
  RECONNECTING: { tone: "neutral", label: "{provider} — reconnecting…", fallback: "Reconnecting…" },
  DISCONNECTED: { tone: "critical", label: "{provider} — disconnected", fallback: "Disconnected" },
  ERROR: { tone: "critical", label: "{provider} — error", fallback: "Provider error" },
  DISABLED: { tone: "neutral", label: "{provider} — disabled", fallback: "Disabled" },
  ENTITLEMENT_MISSING: {
    tone: "neutral",
    label: "{provider} — not in your subscription",
    fallback: "Not in your subscription",
  },
  HEALTHY: { tone: "live", label: "Working" },
  UNAVAILABLE: {
    // Channel/subscription vocabulary (discover/live lanes). Control provider
    // `transport_state: UNAVAILABLE` is presented by `presentProviderTransport`.
    tone: "neutral",
    label: "Not available with your current data subscription",
    affects: "This lane or feature is disabled.",
  },
  READY: { tone: "live", label: "Ready" },
  ACTION_REQUIRED: { tone: "caution", label: "Action required: {next_action}", fallback: "Action required" },
  CONFIGURED: { tone: "live", label: "Configured" },
  MISSING: { tone: "caution", label: "Credentials missing" },
  NOT_REQUIRED: { tone: "neutral", label: "No credentials required" },
  ENABLED: { tone: "live", label: "Enabled" },
  OPTIONAL: { tone: "neutral", label: "Optional" },
  FIXTURE_ONLY: { tone: "replay", label: "Fixture data only" },
  BLOCKED_NON_LOOPBACK: { tone: "critical", label: "Blocked — non-loopback address refused" },
  COMPARATOR_NOT_CONFIGURED: { tone: "neutral", label: "Comparator not configured" },
  // Transport variants (semantic-state-system §3.4: IMPLEMENTED* → "Available",
  // variant detail stays in TechnicalDetails via `raw`).
  IMPLEMENTED: { tone: "live", label: "Available" },
  IMPLEMENTED_READ_ONLY: { tone: "live", label: "Available — read-only" },
  IMPLEMENTED_PUBLIC: { tone: "live", label: "Available" },
  IMPLEMENTED_OPTIONAL: { tone: "live", label: "Available" },
  REACHABLE: { tone: "live", label: "Reachable" },
  NOT_CHECKED: { tone: "neutral", label: "Not checked" },
  HTTPS_PAPER_HOST: { tone: "paper", label: "Paper endpoint configured" },
  // Interactive-broker credential states (tools/provider_readiness.py).
  CREDENTIAL_FILE_PRESENT_MANUAL_LOGIN_REQUIRED: {
    tone: "caution",
    label: "Credential file present — manual login required",
  },
  MANUAL_SESSION_REQUIRED: { tone: "caution", label: "Manual brokerage login required" },
};

const PLATFORM_TABLE: Record<string, Entry> = {
  // Local platform lifecycle aggregate (tools/platform/service_health.py).
  READY: { tone: "live", label: "Ready" },
  RUNNING: { tone: "live", label: "Running" },
  PARTIAL: {
    tone: "caution",
    label: "Partially running",
    sentence: "Some local platform services are not healthy.",
  },
  STOPPED: { tone: "neutral", label: "Stopped" },
  // Setup readiness aggregate (tools/platform/bootstrap.py + provider gate probe).
  ACTION_REQUIRED: { tone: "caution", label: "Action required" },
  // BLOCKED is shared by readiness (required checks failed) and update status
  // (local changes block the fast-forward) — the surrounding section and the
  // backend `detail` text disambiguate; the tone stays honest either way.
  BLOCKED: { tone: "critical", label: "Blocked" },
  // Setup checks.
  PASS: { tone: "live", label: "Pass" },
  FAIL: { tone: "critical", label: "Failed" },
  OPTIONAL: { tone: "neutral", label: "Optional" },
  // Fast-forward update status (tools/platform/control_service.py).
  AVAILABLE: { tone: "caution", label: "Update available" },
  CURRENT: { tone: "live", label: "Up to date" },
  UNAVAILABLE: { tone: "neutral", label: "Unavailable" },
  QUEUED: { tone: "neutral", label: "Queued" },
};

/**
 * Operator-action availability. This translates presentation availability only.
 * Domain reason codes stay on the action descriptor; they are not folded into
 * this table. Unknown availability values stay neutral via the shared fallback.
 */
const ACTION_TABLE: Record<string, Entry> = {
  AVAILABLE: { tone: "live", label: "Available" },
  BLOCKED: {
    tone: "critical",
    label: "Blocked",
    sentence: "This action is blocked.",
  },
  READ_ONLY: {
    tone: "neutral",
    label: "Read-only",
    sentence: "This action is read-only.",
  },
  UNAVAILABLE: {
    tone: "neutral",
    label: "Unavailable",
    sentence: "This action is unavailable.",
  },
};

const DATA_HEALTH_TABLE: Record<string, Entry> = {
  GOOD: { tone: "live", label: "Market data healthy" },
  PASS: { tone: "live", label: "Mark data current" },
  PARTIAL: {
    tone: "caution",
    label: "Market data is partial",
    sentence: "Market data is partial — some sources are unavailable.",
  },
  DEGRADED: {
    tone: "caution",
    label: "Market data is degraded",
    sentence: "Market data is degraded — some surfaces may be incomplete.",
  },
  STALE: {
    tone: "caution",
    label: "Market data is stale",
    sentence: "Market data is stale — quotes may be delayed.",
  },
  UNAVAILABLE: {
    tone: "critical",
    label: "Market data unavailable",
    sentence: "Market data is unavailable.",
    action: { label: "Check Providers", href: "/diagnostics/provider" },
  },
  UNKNOWN: { tone: "neutral", label: "Mark data quality unknown" },
  DISCONNECTED: {
    tone: "critical",
    label: "Mark data disconnected",
    sentence: "Mark data disconnected — P&L is not updating.",
  },
  RESTORED: {
    tone: "caution",
    label: "Session restored — marks wait for fresh data",
  },
  LIVE: { tone: "live", label: "Live" },
  DELAYED: { tone: "caution", label: "Delayed" },
  SNAPSHOT: { tone: "neutral", label: "Snapshot (point-in-time)" },
  FRESH: { tone: "live", label: "Fresh" },
  NOT_APPLICABLE: { tone: "neutral", label: "Not applicable" },
};

const PORTFOLIO_OK_RECONCILIATION = new Set([
  "PASS",
  "HEALTHY",
  "CLEAN",
  "RECONCILED",
  "INTERNAL_AUTHORITATIVE",
]);
const PORTFOLIO_OK_KILL_SWITCH = new Set(["OFF", "INACTIVE", "CLEAR"]);
const PORTFOLIO_OK_RISK = new Set(["PASS", "ALLOW", "APPROVE", "RESIZE"]);
const PORTFOLIO_PROBLEM_RISK = /BLOCKED|REJECTED|WAITING|FAILED/;

const PORTFOLIO_TABLE: Record<string, Entry> = {
  FILLED: { tone: "live", label: "Filled" },
  CANCELLED: { tone: "neutral", label: "Cancelled" },
  EXPIRED: { tone: "neutral", label: "Expired" },
  REJECTED: { tone: "critical", label: "Rejected" },
  RISK_REJECTED: { tone: "critical", label: "Rejected by risk controls" },
  SETTLED: { tone: "live", label: "Settled" },
  PENDING: { tone: "caution", label: "Settlement pending" },
  UNAVAILABLE: { tone: "neutral", label: "Settlement unknown" },
  MARKET: { tone: "neutral", label: "Market" },
  LIMIT: { tone: "neutral", label: "Limit" },
};

const RESEARCH_TABLE: Record<string, Entry> = {
  OBSERVED: { tone: "live", label: "From provider data" },
  DERIVED: { tone: "research", label: "Calculated by IMP" },
  INFERRED: { tone: "caution", label: "IMP inference — unverified" },
  RESEARCH_ONLY: { tone: "research", label: "Research-only evidence — not tradeable" },
  // Research surface epistemic classes (ui_api/projections.py research payloads).
  RESEARCH_PROJECTION: {
    tone: "research",
    label: "Research projection",
    sentence: "Replay-bound research projection — evidence, not prediction.",
  },
  SIMULATION_PROJECTION: {
    tone: "paper",
    label: "Deterministic simulation",
    sentence: "Deterministic simulation output — not live market evidence.",
  },
  // Research surface authority boundaries (never trade authority).
  READ_ONLY_RESEARCH_VISUALIZATION: {
    tone: "research",
    label: "Research-only evidence — not tradeable",
  },
  READ_ONLY_RESEARCH: { tone: "research", label: "Research-only — not tradeable" },
  READ_ONLY_SIMULATION: {
    tone: "paper",
    label: "Read-only simulation — no execution authority",
  },
  // Strategy walk-forward interpretation outcomes (strategy/interpretation.py).
  signal: { tone: "research", label: "Signal" },
  abstention: { tone: "neutral", label: "Abstained" },
  PAPER_OBSERVABILITY: { tone: "paper", label: "Paper simulation observability — read-only" },
  PAPER_OBSERVABILITY_READ_ONLY: {
    tone: "paper",
    label: "Paper simulation observability — read-only",
  },
  READY: { tone: "live", label: "Radar ready" },
  UNREADY: {
    tone: "caution",
    label: "Opportunity radar isn't ready",
    sentence: "Opportunity radar isn't ready: {reason}",
    fallback: "Opportunity radar isn't ready.",
    affects: "The ranked opportunity queue may be incomplete.",
    action: { label: "Open Control", href: "/control#control-feed" },
  },
  EMPTY: {
    tone: "neutral",
    label: "No opportunities right now",
    sentence: "No opportunities right now — nothing has been minted for the current coverage.",
  },
  UNAVAILABLE: {
    tone: "critical",
    label: "Opportunity feed unavailable",
    sentence: "The opportunity feed is unavailable.",
    action: { label: "Open Control", href: "/control#control-feed" },
  },
  DISMISSED: { tone: "neutral", label: "Dismissed" },
  OPEN_WORKSPACE: { tone: "live", label: "Open workspace" },
  ELIGIBLE: { tone: "live", label: "Eligible" },
  STOP: { tone: "critical", label: "Stop — do not act on this opportunity" },
  NONE: { tone: "neutral", label: "No action" },
  INELIGIBLE: { tone: "neutral", label: "Not eligible" },
  NORMALIZED_AWAITING_FORECAST: { tone: "caution", label: "Awaiting forecast" },
  frozen: { tone: "replay", label: "Frozen research snapshot" },
  current: { tone: "live", label: "Current data" },
  positive: { tone: "live", label: "Positive" },
  negative: { tone: "critical", label: "Negative" },
  neutral: { tone: "neutral", label: "Neutral" },
  mixed: { tone: "caution", label: "Mixed" },
  unknown: { tone: "neutral", label: "Unknown" },
};

const ERROR_TABLE: Record<string, Entry> = {
  STALE_DATA: { tone: "caution", label: "The data is stale — refresh before acting" },
  RATE_LIMITED: { tone: "caution", label: "Rate limited — retry shortly" },
  TIMEOUT: { tone: "caution", label: "The request timed out — retry" },
  VALIDATION_ERROR: { tone: "neutral", label: "The request was invalid" },
  PROVIDER_UNAVAILABLE: { tone: "critical", label: "The data provider is unavailable" },
  PROVIDER_REJECTED: { tone: "critical", label: "The data provider rejected the request" },
  UNSUPPORTED_CAPABILITY: { tone: "critical", label: "This capability is not supported here" },
  ACCOUNT_UNAVAILABLE: { tone: "critical", label: "The account is unavailable" },
  RISK_BLOCKED: { tone: "critical", label: "Risk controls blocked this order" },
  MODE_BLOCKED: { tone: "critical", label: "This action is blocked in the current mode" },
  AUTH_ERROR: { tone: "critical", label: "Authentication failed" },
  INTERNAL_ERROR: { tone: "critical", label: "Unexpected error" },
};

const DOMAIN_TABLES: Record<StateDomain, Record<string, Entry>> = {
  mode: MODE_TABLE,
  session: SESSION_TABLE,
  executionAuthority: EXECUTION_AUTHORITY_TABLE,
  providerHealth: PROVIDER_HEALTH_TABLE,
  dataHealth: DATA_HEALTH_TABLE,
  portfolio: PORTFOLIO_TABLE,
  research: RESEARCH_TABLE,
  platform: PLATFORM_TABLE,
  action: ACTION_TABLE,
  error: ERROR_TABLE,
};

/** Portfolio vocabulary has rule-based sets in addition to exact entries. */
function resolvePortfolioRule(raw: string): Entry | undefined {
  const upper = raw.toUpperCase();
  if (PORTFOLIO_OK_KILL_SWITCH.has(upper)) return { tone: "live", label: "Kill switch: off" };
  if (upper === "ON" || upper === "ACTIVE" || upper === "TRIGGERED") {
    return { tone: "critical", label: "Kill switch: on — trading halted" };
  }
  if (PORTFOLIO_OK_RECONCILIATION.has(upper)) return { tone: "live", label: "Reconciled" };
  if (PORTFOLIO_OK_RISK.has(upper)) return { tone: "live", label: humanizeEnum(raw) };
  if (PORTFOLIO_PROBLEM_RISK.test(upper)) {
    return { tone: "critical", label: `Needs attention: ${humanizeEnum(raw)}` };
  }
  return undefined;
}

/**
 * Resolve a backend state/enum value to its canonical semantic presentation.
 * Unknown values render `neutral` with the raw string preserved and a dev-mode
 * warning — never a guessed sentence, never a throw.
 */
export function resolveSemanticState(
  domain: StateDomain,
  rawValue: string | undefined | null,
  options: ResolveOptions = {},
): SemanticState {
  if (rawValue == null || rawValue === "") {
    return { tone: "neutral", label: "Unavailable", raw: "UNAVAILABLE" };
  }
  const raw = String(rawValue);
  const params = options.params ?? {};
  const table = DOMAIN_TABLES[domain];
  const entry = table[raw] ?? table[raw.toUpperCase()] ?? table[raw.toLowerCase()];
  if (entry) return renderEntry(entry, raw, params);
  if (domain === "portfolio") {
    const ruled = resolvePortfolioRule(raw);
    if (ruled) return renderEntry(ruled, raw, params);
  }
  devWarn(`Unmapped ${domain} value: ${raw}`);
  return { tone: "neutral", label: humanizeEnum(raw), raw };
}

/** Tone-ordered icon glyphs — always paired with text (never color alone). */
export const SEMANTIC_TONE_ICON: Record<SemanticTone, string> = {
  live: "●",
  paper: "◆",
  replay: "◐",
  research: "◇",
  caution: "▲",
  critical: "■",
  neutral: "○",
};

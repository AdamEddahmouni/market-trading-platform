/**
 * Control-center presentation logic (pure).
 *
 * Everything here *translates* existing backend contract values — provider
 * roles from `tools/provider_readiness.py`, readiness/lifecycle aggregates,
 * `/context` authority triples, and the opportunity feed status — into
 * operator language. No operational state is computed here beyond mirroring
 * derivations the backend already performs (e.g. the readiness
 * `provider_action` rule in `ui_api/operator_projections.py`).
 */
import type { OperatorReadiness, ProviderReadiness } from "../../api/schemas";
import type { ModeContextEvaluation } from "../mode-session/modeAuthority";
import type { Mode } from "../mode-session/types";
import {
  humanizeEnum,
  resolveSemanticState,
  type SemanticState,
  type SemanticTone,
} from "../../state/semanticState";

/** Stable section anchors — hash deep-links from Command/StatusBar land here. */
export const CONTROL_SECTIONS = {
  overview: "control-overview",
  systemStatus: "control-system-status",
  governance: "control-governance",
  authority: "control-authority",
  attention: "control-attention",
  providers: "control-providers",
  feed: "control-feed",
  technical: "control-technical",
} as const;

export function controlSectionHref(section: keyof typeof CONTROL_SECTIONS): string {
  return `/control#${CONTROL_SECTIONS[section]}`;
}

/** In-page landmarks for keyboard users — labels match visible headings. */
export const CONTROL_SECTION_NAV: ReadonlyArray<{ id: string; label: string }> = [
  { id: CONTROL_SECTIONS.overview, label: "Operating state" },
  { id: CONTROL_SECTIONS.systemStatus, label: "System status" },
  { id: CONTROL_SECTIONS.governance, label: "Program gates" },
  { id: CONTROL_SECTIONS.authority, label: "Execution & authority" },
  { id: CONTROL_SECTIONS.providers, label: "Providers" },
  { id: CONTROL_SECTIONS.feed, label: "Opportunity feed" },
  { id: CONTROL_SECTIONS.technical, label: "Technical detail" },
];

/* -------------------------------------------------------------------------- */
/* Provider roles → capability / impact language                              */
/* -------------------------------------------------------------------------- */

type ProviderRolePresentation = {
  /** What the provider supports (one short phrase). */
  capability: string;
  /** What degradation of this provider means for the operator. */
  impact: string;
};

/**
 * Translation table for the `role` contract values emitted by
 * `tools/provider_readiness.py`. Unknown roles humanize mechanically with no
 * impact sentence — never a guessed consequence.
 */
const PROVIDER_ROLE_PRESENTATION: Record<string, ProviderRolePresentation> = {
  primary_observational_market_data: {
    capability: "Primary live market data (OpenD)",
    impact: "Live quotes stop updating; quote-dependent opportunity evaluation may be incomplete.",
  },
  secondary_observational_market_data: {
    capability: "Secondary observational market data",
    impact: "The backup market-data path is unavailable; primary coverage is unaffected.",
  },
  discovery: {
    capability: "Discovery screening",
    impact: "Radar screeners and the opportunity feed may be incomplete.",
  },
  news_catalyst: {
    capability: "News and catalyst evidence",
    impact: "News and catalyst context on opportunities may be missing.",
  },
  research: {
    capability: "Research data",
    impact: "Research evidence may be incomplete.",
  },
  regulatory: {
    capability: "Regulatory filings data",
    impact: "Regulatory evidence may be incomplete.",
  },
  assistant: {
    capability: "Research assistant",
    impact: "The assistant is unavailable; the rest of the platform is unaffected.",
  },
  operational_persistence: {
    capability: "Optional durable persistence",
    impact: "Shared persistence features stay disabled; local state is unaffected.",
  },
  sandbox_execution: {
    capability: "Sandbox execution comparator",
    impact: "Not required for operation — internal paper simulation is unaffected.",
  },
  paper_execution: {
    capability: "Paper execution comparator",
    impact: "Not required for operation — internal paper simulation is unaffected.",
  },
  simulated_execution: {
    capability: "Simulated execution transport",
    impact: "Not required for operation — internal paper simulation is unaffected.",
  },
  public_positioning: {
    capability: "Public positioning data",
    impact: "Public positioning evidence may be incomplete.",
  },
  public_short_status: {
    capability: "Public short-status data",
    impact: "Short-status evidence may be incomplete.",
  },
  public_options_statistics: {
    capability: "Public options statistics",
    impact: "Options statistics evidence may be incomplete.",
  },
  public_weather: {
    capability: "Public weather data",
    impact: "Weather evidence may be incomplete.",
  },
};

export function presentProviderRole(role: string | undefined): ProviderRolePresentation | null {
  if (!role) return null;
  const known = PROVIDER_ROLE_PRESENTATION[role];
  if (known) return known;
  return { capability: humanizeEnum(role), impact: "" };
}

/**
 * Control provider rows emit backend `transport_state`. The shared
 * `providerHealth` adapter maps the token `UNAVAILABLE` to channel/subscription
 * copy ("not in your current data subscription"). That is the wrong vocabulary
 * for operator readiness: an enabled-but-unreachable transport is a connectivity
 * fact, not an entitlement gap. Entitlements stay on `ENTITLEMENT_MISSING`.
 */
export function presentProviderTransport(provider: ProviderReadiness): SemanticState {
  if (provider.transport_state === "UNAVAILABLE") {
    if (providerIsActive(provider)) {
      return {
        tone: "caution",
        label: "Transport unavailable",
        sentence:
          "This provider is configured to run, but its transport cannot be reached. That is not a data-subscription gap.",
        affects: "Coverage from this provider is unknown until the transport responds.",
        raw: "UNAVAILABLE",
      };
    }
    return {
      tone: "neutral",
      label: "Unavailable",
      sentence:
        "This provider is off by configuration. Unavailable here is not a live transport failure.",
      raw: "UNAVAILABLE",
    };
  }
  return resolveSemanticState("providerHealth", provider.transport_state);
}

/* -------------------------------------------------------------------------- */
/* Provider readiness grouping                                                */
/* -------------------------------------------------------------------------- */

/**
 * Mirrors the backend readiness `provider_action` rule (gate ENABLED with an
 * unavailable/blocked transport) and adds the credential gap on an enabled
 * gate — both mean "configured to run, not running".
 */
export function providerNeedsAction(provider: ProviderReadiness): boolean {
  const gateOn = provider.gate_state === "ENABLED" || provider.gate_state === "CONFIGURED";
  if (!gateOn) return false;
  return (
    provider.transport_state === "UNAVAILABLE" ||
    provider.transport_state === "BLOCKED_NON_LOOPBACK" ||
    provider.credential_state === "MISSING"
  );
}

/** A provider is in active service when its gate is on. */
export function providerIsActive(provider: ProviderReadiness): boolean {
  return provider.gate_state === "ENABLED" || provider.gate_state === "CONFIGURED";
}

export type PartitionedProviders = {
  /** Enabled but not healthy — operator action exists. */
  attention: ProviderReadiness[];
  /** Enabled and not flagged. */
  active: ProviderReadiness[];
  /** Off by configuration or optional — shown behind disclosure. */
  inactive: ProviderReadiness[];
};

export function partitionProviders(providers: ProviderReadiness[]): PartitionedProviders {
  const attention: ProviderReadiness[] = [];
  const active: ProviderReadiness[] = [];
  const inactive: ProviderReadiness[] = [];
  for (const provider of providers) {
    if (providerNeedsAction(provider)) attention.push(provider);
    else if (providerIsActive(provider)) active.push(provider);
    else inactive.push(provider);
  }
  return { attention, active, inactive };
}

/* -------------------------------------------------------------------------- */
/* Required operator attention                                                */
/* -------------------------------------------------------------------------- */

export type ControlAttentionItem = {
  id: string;
  tone: SemanticTone;
  /** What is wrong (one human phrase). */
  title: string;
  /** Impact / why it matters. */
  detail?: string;
  /** Legitimate next step — link only; mutations stay in their own sections. */
  action?: { label: string; href: string };
};

export type ControlAttentionInput = {
  mode: Mode;
  contextState: "loading" | "ready" | "error";
  evaluation?: ModeContextEvaluation;
  readiness?: OperatorReadiness | null;
  readinessError?: boolean;
  lifecycleStatus?: string | null;
  lifecycleError?: boolean;
  feedStatus?: string;
  feedUnreadyReason?: string | null;
  feedError?: boolean;
  /** Paper mode only: whether a paper session is open (undefined = unknown). */
  paperSessionOpen?: boolean;
  /** Humanized UNREADY reason (from opportunityPresentation). */
  humanizedUnreadyReason?: string | null;
  diagnosticsError?: boolean;
};

/** Live ranked rows withheld for a missing receive clock — honesty, not a radar repair. */
export function isLiveClockWithheldFeed(input: {
  feedStatus?: string;
  feedUnreadyReason?: string | null;
}): boolean {
  return input.feedStatus === "UNREADY" && input.feedUnreadyReason === "LIVE_AS_OF_UNAVAILABLE";
}

const TONE_RANK: Record<SemanticTone, number> = {
  critical: 0,
  caution: 1,
  live: 2,
  paper: 2,
  replay: 2,
  research: 2,
  neutral: 3,
};

/**
 * Derive the actionable attention list from real contract states. Informational
 * or by-design states (optional providers, Live's missing opportunity engine,
 * available updates) are deliberately excluded — this list is work, not noise.
 */
export function buildAttentionItems(input: ControlAttentionInput): ControlAttentionItem[] {
  const items: ControlAttentionItem[] = [];

  if (input.diagnosticsError) {
    items.push({
      id: "diagnostics-unavailable",
      tone: "caution",
      title: "Operator diagnostics could not be loaded",
      detail:
        "This is a load failure, not a calendar wait. Platform truth hierarchy is unknown until GET /operator/diagnostics responds.",
      action: { label: "Review system status", href: controlSectionHref("systemStatus") },
    });
  }

  if (input.contextState === "error") {
    items.push({
      id: "context-unavailable",
      tone: "caution",
      title: "Backend context unavailable",
      detail: "Execution controls remain locked until the backend context is reachable.",
      action: { label: "Review authority", href: controlSectionHref("authority") },
    });
  } else if (input.evaluation?.status === "mismatch") {
    items.push({
      id: "context-mismatch",
      tone: "critical",
      title: "UI and backend disagree",
      detail:
        "UI mode selection does not change backend authority. Switch mode or restart the backend session.",
      action: { label: "Review authority", href: controlSectionHref("authority") },
    });
  }

  if (input.lifecycleError) {
    items.push({
      id: "lifecycle-unavailable",
      tone: "caution",
      title: "Platform runtime status could not be checked",
      detail: "Service health is unknown until the local platform responds.",
      action: { label: "Review runtime", href: controlSectionHref("overview") },
    });
  } else if (input.lifecycleStatus === "PARTIAL") {
    items.push({
      id: "lifecycle-partial",
      tone: "caution",
      title: "Some platform services are not healthy",
      detail: "The local platform is only partially running.",
      action: { label: "Review runtime", href: controlSectionHref("overview") },
    });
  } else if (input.lifecycleStatus === "STOPPED") {
    items.push({
      id: "lifecycle-stopped",
      tone: "critical",
      title: "Platform services are stopped",
      detail: "The local platform reports no healthy required services.",
      action: { label: "Review runtime", href: controlSectionHref("overview") },
    });
  }

  if (input.readinessError) {
    items.push({
      id: "readiness-unavailable",
      tone: "caution",
      title: "Platform readiness could not be checked",
      detail: "Setup and provider readiness are unknown until the local platform responds.",
    });
  }

  for (const check of input.readiness?.checks ?? []) {
    if (check.status === "FAIL" && check.required) {
      items.push({
        id: `check-${check.id}`,
        tone: "critical",
        title: check.label,
        detail: check.next_action ? `${check.detail} ${check.next_action}` : check.detail,
      });
    }
  }

  const providers = partitionProviders(input.readiness?.providers ?? []);
  for (const provider of providers.attention) {
    const label = provider.label ?? provider.provider;
    items.push({
      id: `provider-${provider.provider}`,
      tone: provider.transport_state === "BLOCKED_NON_LOOPBACK" ? "critical" : "caution",
      title: `${label} needs attention`,
      detail: provider.next_action,
      action: { label: "Review providers", href: controlSectionHref("providers") },
    });
  }

  if (input.feedError) {
    items.push({
      id: "feed-error",
      tone: "caution",
      title: "Opportunity feed status could not be loaded",
      detail: "Feed readiness is unknown; the ranked queue may be incomplete.",
      action: { label: "Review feed status", href: controlSectionHref("feed") },
    });
  } else if (input.feedStatus === "UNREADY") {
    if (!isLiveClockWithheldFeed(input)) {
      items.push({
        id: "feed-unready",
        tone: "caution",
        title: "Opportunity radar isn't ready",
        detail: input.humanizedUnreadyReason
          ? `${input.humanizedUnreadyReason}. The ranked opportunity queue may be incomplete.`
          : "The ranked opportunity queue may be incomplete.",
        action: { label: "Review feed status", href: controlSectionHref("feed") },
      });
    }
  } else if (input.feedStatus === "UNAVAILABLE" && input.mode !== "LIVE") {
    items.push({
      id: "feed-unavailable",
      tone: "critical",
      title: "Opportunity feed unavailable",
      detail: "The opportunity feed is unavailable; ranked opportunities cannot be trusted right now.",
      action: { label: "Review feed status", href: controlSectionHref("feed") },
    });
  }

  if (input.mode === "PAPER" && input.paperSessionOpen === false) {
    items.push({
      id: "paper-session-closed",
      tone: "caution",
      title: "No paper session open",
      detail: "Paper orders cannot be submitted until a paper session is open.",
      action: { label: "Open Portfolio", href: "/portfolio" },
    });
  }

  return items.sort((a, b) => TONE_RANK[a.tone] - TONE_RANK[b.tone]);
}

/* -------------------------------------------------------------------------- */
/* Execution / authority summary                                              */
/* -------------------------------------------------------------------------- */

/**
 * The plain-language answer to "can IMP execute right now?" — derived from the
 * UI mode plus the backend authority evaluation, never from button labels.
 */
export function authoritySummary(
  mode: Mode,
  contextState: "loading" | "ready" | "error",
  evaluation: ModeContextEvaluation | undefined,
): string {
  if (contextState === "loading") return "Verifying backend authority…";
  if (contextState === "error" || !evaluation || evaluation.status === "unavailable") {
    return "Execution controls remain locked until the backend context is reachable.";
  }
  if (evaluation.status === "mismatch") {
    return "UI mode selection does not change backend authority. Switch mode or restart the backend session.";
  }
  if (mode === "DEMO") return "Demo replay is read-only — order entry is disabled.";
  if (mode === "PAPER") {
    return "Paper orders can be submitted from the Workspace cockpit with a current preview.";
  }
  return "Live market data is observational only — execution stays locked.";
}

/**
 * Research surface presentation model (UIR-01F).
 *
 * Pure derivation layer for the Research pages. Everything here translates
 * existing backend contract fields (`/research/analytics`, `/research/models`,
 * `/research/simulation`) into operator language — nothing is invented, no
 * confidence or contradiction score is synthesized, and unavailable data stays
 * visibly unavailable. Contract authority: docs/ui-redesign-v2/research-contract-map.md.
 */
import type {
  ResearchAnalyticsResponse,
  ResearchModelsResponse,
  ResearchSimulationResponse,
} from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { humanizeEnum } from "../../state/semanticState";
import { formatAbsoluteTime, parseAsOfMs } from "../imp-ui/FreshnessIndicator";

/* -------------------------------------------------------------------------- */
/* Sections (routable tabs)                                                   */
/* -------------------------------------------------------------------------- */

export type ResearchSectionKey = "overview" | "evidence" | "validation" | "simulation";

export const RESEARCH_SECTION_TABS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/research", label: "Overview", end: true },
  { to: "/research/evidence", label: "Evidence" },
  { to: "/research/validation", label: "Validation" },
  { to: "/research/simulation", label: "Simulation" },
];

/* -------------------------------------------------------------------------- */
/* Evidence findings (analytics panels)                                       */
/* -------------------------------------------------------------------------- */

export type ResearchPanelKey =
  | "attention_tiers"
  | "squeeze_outcomes"
  | "squeeze_historical_cohort"
  | "strategy_outcomes"
  | "risk_decisions";

export type ResearchFindingDescriptor = {
  key: ResearchPanelKey;
  /** Stable anchor id for `?panel=` deep links. */
  anchor: string;
  title: string;
  /** What this finding measures — the claim, in operator language. */
  claim: string;
  /** Why the operator should care. */
  whyItMatters: string;
  /**
   * Evidence class label, derived from the backend provenance of the panel
   * (see research-contract-map.md). Presentation mapping only; the raw
   * provenance stays visible in the Methodology disclosure.
   */
  evidenceClass: string;
};

export const RESEARCH_FINDINGS: ReadonlyArray<ResearchFindingDescriptor> = [
  {
    key: "strategy_outcomes",
    anchor: "research-finding-strategy-outcomes",
    title: "Strategy interpretation outcomes",
    claim: "How often the walk-forward strategy evaluation produced a signal versus abstained.",
    whyItMatters:
      "This is the core research result: what the strategy evidence concluded at each observation, with abstentions counted honestly.",
    evidenceClass: "Walk-forward backtest (replay-bound)",
  },
  {
    key: "risk_decisions",
    anchor: "research-finding-risk-decisions",
    title: "Risk simulation decisions",
    claim: "How the deterministic risk simulation ruled on the signals it was shown.",
    whyItMatters:
      "Shows how risk constraints would have treated the research signals — simulation output, not live evidence.",
    evidenceClass: "Simulated (deterministic)",
  },
  {
    key: "attention_tiers",
    anchor: "research-finding-attention-tiers",
    title: "Attention tier distribution",
    claim: "How replayed attention items were distributed across tiers at the current cutoff.",
    whyItMatters:
      "Context for what the replay feed surfaced — it describes the input stream, not a recommendation.",
    evidenceClass: "Replay evidence",
  },
  {
    key: "squeeze_outcomes",
    anchor: "research-finding-squeeze-outcomes",
    title: "Squeeze screener outcomes",
    claim: "Outcome mix across the donor short-squeeze screener bridge.",
    whyItMatters:
      "Historical donor evidence behind the squeeze research screens in Radar — useful context, never a trade signal.",
    evidenceClass: "Historical (donor bridge)",
  },
  {
    key: "squeeze_historical_cohort",
    anchor: "research-finding-squeeze-cohort",
    title: "Historical squeeze cohort",
    claim: "Calibration summary over the historical squeeze cohort.",
    whyItMatters:
      "The cohort baseline the squeeze research is calibrated against — a reference distribution, not a forecast.",
    evidenceClass: "Historical cohort",
  },
];

export function researchFinding(key: ResearchPanelKey): ResearchFindingDescriptor {
  const descriptor = RESEARCH_FINDINGS.find((finding) => finding.key === key);
  if (!descriptor) throw new Error(`Unknown research panel: ${key}`);
  return descriptor;
}

type AnalyticsPanel = ResearchAnalyticsResponse["panels"][ResearchPanelKey];

export function researchPanel(
  analytics: ResearchAnalyticsResponse | null | undefined,
  key: ResearchPanelKey,
): AnalyticsPanel | undefined {
  return analytics?.panels?.[key];
}

/** Availability presentation for one finding — honest about empty vs unavailable. */
export function presentFindingAvailability(panel: AnalyticsPanel | undefined): {
  tone: SemanticTone;
  label: string;
  detail: string;
} {
  if (!panel) {
    return {
      tone: "neutral",
      label: "Unavailable",
      detail: "This finding was not included in the research payload.",
    };
  }
  if (!panel.available) {
    return {
      tone: "caution",
      label: "Unavailable",
      detail: panel.reason
        ? `Not available at this cutoff: ${panel.reason}`
        : "Not available at this cutoff — the source reported no rows.",
    };
  }
  if (!panel.series.length && !(panel.signal_timeline?.length)) {
    return {
      tone: "neutral",
      label: "Empty",
      detail: "Available, but no rows fall inside the current replay window.",
    };
  }
  return { tone: "research", label: "Available", detail: "Data at the current replay cutoff." };
}

/* -------------------------------------------------------------------------- */
/* Vocabulary humanizers (real backend values only)                           */
/* -------------------------------------------------------------------------- */

/** Abstention reason codes from strategy/abstention.py. */
const ABSTENTION_REASON_LABEL: Record<string, string> = {
  ABSTAIN_NO_PREREGISTRATION: "No preregistration",
  ABSTAIN_INSTITUTIONAL_UNAVAILABLE: "Institutional evidence unavailable",
  ABSTAIN_FORECAST_INVALID: "Forecast invalid",
  ABSTAIN_FUTURE_INPUT: "Future-dated input detected",
  ABSTAIN_CONFLICTING_EVIDENCE: "Conflicting evidence",
  ABSTAIN_COPYABILITY_UNAVAILABLE: "Copyability check unavailable",
};

export function presentAbstentionReason(code: string): { label: string; raw: string } {
  return { label: ABSTENTION_REASON_LABEL[code] ?? humanizeEnum(code), raw: code };
}

/** Preregistration gate state (strategy/eligibility.py: PASS / FAIL / ABSENT). */
export function presentPreregistration(status: string | null | undefined): {
  tone: SemanticTone;
  label: string;
  raw: string;
} {
  if (status == null || status === "") {
    return { tone: "neutral", label: "Not reported", raw: "UNAVAILABLE" };
  }
  switch (status.toUpperCase()) {
    case "PASS":
      return { tone: "live", label: "Preregistered", raw: status };
    case "FAIL":
      return { tone: "critical", label: "Preregistration failed", raw: status };
    case "ABSENT":
      return { tone: "neutral", label: "Not preregistered", raw: status };
    default:
      return { tone: "neutral", label: humanizeEnum(status), raw: status };
  }
}

/** Reconciliation / fill-audit check status (e.g. PASS / FAIL). */
export function presentCheckStatus(status: string | null | undefined): {
  tone: SemanticTone;
  label: string;
  raw: string;
} {
  if (status == null || status === "") {
    return { tone: "neutral", label: "Not reported", raw: "UNAVAILABLE" };
  }
  switch (status.toUpperCase()) {
    case "PASS":
      return { tone: "live", label: "Pass", raw: status };
    case "FAIL":
    case "FAILED":
      return { tone: "critical", label: "Failed", raw: status };
    default:
      return { tone: "neutral", label: humanizeEnum(status), raw: status };
  }
}

/**
 * Human absolute time for research epoch/ISO fields (observation_time and
 * prediction_cutoff are epoch ns; as_of_time is ISO). Returns null when the
 * value cannot be parsed — callers render "Unavailable", never a raw number.
 */
export function formatResearchTime(value: unknown): string | null {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const ms = parseAsOfMs(value);
  return ms == null ? null : formatAbsoluteTime(ms);
}

/* -------------------------------------------------------------------------- */
/* Overview synthesis (payload-derived sentences only)                        */
/* -------------------------------------------------------------------------- */

export type ResearchSynthesisInput = {
  analytics?: ResearchAnalyticsResponse | null;
  models?: ResearchModelsResponse | null;
  simulation?: ResearchSimulationResponse | null;
};

export type ResearchSynthesisLine = {
  id: "validation" | "evidence" | "simulation";
  text: string;
};

/**
 * The L1 "what does the evidence currently show" strip. Every number comes
 * straight from a contract field; when a source is missing the line says so
 * instead of guessing.
 */
export function buildResearchSynthesis(input: ResearchSynthesisInput): ResearchSynthesisLine[] {
  const lines: ResearchSynthesisLine[] = [];

  if (input.models) {
    const summary = input.models.interpretation_summary;
    lines.push({
      id: "validation",
      text:
        `Strategy walk-forward at the current cutoff: ${summary.signal_count} ` +
        `${summary.signal_count === 1 ? "signal" : "signals"} and ${summary.abstention_count} ` +
        `${summary.abstention_count === 1 ? "abstention" : "abstentions"} across ` +
        `${summary.total_at_cutoff} ${summary.total_at_cutoff === 1 ? "observation" : "observations"}, ` +
        `${input.models.walk_forward_fold_count} walk-forward ` +
        `${input.models.walk_forward_fold_count === 1 ? "fold" : "folds"}.`,
    });
    const conflicts = countConflictingInterpretations(input.models);
    if (conflicts > 0) {
      lines.push({
        id: "validation",
        text:
          `${conflicts} ${conflicts === 1 ? "observation abstained" : "observations abstained"} ` +
          `because the backend reported conflicting evidence (` +
          `ABSTAIN_CONFLICTING_EVIDENCE). That is the only contract-backed conflict signal.`,
      });
    }
  }

  if (input.analytics) {
    const available = RESEARCH_FINDINGS.filter(
      (finding) => researchPanel(input.analytics, finding.key)?.available,
    ).length;
    lines.push({
      id: "evidence",
      text: `${available} of ${RESEARCH_FINDINGS.length} evidence findings have data at this cutoff.`,
    });
    const squeeze = researchPanel(input.analytics, "squeeze_outcomes");
    if (squeeze && !squeeze.available && squeeze.reason) {
      lines.push({ id: "evidence", text: `Squeeze donor bridge unavailable: ${squeeze.reason}` });
    }
  }

  if (input.simulation) {
    const reconciliation = presentCheckStatus(input.simulation.reconciliation?.status as string | undefined);
    lines.push({
      id: "simulation",
      text:
        `Deterministic simulation: ${input.simulation.ledger_summary.entry_count} ledger ` +
        `${input.simulation.ledger_summary.entry_count === 1 ? "entry" : "entries"}, ` +
        `${input.simulation.risk_decisions.length} risk ` +
        `${input.simulation.risk_decisions.length === 1 ? "decision" : "decisions"}, ` +
        `reconciliation ${reconciliation.label.toLowerCase()}.`,
    });
  }

  return lines;
}

/** Availability map rows for the Overview "where the evidence stands" block. */
export type EvidenceAvailabilityRow = {
  id: string;
  label: string;
  tone: SemanticTone;
  stateLabel: string;
  detail: string;
  href: string;
};

export function buildEvidenceAvailability(input: ResearchSynthesisInput): EvidenceAvailabilityRow[] {
  const rows: EvidenceAvailabilityRow[] = RESEARCH_FINDINGS.map((finding) => {
    const availability = presentFindingAvailability(researchPanel(input.analytics, finding.key));
    return {
      id: finding.key,
      label: finding.title,
      tone: availability.tone,
      stateLabel: availability.label,
      detail: availability.detail,
      href: `/research/evidence?panel=${finding.key}`,
    };
  });

  const models = input.models;
  rows.push({
    id: "validation",
    label: "Strategy validation",
    tone: models ? "research" : "neutral",
    stateLabel: models ? "Available" : "Unavailable",
    detail: models
      ? `${models.walk_forward_fold_count} walk-forward folds · ${presentPreregistration(models.preregistration_status).label}.`
      : "The model validation payload was not included.",
    href: "/research/validation",
  });

  const simulation = input.simulation;
  rows.push({
    id: "simulation",
    label: "Simulation run",
    tone: simulation ? "paper" : "neutral",
    stateLabel: simulation ? "Available" : "Unavailable",
    detail: simulation
      ? `${simulation.ledger_summary.entry_count} ledger entries · deterministic simulation.`
      : "The simulation payload was not included.",
    href: "/research/simulation",
  });

  return rows;
}

const CONFLICT_REASON = "ABSTAIN_CONFLICTING_EVIDENCE";

/** Contract-backed conflict count — never inferred from other fields. */
export function countConflictingInterpretations(
  models?: ResearchModelsResponse | null,
): number {
  if (!models?.interpretations?.length) return 0;
  return models.interpretations.filter((row) =>
    Array.isArray(row.abstention_reason_codes)
      ? row.abstention_reason_codes.some((code) => String(code) === CONFLICT_REASON)
      : false,
  ).length;
}

export function interpretationHasConflict(row: { abstention_reason_codes?: unknown }): boolean {
  return Array.isArray(row.abstention_reason_codes)
    ? row.abstention_reason_codes.some((code) => String(code) === CONFLICT_REASON)
    : false;
}

export type FindingSourceRow = {
  source: string;
  findings: string[];
};

/** Per-finding provenance sources — there is no source-catalog endpoint. */
export function listFindingSources(
  analytics?: ResearchAnalyticsResponse | null,
): FindingSourceRow[] {
  const bySource = new Map<string, string[]>();
  for (const finding of RESEARCH_FINDINGS) {
    const source = researchPanel(analytics, finding.key)?.provenance?.source;
    const label = source ? String(source) : "Unavailable";
    const existing = bySource.get(label) ?? [];
    existing.push(finding.title);
    bySource.set(label, existing);
  }
  return Array.from(bySource.entries()).map(([source, findings]) => ({ source, findings }));
}

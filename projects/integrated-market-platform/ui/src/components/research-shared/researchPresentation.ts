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
  href: string;
};

export type ResearchSessionMode = "DEMO" | "PAPER" | "LIVE";

export type ResearchClaimNodeKey =
  | "source"
  | "hypothesis"
  | "strategy"
  | "experiment"
  | "evidence"
  | "contradiction"
  | "implementation"
  | "forward-test";

export type ClaimDestinationKind = "research" | "related" | "proxy" | "gap";

export type ResearchClaimNode = {
  key: ResearchClaimNodeKey;
  title: string;
  role: string;
  statusLabel: string;
  statusTone: SemanticTone;
  detail: string;
  href: string | null;
  destinationKind: ClaimDestinationKind;
  evidenceClass: string;
};

export type ClaimHop = {
  key: ResearchClaimNodeKey;
  title: string;
  href: string | null;
  note: string;
};

export type ClaimPathRelation = "on-path" | "off-path";

export type ResearchClaimLineageNode = ResearchClaimNode & {
  relation: ClaimPathRelation;
};

export type ResearchClaimLineage = {
  findingKey: ResearchPanelKey;
  findingTitle: string;
  reading: string;
  nodes: ResearchClaimLineageNode[];
};

const CLAIM_NODE_ORDER: ReadonlyArray<ResearchClaimNodeKey> = [
  "source",
  "hypothesis",
  "strategy",
  "experiment",
  "evidence",
  "contradiction",
  "implementation",
  "forward-test",
];

const CLAIM_TITLES: Record<ResearchClaimNodeKey, string> = {
  source: "Source",
  hypothesis: "Hypothesis",
  strategy: "Strategy",
  experiment: "Experiment",
  evidence: "Evidence",
  contradiction: "Contradiction",
  implementation: "Implementation",
  "forward-test": "Forward-test",
};

/**
 * Hops that belong to one analytics finding. Source and evidence are always
 * on the path because they *are* the finding; other nodes stay finding-specific.
 * Hypothesis is only on donor-squeeze paths as a NOT_EXPOSED proxy — not a
 * fabricated object.
 */
const CLAIM_PATH_BY_FINDING: Record<ResearchPanelKey, ReadonlyArray<ResearchClaimNodeKey>> = {
  strategy_outcomes: ["strategy", "contradiction", "experiment", "implementation", "forward-test"],
  risk_decisions: ["experiment", "strategy", "forward-test"],
  attention_tiers: [],
  squeeze_outcomes: ["hypothesis"],
  squeeze_historical_cohort: ["hypothesis"],
};

export function forwardTestWorkspaceHref(mode: ResearchSessionMode): string | null {
  return mode === "PAPER" ? "/workspace" : null;
}

export function parseClaimFindingParam(value: string | null | undefined): ResearchPanelKey | null {
  if (!value) return null;
  return RESEARCH_FINDINGS.some((finding) => finding.key === value)
    ? (value as ResearchPanelKey)
    : null;
}

/** Unknown `?claim=` values are ignored — they are not a new research object. */
export function resolveFollowedFinding(
  requested: string | null | undefined,
  analytics?: ResearchAnalyticsResponse | null,
): ResearchPanelKey {
  const parsed = parseClaimFindingParam(requested);
  if (parsed) return parsed;
  if (researchPanel(analytics, "strategy_outcomes")?.available) return "strategy_outcomes";
  const firstAvailable = RESEARCH_FINDINGS.find(
    (finding) => researchPanel(analytics, finding.key)?.available,
  );
  return firstAvailable?.key ?? "strategy_outcomes";
}

export function claimPathKeys(findingKey: ResearchPanelKey): ResearchClaimNodeKey[] {
  const extra = new Set<ResearchClaimNodeKey>(["source", "evidence", ...CLAIM_PATH_BY_FINDING[findingKey]]);
  return CLAIM_NODE_ORDER.filter((key) => extra.has(key));
}

/** Carry the followed finding on Research routes only. Lab/Workspace stay unscoped. */
export function withResearchClaimQuery(
  href: string | null,
  findingKey: ResearchPanelKey,
): string | null {
  if (!href) return null;
  if (!href.startsWith("/research")) return href;
  const hashIndex = href.indexOf("#");
  const hash = hashIndex >= 0 ? href.slice(hashIndex) : "";
  const withoutHash = hashIndex >= 0 ? href.slice(0, hashIndex) : href;
  const queryIndex = withoutHash.indexOf("?");
  const path = queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash;
  const params = new URLSearchParams(queryIndex >= 0 ? withoutHash.slice(queryIndex + 1) : "");
  params.set("claim", findingKey);
  if (path === "/research/evidence" && !params.has("panel")) {
    params.set("panel", findingKey);
  }
  return `${path}?${params.toString()}${hash}`;
}

/** Distinct hop accessible name so section tabs stay uniquely queryable. */
export function claimFollowAccessibleName(title: string): string {
  return `Follow ${title.toLowerCase()}`;
}

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
      href: "/research/validation",
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
        href: "/research/validation?conflict=1",
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
      href: "/research/evidence",
      text: `${available} of ${RESEARCH_FINDINGS.length} evidence findings have data at this cutoff.`,
    });
    const squeeze = researchPanel(input.analytics, "squeeze_outcomes");
    if (squeeze && !squeeze.available && squeeze.reason) {
      lines.push({
        id: "evidence",
        href: "/research/evidence?panel=squeeze_outcomes",
        text: `Squeeze donor bridge unavailable: ${squeeze.reason}`,
      });
    }
  }

  if (input.simulation) {
    const reconciliation = presentCheckStatus(input.simulation.reconciliation?.status as string | undefined);
    lines.push({
      id: "simulation",
      href: "/research/simulation",
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

function recordScalar(record: Record<string, unknown> | undefined, key: string): string | null {
  if (!record) return null;
  const value = record[key];
  if (value == null) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function strategyNodeDetail(models?: ResearchModelsResponse | null): string {
  if (!models) return "The model validation payload was not included.";
  const family = recordScalar(models.model_summary, "model_family") ?? "UNKNOWN";
  const alignment =
    recordScalar(models.model_summary, "alignment_type") ??
    recordScalar(models.strategy_spec, "alignment_type") ??
    "UNKNOWN";
  return `${family} · ${alignment} · ${presentPreregistration(models.preregistration_status).label}.`;
}

function sourceNodeDetail(analytics?: ResearchAnalyticsResponse | null): string {
  if (!analytics) return "Analytics payload not included — sources UNAVAILABLE.";
  const sources = listFindingSources(analytics)
    .map((row) => row.source)
    .filter((source) => source !== "Unavailable");
  if (!sources.length) return "Panels loaded, but no provenance.source values were reported.";
  return `Provenance sources on this payload: ${sources.join("; ")}. No source-catalog endpoint exists.`;
}

function contradictionNode(models?: ResearchModelsResponse | null): Pick<
  ResearchClaimNode,
  "statusLabel" | "statusTone" | "detail" | "href" | "destinationKind"
> {
  if (!models) {
    return {
      statusLabel: "Unavailable",
      statusTone: "neutral",
      detail:
        "Contradiction flags are not a contract. Conflict count cannot be read until validation loads.",
      href: "/research/validation",
      destinationKind: "research",
    };
  }
  const conflicts = countConflictingInterpretations(models);
  if (conflicts > 0) {
    return {
      statusLabel: `${conflicts} contract-backed ${conflicts === 1 ? "conflict" : "conflicts"}`,
      statusTone: "caution",
      detail:
        "Only ABSTAIN_CONFLICTING_EVIDENCE is a conflict signal. This is not a contradiction score.",
      href: "/research/validation?conflict=1",
      destinationKind: "research",
    };
  }
  return {
    statusLabel: "None reported",
    statusTone: "neutral",
    detail:
      "No ABSTAIN_CONFLICTING_EVIDENCE rows in this window. Absence is not proof that evidence agrees.",
    href: "/research/validation",
    destinationKind: "research",
  };
}

function forwardTestNode(mode: ResearchSessionMode): Pick<
  ResearchClaimNode,
  "statusLabel" | "statusTone" | "detail" | "href" | "destinationKind" | "evidenceClass"
> {
  if (mode === "PAPER") {
    return {
      statusLabel: "Not on this surface",
      statusTone: "neutral",
      detail:
        "Account-bound Paper forward tests live in Workspace. This simulation is not a forward test. FTEP campaign state has no Research UI contract.",
      href: "/workspace",
      destinationKind: "related",
      evidenceClass: "Prospective paper forward-test (Workspace) · not this page",
    };
  }
  return {
    statusLabel: "NOT_EXPOSED",
    statusTone: "neutral",
    detail:
      "Governed FTEP campaign state is not on this surface. Paper Workspace holds account-bound forward tests; Demo/Live Research does not fetch them.",
    href: null,
    destinationKind: "gap",
    evidenceClass: "NOT_EXPOSED",
  };
}

/**
 * Claim graph for Overview. Status is payload-derived or an explicit gap token.
 * Does not invent hypotheses, contradiction scores, FTEP state, or live evidence.
 */
export function buildClaimNavigation(
  input: ResearchSynthesisInput,
  mode: ResearchSessionMode,
): ResearchClaimNode[] {
  const contradiction = contradictionNode(input.models);
  const forwardTest = forwardTestNode(mode);
  const availableFindings = input.analytics
    ? RESEARCH_FINDINGS.filter((finding) => researchPanel(input.analytics, finding.key)?.available)
        .length
    : 0;

  const nodes: Record<ResearchClaimNodeKey, ResearchClaimNode> = {
    source: {
      key: "source",
      title: CLAIM_TITLES.source,
      role: "Where the finding came from",
      statusLabel: input.analytics ? "Disclosed per finding" : "Unavailable",
      statusTone: input.analytics ? "research" : "neutral",
      detail: sourceNodeDetail(input.analytics),
      href: "/research/evidence",
      destinationKind: "research",
      evidenceClass: "Panel provenance.source / method only",
    },
    hypothesis: {
      key: "hypothesis",
      title: CLAIM_TITLES.hypothesis,
      role: "What claim is being tested",
      statusLabel: "NOT_EXPOSED",
      statusTone: "neutral",
      detail:
        "No hypothesis object or lifecycle endpoint. Closest contract: per-observation interpretations on Validation.",
      href: "/research/validation#research-interpretations-heading",
      destinationKind: "proxy",
      evidenceClass: "NOT_EXPOSED",
    },
    strategy: {
      key: "strategy",
      title: CLAIM_TITLES.strategy,
      role: "Which model and gates produced the claim",
      statusLabel: input.models ? presentPreregistration(input.models.preregistration_status).label : "Unavailable",
      statusTone: input.models
        ? presentPreregistration(input.models.preregistration_status).tone
        : "neutral",
      detail: strategyNodeDetail(input.models),
      href: "/research/validation",
      destinationKind: "research",
      evidenceClass: "Walk-forward validation (replay-bound)",
    },
    experiment: {
      key: "experiment",
      title: CLAIM_TITLES.experiment,
      role: "Deterministic simulation of the claim",
      statusLabel: input.simulation ? "Simulation record" : "Unavailable",
      statusTone: input.simulation ? "paper" : "neutral",
      detail: input.simulation
        ? `${input.simulation.ledger_summary.entry_count} ledger entries · bar-conservative simulator, not FTEP and not production readiness.`
        : "The simulation payload was not included.",
      href: "/research/simulation",
      destinationKind: "research",
      evidenceClass: "Simulated (deterministic) · not prospective forward-test",
    },
    evidence: {
      key: "evidence",
      title: CLAIM_TITLES.evidence,
      role: "What the current cutoff actually shows",
      statusLabel: input.analytics
        ? `${availableFindings} of ${RESEARCH_FINDINGS.length} findings`
        : "Unavailable",
      statusTone: input.analytics ? "research" : "neutral",
      detail: input.analytics
        ? "Analytics panels are distributions at cutoff — not ranked opportunities or proof."
        : "The analytics payload was not included.",
      href: "/research/evidence",
      destinationKind: "research",
      evidenceClass: "Mixed historical / replay / walk-forward / simulated — per finding",
    },
    contradiction: {
      key: "contradiction",
      title: CLAIM_TITLES.contradiction,
      role: "Whether evidence conflicted",
      ...contradiction,
      evidenceClass: "ABSTAIN_CONFLICTING_EVIDENCE only",
    },
    implementation: {
      key: "implementation",
      title: CLAIM_TITLES.implementation,
      role: "Recorded workflow to inspect",
      statusLabel: "Inspect in Lab",
      statusTone: "research",
      detail:
        "Research interprets results. Lab inspects the recorded validation/simulation workflow. No mutations from this page.",
      href: "/lab/validation",
      destinationKind: "related",
      evidenceClass: "Process surface (Lab) · not a new evidence class",
    },
    "forward-test": {
      key: "forward-test",
      title: CLAIM_TITLES["forward-test"],
      role: "Prospective status, if any",
      ...forwardTest,
    },
  };

  return CLAIM_NODE_ORDER.map((key) => nodes[key]);
}

export function buildClaimLineageReading(
  findingKey: ResearchPanelKey,
  input: ResearchSynthesisInput,
): string {
  const finding = researchFinding(findingKey);
  const panel = researchPanel(input.analytics, findingKey);
  const availability = presentFindingAvailability(panel);
  const source = panel?.provenance?.source ? String(panel.provenance.source) : "UNAVAILABLE";
  return (
    `Following ${finding.title}: ${availability.label.toLowerCase()} · source ${source}. ` +
    `${finding.claim} Off-path nodes stay visible as gaps or other findings — they are not this claim.`
  );
}

/**
 * Finding-scoped view of the eight-node graph. Reuses `buildClaimNavigation`;
 * does not invent a second graph or extra fetches.
 */
export function buildClaimLineage(
  input: ResearchSynthesisInput,
  mode: ResearchSessionMode,
  findingKey: ResearchPanelKey,
): ResearchClaimLineage {
  const onPath = new Set(claimPathKeys(findingKey));
  const finding = researchFinding(findingKey);
  const panel = researchPanel(input.analytics, findingKey);
  const availability = presentFindingAvailability(panel);
  const source = panel?.provenance?.source ? String(panel.provenance.source) : "UNAVAILABLE";
  const method = panel?.provenance?.method ? String(panel.provenance.method) : "UNAVAILABLE";

  const nodes = buildClaimNavigation(input, mode).map((node) => {
    let next: ResearchClaimLineageNode = {
      ...node,
      relation: onPath.has(node.key) ? "on-path" : "off-path",
      href: withResearchClaimQuery(node.href, findingKey),
    };
    if (node.key === "source") {
      next = {
        ...next,
        href: withResearchClaimQuery(`/research/evidence?panel=${findingKey}`, findingKey),
        detail: onPath.has("source")
          ? `This finding discloses provenance.source ${source} and method ${method}. No source-catalog endpoint exists.`
          : next.detail,
      };
    }
    if (node.key === "evidence") {
      next = {
        ...next,
        href: withResearchClaimQuery(`/research/evidence?panel=${findingKey}`, findingKey),
        statusLabel: input.analytics ? availability.label : "Unavailable",
        statusTone: availability.tone,
        detail: `${finding.title}: ${availability.detail}`,
      };
    }
    if (next.relation === "off-path") {
      next = {
        ...next,
        detail: `${next.detail} Not on this finding's path.`,
      };
    }
    return next;
  });

  return {
    findingKey,
    findingTitle: finding.title,
    reading: buildClaimLineageReading(findingKey, input),
    nodes,
  };
}

export function pickClaimNodes(
  nodes: ReadonlyArray<ResearchClaimNode>,
  keys: ReadonlyArray<ResearchClaimNodeKey>,
): ResearchClaimNode[] {
  return keys
    .map((key) => nodes.find((node) => node.key === key))
    .filter((node): node is ResearchClaimNode => node != null);
}

/** Static hops for section pages that fetch only their own endpoint. */
export function claimHopsForFinding(
  key: ResearchPanelKey,
  mode: ResearchSessionMode,
): ClaimHop[] {
  const forwardTestHref = forwardTestWorkspaceHref(mode);
  const shared: Record<ResearchClaimNodeKey, ClaimHop> = {
    source: {
      key: "source",
      title: CLAIM_TITLES.source,
      href: "/research/evidence",
      note: "Provenance is per panel — there is no source catalog.",
    },
    hypothesis: {
      key: "hypothesis",
      title: CLAIM_TITLES.hypothesis,
      href: "/research/validation#research-interpretations-heading",
      note: "NOT_EXPOSED as an object; interpretations are the proxy.",
    },
    strategy: {
      key: "strategy",
      title: CLAIM_TITLES.strategy,
      href: "/research/validation",
      note: "Walk-forward model record.",
    },
    experiment: {
      key: "experiment",
      title: CLAIM_TITLES.experiment,
      href: "/research/simulation",
      note: "Deterministic simulation — not a forward test.",
    },
    evidence: {
      key: "evidence",
      title: CLAIM_TITLES.evidence,
      href: "/research/evidence",
      note: "Findings at the current cutoff.",
    },
    contradiction: {
      key: "contradiction",
      title: CLAIM_TITLES.contradiction,
      href: "/research/validation?conflict=1",
      note: "Only ABSTAIN_CONFLICTING_EVIDENCE is a conflict signal.",
    },
    implementation: {
      key: "implementation",
      title: CLAIM_TITLES.implementation,
      href: "/lab/validation",
      note: "Inspect the recorded workflow in Lab.",
    },
    "forward-test": {
      key: "forward-test",
      title: CLAIM_TITLES["forward-test"],
      href: forwardTestHref,
      note: forwardTestHref
        ? "Paper forward tests are in Workspace, not Research."
        : "Forward-test and FTEP status are NOT_EXPOSED on this surface.",
    },
  };

  const scoped = (hop: ClaimHop): ClaimHop => ({
    ...hop,
    href: withResearchClaimQuery(hop.href, key),
  });
  return claimPathKeys(key).map((hopKey) => {
    const hop = shared[hopKey];
    if (hopKey === "source" || hopKey === "evidence") {
      return scoped({
        ...hop,
        href: `/research/evidence?panel=${key}`,
      });
    }
    return scoped(hop);
  });
}

function scopeSectionHops(hops: ClaimHop[], findingKey?: ResearchPanelKey): ClaimHop[] {
  if (!findingKey) return hops;
  return hops.map((hop) => ({ ...hop, href: withResearchClaimQuery(hop.href, findingKey) }));
}

export function sectionClaimHops(
  section: Exclude<ResearchSectionKey, "overview">,
  mode: ResearchSessionMode,
  findingKey?: ResearchPanelKey,
): ClaimHop[] {
  const forwardTestHref = forwardTestWorkspaceHref(mode);
  if (section === "evidence") {
    return scopeSectionHops(
      [
        { key: "strategy", title: CLAIM_TITLES.strategy, href: "/research/validation", note: "Validation record." },
        {
          key: "contradiction",
          title: CLAIM_TITLES.contradiction,
          href: "/research/validation?conflict=1",
          note: "Conflict abstentions only.",
        },
        {
          key: "experiment",
          title: CLAIM_TITLES.experiment,
          href: "/research/simulation",
          note: "Simulation, not FTEP.",
        },
      ],
      findingKey,
    );
  }
  if (section === "validation") {
    return scopeSectionHops(
      [
        {
          key: "evidence",
          title: CLAIM_TITLES.evidence,
          href: findingKey ? `/research/evidence?panel=${findingKey}` : "/research/evidence",
          note: "Findings at cutoff.",
        },
        {
          key: "experiment",
          title: CLAIM_TITLES.experiment,
          href: "/research/simulation",
          note: "Deterministic simulation.",
        },
        {
          key: "implementation",
          title: CLAIM_TITLES.implementation,
          href: "/lab/validation",
          note: "Lab process surface.",
        },
        {
          key: "forward-test",
          title: CLAIM_TITLES["forward-test"],
          href: forwardTestHref,
          note: forwardTestHref ? "Workspace holds Paper forward tests." : "NOT_EXPOSED here.",
        },
      ],
      findingKey,
    );
  }
  return scopeSectionHops(
    [
      { key: "strategy", title: CLAIM_TITLES.strategy, href: "/research/validation", note: "Model that fed this run." },
      {
        key: "evidence",
        title: CLAIM_TITLES.evidence,
        href: findingKey ? `/research/evidence?panel=${findingKey}` : "/research/evidence",
        note: "Findings at cutoff.",
      },
      {
        key: "forward-test",
        title: CLAIM_TITLES["forward-test"],
        href: forwardTestHref,
        note: "This run is simulated, not a prospective forward test.",
      },
      {
        key: "implementation",
        title: CLAIM_TITLES.implementation,
        href: "/lab/simulation",
        note: "Inspect simulation workflow in Lab.",
      },
    ],
    findingKey,
  );
}

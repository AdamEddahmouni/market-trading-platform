import type { OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";

/** Honesty labels shown to operators. Thesis is never OBSERVED. */
export type ProvenanceHonesty = "OBSERVED" | "DERIVED" | "ASSERTED" | "INFERRED" | "UNKNOWN";

export type DecisionProvenanceField = {
  label: string;
  value: string;
  honesty: ProvenanceHonesty;
  /** AI-assisted / non-authoritative rows — render separately. */
  nonAuthoritative?: boolean;
};

export type DecisionProvenancePresentation = {
  present: boolean;
  fields: DecisionProvenanceField[];
  aiAssistedNotes: DecisionProvenanceField[];
};

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  if (Array.isArray(value)) {
    const parts = value.map((item) => String(item).trim()).filter(Boolean);
    return parts.length ? parts.join(", ") : "UNAVAILABLE";
  }
  return String(value);
}

function readDecisionProvenance(
  evidence?: OpportunityEvidenceResponse | null,
  row?: OpportunityReviewRow | null,
): Record<string, unknown> | undefined {
  const fromEvidence = asRecord((evidence as { decision_provenance?: unknown } | null | undefined)?.decision_provenance);
  if (fromEvidence) return fromEvidence;
  const rowRecord = row as { decision_provenance?: unknown; metadata?: unknown } | null | undefined;
  const fromRow = asRecord(rowRecord?.decision_provenance);
  if (fromRow) return fromRow;
  const metadata = asRecord(rowRecord?.metadata);
  return asRecord(metadata?.decision_provenance);
}

/** Thesis honesty is never OBSERVED — coerce accidental OBSERVED to ASSERTED. */
export function classifyThesisHonesty(raw: unknown): ProvenanceHonesty {
  const value = String(raw ?? "").trim().toUpperCase();
  if (value === "DERIVED") return "DERIVED";
  if (value === "INFERRED") return "INFERRED";
  if (value === "UNKNOWN" || !value) return "UNKNOWN";
  if (value === "OBSERVED") return "ASSERTED";
  if (value === "ASSERTED") return "ASSERTED";
  return "ASSERTED";
}

function formatFreshnessWindow(window: Record<string, unknown> | undefined): string {
  if (!window) return "UNAVAILABLE";
  const parts: string[] = [];
  if (window.policy_name) parts.push(`policy ${display(window.policy_name)}`);
  if (window.status) parts.push(`status ${display(window.status)}`);
  if (window.information_cutoff_ns != null) parts.push(`cutoff_ns ${display(window.information_cutoff_ns)}`);
  if (window.valid_until_ns != null) parts.push(`valid_until_ns ${display(window.valid_until_ns)}`);
  if (window.stale_after_ns != null) parts.push(`stale_after_ns ${display(window.stale_after_ns)}`);
  return parts.length ? parts.join(" · ") : "UNAVAILABLE";
}

function formatActionability(actionability: Record<string, unknown> | undefined): string {
  if (!actionability) return "UNAVAILABLE";
  const status = display(actionability.status);
  const still = Array.isArray(actionability.still_actionable_reasons)
    ? actionability.still_actionable_reasons.map(String).filter(Boolean)
    : [];
  const noLonger = Array.isArray(actionability.no_longer_actionable_reasons)
    ? actionability.no_longer_actionable_reasons.map(String).filter(Boolean)
    : [];
  if (still.length) return `${status} — still actionable: ${still.join(", ")}`;
  if (noLonger.length) return `${status} — not actionable: ${noLonger.join(", ")}`;
  return status;
}

/**
 * Smallest operator-facing projection of already-landed decision provenance.
 * Backend fields only — no invented scores. Thesis is never labeled OBSERVED.
 */
export function buildDecisionProvenancePresentation(
  evidence?: OpportunityEvidenceResponse | null,
  row?: OpportunityReviewRow | null,
): DecisionProvenancePresentation {
  const provenance = readDecisionProvenance(evidence, row);
  if (!provenance) {
    return { present: false, fields: [], aiAssistedNotes: [] };
  }

  const thesis = asRecord(provenance.thesis);
  const thesisHonesty = classifyThesisHonesty(thesis?.honesty);
  const originParts = [display(provenance.origin_kind)];
  if (provenance.strategy_id) originParts.push(`strategy ${display(provenance.strategy_id)}`);
  if (provenance.strategy_family) originParts.push(`family ${display(provenance.strategy_family)}`);

  const invalidation =
    Array.isArray(thesis?.invalidation_criteria) && thesis.invalidation_criteria.length
      ? display(thesis.invalidation_criteria)
      : Array.isArray((evidence as { invalidation_criteria?: unknown } | null | undefined)?.invalidation_criteria)
        ? display((evidence as { invalidation_criteria?: unknown }).invalidation_criteria)
        : "UNAVAILABLE";

  const actionability =
    asRecord(provenance.actionability) ??
    asRecord((evidence as { actionability_audit?: unknown } | null | undefined)?.actionability_audit);

  const fields: DecisionProvenanceField[] = [
    {
      label: "Origin",
      value: originParts.join(" · "),
      honesty: "DERIVED",
    },
    {
      label: "Thesis statement",
      value: thesis?.statement
        ? `${display(thesis.statement)} (${thesisHonesty === "DERIVED" ? "derived" : "asserted"} — not an observed market fact)`
        : "UNAVAILABLE",
      honesty: thesisHonesty === "DERIVED" ? "DERIVED" : "ASSERTED",
    },
    {
      label: "Invalidation criteria",
      value: invalidation,
      honesty: "DERIVED",
    },
    {
      label: "Freshness window",
      value: formatFreshnessWindow(asRecord(provenance.freshness_window)),
      honesty: "DERIVED",
    },
    {
      label: "Why still actionable / why not",
      value: formatActionability(actionability),
      honesty: "DERIVED",
    },
  ];

  const notesRaw = Array.isArray(provenance.ai_assisted_notes) ? provenance.ai_assisted_notes : [];
  const aiAssistedNotes: DecisionProvenanceField[] = notesRaw
    .map((note) => String(note).trim())
    .filter(Boolean)
    .map((note) => ({
      label: "AI-assisted note",
      value: note,
      honesty: "INFERRED" as const,
      nonAuthoritative: true,
    }));

  if (!aiAssistedNotes.length) {
    aiAssistedNotes.push({
      label: "AI-assisted notes",
      value: "None attached — AI notes are non-authoritative and never authorize state changes",
      honesty: "UNKNOWN",
      nonAuthoritative: true,
    });
  }

  return { present: true, fields, aiAssistedNotes };
}

"""Human sentences for the canonical diagnostic and blocking codes.

The mapping is presentation only: it never changes an outcome and never invents a reason.
A code with no entry is shown verbatim, so an unmapped code is visible rather than
silently swallowed.
"""

from __future__ import annotations

#: Phase 3A evaluation explanation / diagnostic codes.
EVALUATION_REASONS: dict[str, str] = {
    "EVALUATION_CONDITION_SATISFIED": "The rule condition was met by admissible evidence.",
    "EVALUATION_CONDITION_NOT_SATISFIED": (
        "Admissible evidence was present and the rule condition was not met."
    ),
    "EVALUATION_PROVIDER_SCOPE_REQUIRED": (
        "The rule requires an explicit provider scope for its input, and no admissible "
        "provider-scoped evidence exists at the detection boundary."
    ),
    "EVALUATION_REQUIRED_DOMAIN_MISSING": (
        "A required evidence domain is absent from the frozen evidence set."
    ),
    "EVALUATION_REQUIRED_DOMAIN_UNKNOWN": "A required evidence domain has unknown status.",
    "EVALUATION_REQUIRED_DOMAIN_CONFLICTED": "A required evidence domain is conflicted.",
    "EVALUATION_RELATIVE_VOLUME_UNAVAILABLE": (
        "Relative volume is unavailable: historical volume units and corporate-action "
        "semantics remain unresolved, so no volume-derived value is admissible."
    ),
    "EVALUATION_SHORT_INTEREST_UNAVAILABLE": (
        "Published short interest was never collected for this detection boundary."
    ),
    "EVALUATION_SHORT_INTEREST_CHANGE_UNAVAILABLE": (
        "No short-interest time series exists, so its change cannot be observed."
    ),
    "EVALUATION_DAYS_TO_COVER_UNAVAILABLE": (
        "Days to cover requires short interest and admissible volume; neither is available."
    ),
    "EVALUATION_BORROW_FEE_UNAVAILABLE": (
        "No borrow-fee provider is configured, so no borrow fee was collected."
    ),
    "EVALUATION_BORROW_AVAILABILITY_UNAVAILABLE": (
        "No borrow-availability provider is configured, so no borrow availability was collected."
    ),
    "EVALUATION_NEWS_UNAVAILABLE": (
        "No news evidence was collected for this detection boundary."
    ),
    "EVALUATION_NEWS_TIMESTAMP_UNKNOWN": "News exists but its publication time is unknown.",
    "EVALUATION_NEWS_AFTER_AS_OF": "The only news found is dated after the detection boundary.",
    "EVALUATION_SEC_FILING_UNAVAILABLE": (
        "No SEC filing evidence was collected for this detection boundary."
    ),
    "EVALUATION_CORPORATE_ACTION_UNAVAILABLE": (
        "No corporate-action context was collected for this detection boundary."
    ),
    "EVALUATION_FLOAT_UNAVAILABLE": "No float provider is configured, so float was not collected.",
    "EVALUATION_PRICE_UNAVAILABLE": "No admissible price observation exists.",
    "EVALUATION_RETURN_UNAVAILABLE": "No admissible return metric could be computed.",
    "EVALUATION_PARTIAL_BAR": "The boundary bar was not definitely completed.",
    "EVALUATION_INPUT_UNAVAILABLE": "The rule input is unavailable.",
    "EVALUATION_INPUT_CONFLICTED": "The rule inputs conflict with one another.",
    "EVALUATION_INPUT_INSUFFICIENT": "The rule inputs are insufficient.",
    "EVALUATION_UNIT_INCOMPATIBLE": "The rule inputs use incompatible units.",
    "EVALUATION_REQUIRED_HISTORY_INSUFFICIENT": "Insufficient history for the rule window.",
    "EVALUATION_DEFAULT_SUBSTITUTION_FORBIDDEN": (
        "A default value would have been substituted, which the policy forbids."
    ),
    "EVALUATION_NOT_APPLICABLE": "The rule does not apply to this asset class.",
    "EVALUATION_REPORTING_PERIOD_TOO_OLD": "The reporting period is too old to be admissible.",
}

#: Batch 08 blocking reason codes — why a rule received no substantive evidence.
BLOCKING_REASONS: dict[str, str] = {
    "ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07": (
        "Absolute price levels are inadmissible: Batch 06 resolved the provider price "
        "series as split-adjusted, so an absolute level at a past boundary cannot be "
        "trusted. Price ratios remain admissible."
    ),
    "VOLUME_SEMANTICS_BLOCKED_BY_BATCH07": (
        "Volume is inadmissible: the provider's volume unit and its corporate-action "
        "treatment are unresolved in the official documentation."
    ),
    "REQUIRED_DOMAIN_ABSENT_FROM_EVIDENCE": (
        "The evidence domain this rule needs was never collected for these cases."
    ),
    "EVIDENCE_META_RULE_NOT_BAR_DEPENDENT": (
        "This is an evidence meta-rule; it depends on the evidence set rather than on bars."
    ),
    "NO_DETECTION_TIME_EVIDENCE_EXISTS": (
        "No lawful non-authenticated source produced this evidence at the detection "
        "boundary, so nothing was collected."
    ),
}

#: Batch 09 research-detection reason prefixes.
DETECTION_REASONS: dict[str, str] = {
    "REQUIRED_RULE_UNKNOWN": (
        "A rule required by the research-detection predicate is UNKNOWN, so detection "
        "cannot be evaluated either way."
    ),
    "REQUIRED_RULE_CONFLICTED": "A required rule is CONFLICTED, so detection is unevaluable.",
    "REQUIRED_RULE_INSUFFICIENT_DATA": (
        "A required rule has insufficient data, so detection is unevaluable."
    ),
}

#: Batch 09 skip diagnostics — why a case produced no research dataset row.
SKIP_REASONS: dict[str, str] = {
    "RESEARCH_CASE_OUTCOME_MISSING": (
        "No forward outcome window has been lawfully acquired for this case."
    ),
    "RESEARCH_CASE_STATUS_INCOMPLETE": (
        "The case is evaluation-only: a Phase 3A evaluation exists but the outcome side "
        "does not, so the case is skipped rather than failed."
    ),
}


def explain_evaluation(code: str | None) -> str:
    """Sentence for an evaluation code. Unmapped codes are echoed verbatim."""
    if not code:
        return "No explanation code was recorded."
    return EVALUATION_REASONS.get(code, code)


def explain_blocking(codes: list[str] | tuple[str, ...] | None) -> list[str]:
    """Sentences for blocking reason codes, preserving order and echoing unmapped ones."""
    if not codes:
        return []
    return [BLOCKING_REASONS.get(code, code) for code in codes]


def explain_detection(reasons: list[str] | tuple[str, ...] | None) -> list[str]:
    """Sentences for research-detection reasons of the form ``PREFIX:RULE_ID``."""
    out: list[str] = []
    for reason in reasons or ():
        prefix, _, detail = reason.partition(":")
        sentence = DETECTION_REASONS.get(prefix)
        if sentence is None:
            out.append(reason)
        elif detail:
            out.append(f"{sentence} (rule: {detail})")
        else:
            out.append(sentence)
    return out


def explain_skip(codes: list[str] | tuple[str, ...] | None) -> list[str]:
    """Sentences for Batch 09 skip diagnostics."""
    return [SKIP_REASONS.get(code, code) for code in codes or ()]


__all__ = [
    "BLOCKING_REASONS",
    "DETECTION_REASONS",
    "EVALUATION_REASONS",
    "SKIP_REASONS",
    "explain_blocking",
    "explain_detection",
    "explain_evaluation",
    "explain_skip",
]

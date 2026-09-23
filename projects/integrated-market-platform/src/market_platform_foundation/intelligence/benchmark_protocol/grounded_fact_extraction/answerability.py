"""Answerability classification for grounded factual probes (no evaluator gold)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AnswerabilityClass(StrEnum):
    """Whether admitted/harness evidence can support a factual answer."""

    ANSWERABLE = "ANSWERABLE"
    ABSENT_EVIDENCE = "ABSENT_EVIDENCE"
    NEGATIVE_EVIDENCE = "NEGATIVE_EVIDENCE"
    CAPABILITY_ABSENT = "CAPABILITY_ABSENT"
    CONTRADICTING_EVIDENCE = "CONTRADICTING_EVIDENCE"
    UNANSWERABLE_PROBE = "UNANSWERABLE_PROBE"


# Blind-mode capability tokens used by the IBP facts SUT (bar fixtures cover quotes/trades only).
_BAR_BACKED_CAPABILITIES = frozenset({"QUOTES", "TRADES"})
_BLIND_MODE_REQUIRED_CAPABILITIES: dict[str, frozenset[str]] = {
    "A": frozenset({"QUOTES", "TRADES"}),
    "B": frozenset({"OPTIONS_CHAIN"}),
    "C": frozenset({"SHORT_INTEREST"}),
    "D": frozenset({"NEWS"}),
    "E": frozenset({"MACRO", "QUOTES"}),
}


def available_capabilities_from_payload(payload: Any) -> frozenset[str]:
    """Infer which intelligence capabilities a projected payload can support."""
    if payload is None:
        return frozenset()
    if isinstance(payload, dict) and payload and all(isinstance(v, list) for v in payload.values()):
        return frozenset(_BAR_BACKED_CAPABILITIES)
    if isinstance(payload, list) and payload:
        return frozenset(_BAR_BACKED_CAPABILITIES)
    if isinstance(payload, dict):
        caps: set[str] = set()
        keys = {str(k).casefold() for k in payload.keys()}
        if "options" in keys or "options_chain" in keys:
            caps.add("OPTIONS_CHAIN")
        if "short_interest" in keys or "borrow" in keys:
            caps.add("SHORT_INTEREST")
        if "news" in keys or "headlines" in keys:
            caps.add("NEWS")
        if "macro" in keys or "regime" in keys:
            caps.add("MACRO")
        if "bars" in keys or "rows" in keys or any(
            isinstance(v, list) for v in payload.values()
        ):
            caps.update(_BAR_BACKED_CAPABILITIES)
        return frozenset(caps)
    return frozenset()


def classify_answerability(
    *,
    blind_mode: str | None,
    evidence_present: bool,
    available_capabilities: frozenset[str] | set[str] | None = None,
    conflicting: bool = False,
    negative_fact_present: bool = False,
    question_class: str | None = None,
) -> AnswerabilityClass:
    """Classify whether a factual probe should answer, abstain, or report polarity."""
    if conflicting:
        return AnswerabilityClass.CONTRADICTING_EVIDENCE
    if not evidence_present:
        return AnswerabilityClass.ABSENT_EVIDENCE

    # Capability gating applies only when a blind mode is explicitly supplied
    # (legacy Smoke10 harness path). Admitted factual questions pass blind_mode=None.
    if blind_mode is not None:
        mode = str(blind_mode)
        required = _BLIND_MODE_REQUIRED_CAPABILITIES.get(mode, frozenset())
        available = frozenset(available_capabilities or ())
        if required and not required.issubset(available):
            return AnswerabilityClass.CAPABILITY_ABSENT

    if question_class in {"ABSTENTION", "UNANSWERABLE_METRIC"}:
        return AnswerabilityClass.UNANSWERABLE_PROBE

    if negative_fact_present:
        return AnswerabilityClass.NEGATIVE_EVIDENCE

    return AnswerabilityClass.ANSWERABLE


def abstention_reason_for(answerability: AnswerabilityClass) -> str | None:
    mapping = {
        AnswerabilityClass.ABSENT_EVIDENCE: "ABSENT_HARNESS_EVIDENCE",
        AnswerabilityClass.CAPABILITY_ABSENT: "CAPABILITY_EVIDENCE_ABSENT",
        AnswerabilityClass.CONTRADICTING_EVIDENCE: "CONFLICTING_EVIDENCE",
        AnswerabilityClass.UNANSWERABLE_PROBE: "PROBE_NOT_ANSWERABLE_FROM_EVIDENCE",
        AnswerabilityClass.NEGATIVE_EVIDENCE: None,
        AnswerabilityClass.ANSWERABLE: None,
    }
    return mapping[answerability]


__all__ = [
    "AnswerabilityClass",
    "abstention_reason_for",
    "available_capabilities_from_payload",
    "classify_answerability",
]

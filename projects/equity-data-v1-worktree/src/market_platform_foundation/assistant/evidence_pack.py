"""Shared evidence selection and packaging for assistant inference."""

from __future__ import annotations

import json
from typing import Any

from .intent_router import AssistantIntent, route_intent


def format_explanation(explain_payload: dict[str, object], *, ref: str) -> str:
    explanation = explain_payload.get("explanation")
    if not isinstance(explanation, dict):
        return f"Evidence at {ref} is unavailable."
    meaning = str(explanation.get("meaning", ""))
    alignment = str(explanation.get("alignment_summary", ""))
    why = str(explanation.get("why", ""))
    parts = [part for part in (meaning, alignment, why) if part]
    return " — ".join(parts) if parts else f"Evidence at {ref} has no narrative."


def pick_explain_ref(
    intent: AssistantIntent,
    *,
    evidence_context: dict[str, Any],
    prompt: str,
) -> str | None:
    selection_ref = evidence_context.get("selection_ref")
    if isinstance(selection_ref, str) and selection_ref:
        if selection_ref.startswith("explain:"):
            return selection_ref
        if selection_ref.startswith("inspect:"):
            return selection_ref.replace("inspect:", "explain:", 1)

    available = {str(ref) for ref in evidence_context.get("available_explain_refs", ()) if ref}
    instrument_id = str(evidence_context.get("instrument_id", "")).upper()
    normalized = prompt.lower()

    if intent == "quality":
        return "explain:quality:system" if "explain:quality:system" in available else None
    if intent == "summary":
        return "explain:replay:context" if "explain:replay:context" in available else None
    if intent == "strategy":
        strategy_refs = sorted(ref for ref in available if ref.startswith("explain:strategy:"))
        return strategy_refs[-1] if strategy_refs else None
    if intent in {"explain", "instrument"}:
        if instrument_id and f"explain:disclosure:{instrument_id}" in available:
            return f"explain:disclosure:{instrument_id}"
        return "explain:replay:context" if "explain:replay:context" in available else None
    if intent == "institutional":
        for keyword, prefix in (
            ("disclosure", "explain:disclosure:"),
            ("order flow", "explain:order-flow:"),
            ("order-flow", "explain:order-flow:"),
            ("options", "explain:options:"),
            ("futures", "explain:futures:"),
            ("catalyst", "explain:catalyst:"),
            ("squeeze", "explain:squeeze:"),
            ("large", "explain:large-transactions:"),
            ("order book", "explain:order-book:"),
            ("fund", "explain:fund-etf:"),
            ("etf", "explain:fund-etf:"),
        ):
            if keyword in normalized:
                matches = [ref for ref in available if ref.startswith(prefix)]
                if matches:
                    return matches[0]
        families = evidence_context.get("institutional_flow", {}).get("families", [])
        if isinstance(families, list):
            for row in families:
                if isinstance(row, dict) and row.get("available") and row.get("explanation_ref"):
                    return str(row["explanation_ref"])
    if intent == "conflict":
        return _conflict_explain_ref(evidence_context)
    if intent == "what_changed":
        return _what_changed_explain_ref(evidence_context)
    if intent == "show_source":
        if selection_ref and isinstance(selection_ref, str):
            return (
                selection_ref
                if selection_ref.startswith("explain:")
                else selection_ref.replace("inspect:", "explain:", 1)
            )
        return "explain:replay:context" if "explain:replay:context" in available else None
    return "explain:replay:context" if "explain:replay:context" in available else None


def collect_explain_refs(
    intent: AssistantIntent,
    *,
    evidence_context: dict[str, Any],
    prompt: str,
    max_refs: int = 8,
) -> list[str]:
    available = [str(ref) for ref in evidence_context.get("available_explain_refs", ()) if ref]
    refs: list[str] = []
    primary = pick_explain_ref(intent, evidence_context=evidence_context, prompt=prompt)
    if primary:
        refs.append(primary)

    if intent == "conflict":
        families = evidence_context.get("institutional_flow", {}).get("families", [])
        if isinstance(families, list):
            for row in families:
                if isinstance(row, dict) and row.get("available") and row.get("explanation_ref"):
                    ref = str(row["explanation_ref"])
                    if ref not in refs:
                        refs.append(ref)
    else:
        for ref in available:
            if ref not in refs:
                refs.append(ref)

    for baseline in ("explain:replay:context", "explain:quality:system"):
        if baseline in available and baseline not in refs:
            refs.append(baseline)
    return refs[:max_refs]


def build_evidence_pack(
    prompt: str,
    evidence_context: dict[str, Any],
    *,
    max_refs: int = 8,
) -> dict[str, object]:
    resolve_explain = evidence_context.get("resolve_explain")
    intent = route_intent(prompt)
    items: list[dict[str, object]] = []
    refs = collect_explain_refs(intent, evidence_context=evidence_context, prompt=prompt, max_refs=max_refs)
    if callable(resolve_explain):
        for ref in refs:
            try:
                payload = resolve_explain(ref)
            except ValueError:
                continue
            explanation = payload.get("explanation")
            if isinstance(explanation, dict):
                items.append(
                    {
                        "ref": ref,
                        "alignment_summary": explanation.get("alignment_summary"),
                        "meaning": explanation.get("meaning"),
                        "why": explanation.get("why"),
                    }
                )
    allowed_refs = list(refs)
    for ref in evidence_context.get("available_explain_refs", ()):
        ref_str = str(ref)
        if ref_str and ref_str not in allowed_refs:
            allowed_refs.append(ref_str)
    return {
        "allowed_citation_refs": allowed_refs,
        "as_of_context": evidence_context.get("as_of_context"),
        "instrument_id": evidence_context.get("instrument_id"),
        "intent": intent,
        "items": items,
        "quality": evidence_context.get("quality"),
        "selection_ref": evidence_context.get("selection_ref"),
    }


def evidence_pack_prompt_text(pack: dict[str, object]) -> str:
    return json.dumps(pack, indent=2, sort_keys=True)


def build_conflict_answer(evidence_context: dict[str, Any], resolve_explain: Any) -> tuple[str, tuple[str, ...]]:
    families = evidence_context.get("institutional_flow", {}).get("families", [])
    if not isinstance(families, list):
        return "No institutional families are loaded for conflict review.", ()
    available = [row for row in families if isinstance(row, dict) and row.get("available")]
    if len(available) < 2:
        return (
            "Only one or zero whale families are available at this cursor; "
            "no cross-family conflict can be assessed.",
            ("explain:quality:system",),
        )
    refs: list[str] = []
    lines: list[str] = []
    for row in available[:4]:
        ref = str(row.get("explanation_ref", ""))
        if not ref:
            continue
        try:
            payload = resolve_explain(ref)
            explanation = payload.get("explanation", {})
            if isinstance(explanation, dict):
                lines.append(
                    f"{row.get('label', row.get('family_id'))}: "
                    f"{explanation.get('alignment_summary', 'UNKNOWN')}"
                )
                refs.append(ref)
        except ValueError:
            continue
    if not lines:
        return "Conflicting-evidence review could not resolve any family explanations.", ()
    content = (
        "Cross-family alignment summary (research-only, not a consensus score): "
        + "; ".join(lines)
    )
    return content, tuple(refs)


def _conflict_explain_ref(evidence_context: dict[str, Any]) -> str | None:
    families = evidence_context.get("institutional_flow", {}).get("families", [])
    if not isinstance(families, list):
        return None
    available_rows = [row for row in families if isinstance(row, dict) and row.get("available")]
    if len(available_rows) < 2:
        return "explain:quality:system"
    return str(available_rows[0].get("explanation_ref", "")) or None


def _what_changed_explain_ref(evidence_context: dict[str, Any]) -> str | None:
    selection_ref = evidence_context.get("selection_ref")
    if isinstance(selection_ref, str) and selection_ref.startswith("inspect:squeeze:"):
        return selection_ref.replace("inspect:", "explain:", 1)
    strategy_refs = [
        str(ref)
        for ref in evidence_context.get("available_explain_refs", ())
        if str(ref).startswith("explain:strategy:")
    ]
    if strategy_refs:
        return sorted(strategy_refs)[-1]
    return "explain:replay:context"

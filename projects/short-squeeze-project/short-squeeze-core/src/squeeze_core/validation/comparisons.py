"""Original-versus-rebuilt field comparison.

Comparison answers a narrow question: do two recorded values agree, and are they even
the same kind of quantity? It never judges whether a rule was correct -- that is
rule_validation.py's job, deliberately kept separate so a value differing is not
mistaken for a rule being wrong.
"""

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from .identifiers import deterministic_validation_id, field_comparison_identity
from .models import ComparisonState, FieldComparisonEntry, OriginalFieldValue, OriginalValueState

# Units that measure genuinely different quantities. Comparing across a pair here is a
# semantic error, not a value difference: a percent-of-float and an absolute share
# count can never "agree" no matter what numbers they carry.
_INCOMPATIBLE_UNIT_PAIRS = frozenset(
    {
        frozenset({"PERCENT_OF_FLOAT", "SHARES"}),
        frozenset({"PERCENT", "SHARES"}),
        frozenset({"PERCENT_OF_FLOAT", "DAYS"}),
        frozenset({"PERCENT", "DAYS"}),
        frozenset({"SHARES", "DAYS"}),
        frozenset({"USD", "PERCENT"}),
        frozenset({"USD", "SHARES"}),
    }
)

# Units that describe the same quantity in different scales, so a normalized match is
# meaningful. Value is the multiplier converting the first unit into the second.
_NORMALIZABLE_UNITS = {
    ("PERCENT_FRACTION", "PERCENT"): Decimal("100"),
    ("MILLION_SHARES", "SHARES"): Decimal("1000000"),
    ("BASIS_POINTS", "PERCENT"): Decimal("0.01"),
}


def _as_decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None
    return None


def _units_incompatible(original_unit: str | None, rebuilt_unit: str | None) -> bool:
    if original_unit is None or rebuilt_unit is None:
        return False
    if original_unit == rebuilt_unit:
        return False
    return frozenset({original_unit, rebuilt_unit}) in _INCOMPATIBLE_UNIT_PAIRS


def _normalization_factor(original_unit: str | None, rebuilt_unit: str | None) -> Decimal | None:
    if original_unit is None or rebuilt_unit is None or original_unit == rebuilt_unit:
        return None
    forward = _NORMALIZABLE_UNITS.get((original_unit, rebuilt_unit))
    if forward is not None:
        return forward
    reverse = _NORMALIZABLE_UNITS.get((rebuilt_unit, original_unit))
    if reverse is not None and reverse != 0:
        return Decimal("1") / reverse
    return None


def classify_comparison(
    original: OriginalFieldValue | None,
    rebuilt_value: object | None,
    *,
    rebuilt_unit: str | None = None,
    rebuilt_available: bool = True,
    mislabeled: bool = False,
) -> ComparisonState:
    """Resolve the comparison state for one field.

    Order matters. Mislabeling and semantic incompatibility are checked before any
    numeric comparison, because two numbers that happen to be close say nothing when
    they measure different quantities.
    """

    if mislabeled:
        return ComparisonState.ORIGINAL_MISLABELED

    if original is None or original.state is OriginalValueState.UNKNOWN:
        if not rebuilt_available or rebuilt_value is None:
            return ComparisonState.UNKNOWN
        return ComparisonState.ORIGINAL_MISSING

    if original.state is OriginalValueState.MISSING_IN_ARTIFACT:
        return ComparisonState.ORIGINAL_MISSING

    if original.state is OriginalValueState.DEFAULT_SUBSTITUTED:
        return ComparisonState.ORIGINAL_DEFAULT_SUBSTITUTION

    if not rebuilt_available or rebuilt_value is None:
        return ComparisonState.REBUILT_UNAVAILABLE

    if _units_incompatible(original.unit, rebuilt_unit):
        return ComparisonState.DIFFERENT_SEMANTICS

    if original.state is OriginalValueState.AMBIGUOUS:
        return ComparisonState.INCOMPARABLE

    original_number = _as_decimal(original.value)
    rebuilt_number = _as_decimal(rebuilt_value)

    if original_number is None or rebuilt_number is None:
        if isinstance(original.value, bool) and isinstance(rebuilt_value, bool):
            return ComparisonState.MATCH if original.value == rebuilt_value else ComparisonState.DIFFERENT_VALUE
        # Two non-numeric strings (timestamps, headlines, provider names) are perfectly
        # comparable -- they either agree or they do not. INCOMPARABLE is reserved for
        # values whose types cannot be meaningfully lined up at all.
        if isinstance(original.value, str) and isinstance(rebuilt_value, str):
            return (
                ComparisonState.MATCH
                if original.value == rebuilt_value
                else ComparisonState.DIFFERENT_VALUE
            )
        if original.value is not None and str(original.value) == str(rebuilt_value):
            return ComparisonState.MATCH
        return ComparisonState.INCOMPARABLE

    if original.unit == rebuilt_unit or original.unit is None or rebuilt_unit is None:
        return (
            ComparisonState.MATCH
            if original_number == rebuilt_number
            else ComparisonState.DIFFERENT_VALUE
        )

    factor = _normalization_factor(original.unit, rebuilt_unit)
    if factor is None:
        return ComparisonState.INCOMPARABLE
    if original_number * factor == rebuilt_number:
        return ComparisonState.MATCH_WITH_NORMALIZATION
    return ComparisonState.DIFFERENT_VALUE


def build_field_comparison(
    field_id: str,
    original: OriginalFieldValue | None,
    *,
    display_name: str | None = None,
    rebuilt_value: object | None = None,
    rebuilt_unit: str | None = None,
    rebuilt_provider: str | None = None,
    rebuilt_available: bool = True,
    available_at_detection: bool | None = None,
    mislabeled: bool = False,
    issues: Sequence[str] = (),
    supporting_artifact_ids: Sequence[str] = (),
    supporting_observation_ids: Sequence[str] = (),
    supporting_metric_ids: Sequence[str] = (),
    **timing: object,
) -> FieldComparisonEntry:
    state = classify_comparison(
        original,
        rebuilt_value,
        rebuilt_unit=rebuilt_unit,
        rebuilt_available=rebuilt_available,
        mislabeled=mislabeled,
    )

    resolved_issues = list(issues)
    if state is ComparisonState.DIFFERENT_SEMANTICS:
        resolved_issues.append(
            f"original unit {original.unit if original else None!r} and rebuilt unit "
            f"{rebuilt_unit!r} measure different quantities; not compared numerically"
        )
    if state is ComparisonState.ORIGINAL_MISLABELED and original is not None:
        resolved_issues.append(
            f"displayed label {original.display_label!r} does not describe the underlying value"
        )

    draft = FieldComparisonEntry(
        field_id=field_id,
        display_name=display_name or (original.display_label if original else None),
        original_value=None if original is None else original.value,
        original_unit=None if original is None else original.unit,
        original_provider=None if original is None else original.provider,
        rebuilt_value=rebuilt_value if rebuilt_available else None,
        rebuilt_unit=rebuilt_unit,
        rebuilt_provider=rebuilt_provider,
        available_at_detection=available_at_detection,
        original_source_time=None if original is None else original.source_timestamp,
        comparison_state=state,
        issues=tuple(resolved_issues),
        supporting_artifact_ids=tuple(supporting_artifact_ids),
        supporting_observation_ids=tuple(supporting_observation_ids),
        supporting_metric_ids=tuple(supporting_metric_ids),
        deterministic_id="",
        **timing,  # type: ignore[arg-type]
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(field_comparison_identity(draft))}
    )


__all__ = ["build_field_comparison", "classify_comparison"]

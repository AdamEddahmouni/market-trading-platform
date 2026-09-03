from __future__ import annotations

from .enums import Classification
from .evidence import EvidenceInput
from .models import MethodologyResult

LEGACY_ID = "legacy_prime_setup"
LEGACY_LABEL = "LEGACY PRIME SETUP — HISTORICAL REFERENCE"
REQUIRED = (
    "price",
    "today_percentage_change",
    "relative_volume",
    "published_short_interest_pct",
)
UNITS = {
    "price": "PRICE",
    "today_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
    "published_short_interest_pct": "PERCENT",
}


def evaluate_legacy(inputs: dict[str, EvidenceInput], *, as_of: str | None = None) -> MethodologyResult:
    conflicts = tuple(key for key in REQUIRED if inputs.get(key) and inputs[key].conflict)
    missing = tuple(
        key for key in REQUIRED
        if key not in inputs or not inputs[key].eligible_for(UNITS[key])
    )
    conditions = {
        "price": None,
        "today_percentage_change": None,
        "relative_volume": None,
        "published_short_interest_pct": None,
    }
    if conflicts:
        classification = Classification.CONFLICTED
    elif missing:
        classification = Classification.UNEVALUABLE
    else:
        conditions = {
            "price": 2 <= float(inputs["price"].value) <= 20,
            "today_percentage_change": float(inputs["today_percentage_change"].value) >= 10,
            "relative_volume": float(inputs["relative_volume"].value) >= 5,
            "published_short_interest_pct": (
                float(inputs["published_short_interest_pct"].value) >= 5
            ),
        }
        classification = (
            Classification.PRIME if all(conditions.values()) else Classification.NOT_QUALIFIED
        )
    known = tuple(
        key for key in REQUIRED
        if key in inputs and inputs[key].eligible_for(UNITS[key])
    )
    return MethodologyResult(
        methodology_id=LEGACY_ID,
        methodology_version="1.0.0",
        methodology_label=LEGACY_LABEL,
        classification=str(classification),
        evaluable=classification in (Classification.PRIME, Classification.NOT_QUALIFIED),
        pressure=None,
        ignition=None,
        evidence_coverage={
            "category": "COMPLETE" if not missing and not conflicts else "INCOMPLETE",
            "available": len(known),
            "required": len(REQUIRED),
        },
        known_inputs=known,
        missing_inputs=missing,
        supporting_evidence=tuple(inputs[key].as_dict() for key in known),
        blocking_reasons=tuple(
            f"{key} is absent, incompatible, stale, or research-inadmissible" for key in missing
        ),
        conflict_reasons=tuple(f"material conflict in {key}" for key in conflicts),
        as_of=as_of,
        metadata={"conditions": conditions, "validated": False},
    )

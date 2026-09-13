"""External paper comparator binding — explicit challenge model, not market truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

COMPARATOR_NOT_MARKET_TRUTH_STATEMENT = (
    "External Paper, sandbox, replay, or vendor simulator output is a comparator "
    "challenge model with its own limitations. It is never market ground truth and "
    "must not silently override IMP simulation results."
)


class ComparatorContractError(ValueError):
    """Invalid external comparator binding."""


@dataclass(frozen=True, slots=True)
class ExternalPaperComparatorBinding:
    comparator_id: str
    environment: str
    account_mode: str
    limitations: tuple[str, ...]
    version_ref: str | None = None
    is_market_truth: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparator_id": self.comparator_id,
            "environment": self.environment,
            "account_mode": self.account_mode,
            "limitations": list(self.limitations),
            "version_ref": self.version_ref,
            "is_market_truth": self.is_market_truth,
            "not_market_truth_statement": COMPARATOR_NOT_MARKET_TRUTH_STATEMENT,
        }


def validate_comparator_binding(payload: Mapping[str, Any]) -> ExternalPaperComparatorBinding:
    comparator_id = str(payload.get("comparator_id") or "").strip()
    environment = str(payload.get("environment") or "").strip()
    account_mode = str(payload.get("account_mode") or "").strip()
    if not comparator_id or not environment or not account_mode:
        raise ComparatorContractError("COMPARATOR_BINDING_INCOMPLETE")
    if bool(payload.get("is_market_truth")):
        raise ComparatorContractError("COMPARATOR_MARKET_TRUTH_FORBIDDEN")
    limitations_raw = payload.get("limitations") or []
    if not isinstance(limitations_raw, list) or not limitations_raw:
        raise ComparatorContractError("COMPARATOR_LIMITATIONS_REQUIRED")
    limitations = tuple(str(item).strip() for item in limitations_raw if str(item).strip())
    if not limitations:
        raise ComparatorContractError("COMPARATOR_LIMITATIONS_REQUIRED")
    return ExternalPaperComparatorBinding(
        comparator_id=comparator_id,
        environment=environment,
        account_mode=account_mode,
        limitations=limitations,
        version_ref=str(payload.get("version_ref") or "") or None,
        is_market_truth=False,
    )


__all__ = [
    "COMPARATOR_NOT_MARKET_TRUTH_STATEMENT",
    "ComparatorContractError",
    "ExternalPaperComparatorBinding",
    "validate_comparator_binding",
]

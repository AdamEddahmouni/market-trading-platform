"""External paper comparator binding — explicit challenge model, not market truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

COMPARATOR_NOT_MARKET_TRUTH_STATEMENT = (
    "External Paper, sandbox, replay, or vendor simulator output is a comparator "
    "challenge model with its own limitations. It is never market ground truth and "
    "must not silently override IMP simulation results."
)

ALPACA_PAPER_HOST = "paper-api.alpaca.markets"

_LIVE_HOSTS = frozenset(
    {
        "api.tradier.com",
        "stream.tradier.com",
        "api.alpaca.markets",
    }
)
_LIVE_ENVIRONMENTS = frozenset({"live", "production", "prod"})
_LIVE_ACCOUNT_MODES = frozenset({"live", "production", "real", "funded"})


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


def _environment_host(environment: str) -> str:
    text = environment.strip()
    if "://" in text:
        return (urlparse(text).hostname or "").lower()
    return ""


def _is_alpaca_comparator(comparator_id: str) -> bool:
    return "alpaca" in comparator_id.strip().lower()


def assert_paper_only_environment(*, environment: str, account_mode: str) -> None:
    """Fail closed on Live/production hosts or ambiguous live account modes."""
    host = _environment_host(environment)
    if host in _LIVE_HOSTS:
        raise ComparatorContractError("COMPARATOR_LIVE_HOST_FORBIDDEN")
    env_key = environment.strip().lower()
    if env_key in _LIVE_ENVIRONMENTS:
        raise ComparatorContractError("COMPARATOR_LIVE_HOST_FORBIDDEN")
    if account_mode.strip().lower() in _LIVE_ACCOUNT_MODES:
        raise ComparatorContractError("COMPARATOR_LIVE_ACCOUNT_FORBIDDEN")


def assert_alpaca_paper_pairing_host(environment: str) -> None:
    """Alpaca pairing is paper-api.alpaca.markets only. Live host is forbidden."""
    text = str(environment or "").strip()
    host = _environment_host(text)
    if host in _LIVE_HOSTS:
        raise ComparatorContractError("COMPARATOR_LIVE_HOST_FORBIDDEN")
    parsed = urlparse(text) if "://" in text else None
    if parsed is None or (parsed.hostname or "").lower() != ALPACA_PAPER_HOST:
        raise ComparatorContractError("COMPARATOR_ALPACA_PAPER_HOST_REQUIRED")
    if parsed.scheme != "https":
        raise ComparatorContractError("COMPARATOR_ALPACA_PAPER_HOST_REQUIRED")


def validate_comparator_binding(payload: Mapping[str, Any]) -> ExternalPaperComparatorBinding:
    comparator_id = str(payload.get("comparator_id") or "").strip()
    environment = str(payload.get("environment") or "").strip()
    account_mode = str(payload.get("account_mode") or "").strip()
    if not comparator_id or not environment or not account_mode:
        raise ComparatorContractError("COMPARATOR_BINDING_INCOMPLETE")
    if bool(payload.get("is_market_truth")):
        raise ComparatorContractError("COMPARATOR_MARKET_TRUTH_FORBIDDEN")
    assert_paper_only_environment(environment=environment, account_mode=account_mode)
    if _is_alpaca_comparator(comparator_id):
        assert_alpaca_paper_pairing_host(environment)
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
    "ALPACA_PAPER_HOST",
    "COMPARATOR_NOT_MARKET_TRUTH_STATEMENT",
    "ComparatorContractError",
    "ExternalPaperComparatorBinding",
    "assert_alpaca_paper_pairing_host",
    "assert_paper_only_environment",
    "validate_comparator_binding",
]

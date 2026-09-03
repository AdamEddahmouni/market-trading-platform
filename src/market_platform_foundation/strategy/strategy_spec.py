"""Strategy specification and identity per Revision 3 Section 11."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

ALIGNMENT_TYPES = ("FORECAST_MOMENTUM", "WHALE_ALIGNED", "WHALE_CONTRARIAN")
SPEC_VERSION = "1.0.0"
TAXONOMY_VERSION = "strategy_taxonomy/1.0.0"


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """Immutable typed identity for a strategy definition.

    Taxonomy fields are optional so definitions produced by the original
    dictionary API retain their existing identity hash and serialized shape.
    """

    alignment_type: str
    hypothesis: str
    evidence_requirements: tuple[str, ...]
    instrument_id: str = "EQ-1"
    spec_version: str = SPEC_VERSION
    family: str | None = None
    style: str | None = None
    asset_class: str | None = None
    timeframe: str | None = None
    taxonomy_version: str | None = None

    def __post_init__(self) -> None:
        if self.alignment_type not in ALIGNMENT_TYPES:
            raise ValueError(f"unsupported alignment type: {self.alignment_type}")
        object.__setattr__(
            self,
            "evidence_requirements",
            tuple(sorted(str(item) for item in self.evidence_requirements)),
        )
        for field_name in ("hypothesis", "instrument_id", "spec_version"):
            value = getattr(self, field_name)
            if not str(value).strip():
                raise ValueError(f"{field_name} is required")
            object.__setattr__(self, field_name, str(value))
        taxonomy_present = False
        for field_name in ("family", "style", "asset_class", "timeframe"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = str(value).strip().upper()
                if not normalized:
                    raise ValueError(f"{field_name} is required when provided")
                object.__setattr__(self, field_name, normalized)
                taxonomy_present = True
        if taxonomy_present:
            object.__setattr__(
                self,
                "taxonomy_version",
                str(self.taxonomy_version or TAXONOMY_VERSION),
            )
        elif self.taxonomy_version is not None:
            raise ValueError("taxonomy_version requires taxonomy fields")

    @classmethod
    def from_legacy_spec(cls, strategy_spec: Mapping[str, Any]) -> "StrategyDefinition":
        return cls(
            alignment_type=str(strategy_spec["alignment_type"]),
            hypothesis=str(strategy_spec["hypothesis"]),
            evidence_requirements=tuple(strategy_spec["evidence_requirements"]),
            instrument_id=str(strategy_spec.get("instrument_id", "EQ-1")),
            spec_version=str(strategy_spec.get("spec_version", SPEC_VERSION)),
            family=str(strategy_spec["family"]) if strategy_spec.get("family") is not None else None,
            style=str(strategy_spec["style"]) if strategy_spec.get("style") is not None else None,
            asset_class=(
                str(strategy_spec["asset_class"])
                if strategy_spec.get("asset_class") is not None
                else None
            ),
            timeframe=str(strategy_spec["timeframe"]) if strategy_spec.get("timeframe") is not None else None,
            taxonomy_version=(
                str(strategy_spec["taxonomy_version"])
                if strategy_spec.get("taxonomy_version") is not None
                else None
            ),
        )

    @property
    def identity_hash(self) -> str:
        return strategy_identity_hash(self.to_legacy_spec())

    def to_legacy_spec(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "alignment_type": self.alignment_type,
            "evidence_requirements": list(self.evidence_requirements),
            "hypothesis": self.hypothesis,
            "instrument_id": self.instrument_id,
            "spec_version": self.spec_version,
        }
        for field_name in ("family", "style", "asset_class", "timeframe", "taxonomy_version"):
            value = getattr(self, field_name)
            if value is not None:
                body[field_name] = value
        return {**body, "strategy_identity_hash": strategy_identity_hash(body)}

    def to_dict(self) -> dict[str, Any]:
        return self.to_legacy_spec()


def build_strategy_spec(
    *,
    alignment_type: str,
    hypothesis: str,
    evidence_requirements: list[str],
    instrument_id: str = "EQ-1",
    family: str | None = None,
    style: str | None = None,
    asset_class: str | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    return build_strategy_definition(
        alignment_type=alignment_type,
        hypothesis=hypothesis,
        evidence_requirements=evidence_requirements,
        instrument_id=instrument_id,
        family=family,
        style=style,
        asset_class=asset_class,
        timeframe=timeframe,
    ).to_legacy_spec()


def build_strategy_definition(
    *,
    alignment_type: str,
    hypothesis: str,
    evidence_requirements: list[str] | tuple[str, ...],
    instrument_id: str = "EQ-1",
    spec_version: str = SPEC_VERSION,
    family: str | None = None,
    style: str | None = None,
    asset_class: str | None = None,
    timeframe: str | None = None,
) -> StrategyDefinition:
    return StrategyDefinition(
        alignment_type=alignment_type,
        hypothesis=hypothesis,
        evidence_requirements=tuple(evidence_requirements),
        instrument_id=instrument_id,
        spec_version=spec_version,
        family=family,
        style=style,
        asset_class=asset_class,
        timeframe=timeframe,
    )


def strategy_spec_from_definition(definition: StrategyDefinition) -> dict[str, Any]:
    return definition.to_legacy_spec()


def strategy_definition_from_spec(
    strategy_spec: Mapping[str, Any],
) -> StrategyDefinition:
    return StrategyDefinition.from_legacy_spec(strategy_spec)


def coerce_strategy_spec(
    strategy_spec: StrategyDefinition | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(strategy_spec, StrategyDefinition):
        return strategy_spec.to_legacy_spec()
    return dict(strategy_spec)


def strategy_identity_hash(
    spec_body: Mapping[str, Any] | StrategyDefinition,
) -> str:
    if isinstance(spec_body, StrategyDefinition):
        spec_body = spec_body.to_legacy_spec()
    without_hash = {k: v for k, v in spec_body.items() if k != "strategy_identity_hash"}
    return sha256_bytes(canonical_bytes(without_hash))

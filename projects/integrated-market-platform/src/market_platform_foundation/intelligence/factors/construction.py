"""Frozen quantitative factor construction specification.

This is the reusable preprocessing/universe/portfolio-rule contract. It does
not compute a factor value and does not claim incremental alpha.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    dataclass_field_names,
    normalize_unique_strings,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
)
from .errors import FactorContractError
from .families import (
    CharacteristicTransform,
    FactorFamily,
    FactorSign,
    InvalidDenominatorRule,
    MissingnessRule,
    MultiplicityPolicy,
    Neutralization,
)
from .identity import CONSTRUCTION_ID_PREFIX, IDENTITY_VERSION, factor_hash
from .promotion import assert_research_only, reject_promotion_fields


def _require_version(value: str, *, field_name: str) -> str:
    text = str(value)
    if not text or text.strip() != text or not text.strip():
        raise FactorContractError(f"{field_name.upper()}_INVALID")
    return text


def construction_identity_payload(
    *,
    schema_version: str,
    feature_id: str,
    feature_version: str,
    hypothesis_family_id: str,
    family: FactorFamily,
    formula: str,
    sign: FactorSign,
    required_source_fields: tuple[str, ...],
    pit_lag_ns: int,
    invalid_denominator_rule: InvalidDenominatorRule,
    missingness_rule: MissingnessRule,
    winsorization: str,
    transform: CharacteristicTransform,
    neutralization: Neutralization,
    universe_version: str,
    breakpoint_version: str,
    portfolio_rule_version: str,
    searched_family_size: int,
    multiplicity_policy: MultiplicityPolicy,
    code_version: str,
) -> dict[str, Any]:
    return {
        "identity_version": IDENTITY_VERSION,
        "schema_version": schema_version,
        "feature_id": feature_id,
        "feature_version": feature_version,
        "hypothesis_family_id": hypothesis_family_id,
        "family": family.value,
        "formula": formula,
        "sign": sign.value,
        "required_source_fields": list(required_source_fields),
        "pit_lag_ns": pit_lag_ns,
        "invalid_denominator_rule": invalid_denominator_rule.value,
        "missingness_rule": missingness_rule.value,
        "winsorization": winsorization,
        "transform": transform.value,
        "neutralization": neutralization.value,
        "universe_version": universe_version,
        "breakpoint_version": breakpoint_version,
        "portfolio_rule_version": portfolio_rule_version,
        "searched_family_size": searched_family_size,
        "multiplicity_policy": multiplicity_policy.value,
        "code_version": code_version,
        "current_universe_backfill_forbidden": True,
    }


def derive_construction_spec_id_from_payload(payload: dict[str, Any]) -> str:
    return factor_hash(payload, prefix=CONSTRUCTION_ID_PREFIX)


@dataclass(frozen=True, slots=True)
class FactorConstructionSpecV1:
    """Frozen construction rules for one characteristic/factor expression.

    Changing any construction field after seeing results is a new experiment.
    """

    spec_id: str
    schema_version: str
    feature_id: str
    feature_version: str
    hypothesis_family_id: str
    family: FactorFamily
    formula: str
    sign: FactorSign
    required_source_fields: tuple[str, ...]
    pit_lag_ns: int
    invalid_denominator_rule: InvalidDenominatorRule
    missingness_rule: MissingnessRule
    winsorization: str
    transform: CharacteristicTransform
    neutralization: Neutralization
    universe_version: str
    breakpoint_version: str
    portfolio_rule_version: str
    searched_family_size: int
    multiplicity_policy: MultiplicityPolicy
    code_version: str
    current_universe_backfill_forbidden: bool = True

    def __post_init__(self) -> None:
        validate_id(self.spec_id, field_name="spec_id")
        validate_schema_version(self.schema_version)
        validate_id(self.feature_id, field_name="feature_id")
        _require_version(self.feature_version, field_name="feature_version")
        validate_id(self.hypothesis_family_id, field_name="hypothesis_family_id")
        if not isinstance(self.family, FactorFamily):
            object.__setattr__(self, "family", FactorFamily(str(self.family)))
        if not self.formula or not str(self.formula).strip():
            raise FactorContractError("FACTOR_FORMULA_REQUIRED")
        if not isinstance(self.sign, FactorSign):
            object.__setattr__(self, "sign", FactorSign(str(self.sign)))
        object.__setattr__(
            self, "required_source_fields", normalize_unique_strings(self.required_source_fields)
        )
        if not self.required_source_fields:
            raise FactorContractError("FACTOR_SOURCE_FIELDS_REQUIRED")
        if not isinstance(self.pit_lag_ns, int) or self.pit_lag_ns < 0:
            raise FactorContractError("FACTOR_PIT_LAG_INVALID")
        if not isinstance(self.invalid_denominator_rule, InvalidDenominatorRule):
            object.__setattr__(
                self,
                "invalid_denominator_rule",
                InvalidDenominatorRule(str(self.invalid_denominator_rule)),
            )
        if not isinstance(self.missingness_rule, MissingnessRule):
            object.__setattr__(self, "missingness_rule", MissingnessRule(str(self.missingness_rule)))
        _require_version(self.winsorization, field_name="winsorization")
        if not isinstance(self.transform, CharacteristicTransform):
            object.__setattr__(self, "transform", CharacteristicTransform(str(self.transform)))
        if not isinstance(self.neutralization, Neutralization):
            object.__setattr__(self, "neutralization", Neutralization(str(self.neutralization)))
        _require_version(self.universe_version, field_name="universe_version")
        _require_version(self.breakpoint_version, field_name="breakpoint_version")
        _require_version(self.portfolio_rule_version, field_name="portfolio_rule_version")
        if not isinstance(self.searched_family_size, int) or self.searched_family_size < 1:
            raise FactorContractError("FACTOR_SEARCHED_FAMILY_SIZE_INVALID")
        if not isinstance(self.multiplicity_policy, MultiplicityPolicy):
            object.__setattr__(
                self, "multiplicity_policy", MultiplicityPolicy(str(self.multiplicity_policy))
            )
        _require_version(self.code_version, field_name="code_version")
        if self.current_universe_backfill_forbidden is not True:
            raise FactorContractError("FACTOR_CURRENT_UNIVERSE_BACKFILL_FORBIDDEN")
        expected = derive_construction_spec_id_from_payload(
            construction_identity_payload(
                schema_version=self.schema_version,
                feature_id=self.feature_id,
                feature_version=self.feature_version,
                hypothesis_family_id=self.hypothesis_family_id,
                family=self.family,
                formula=self.formula,
                sign=self.sign,
                required_source_fields=self.required_source_fields,
                pit_lag_ns=self.pit_lag_ns,
                invalid_denominator_rule=self.invalid_denominator_rule,
                missingness_rule=self.missingness_rule,
                winsorization=self.winsorization,
                transform=self.transform,
                neutralization=self.neutralization,
                universe_version=self.universe_version,
                breakpoint_version=self.breakpoint_version,
                portfolio_rule_version=self.portfolio_rule_version,
                searched_family_size=self.searched_family_size,
                multiplicity_policy=self.multiplicity_policy,
                code_version=self.code_version,
            )
        )
        if self.spec_id != expected:
            raise FactorContractError("FACTOR_CONSTRUCTION_IDENTITY_MISMATCH")
        assert_research_only()


def build_construction_spec(
    *,
    feature_id: str,
    feature_version: str,
    hypothesis_family_id: str,
    family: FactorFamily,
    formula: str,
    sign: FactorSign,
    required_source_fields: tuple[str, ...],
    pit_lag_ns: int,
    invalid_denominator_rule: InvalidDenominatorRule,
    missingness_rule: MissingnessRule,
    winsorization: str,
    transform: CharacteristicTransform,
    neutralization: Neutralization,
    universe_version: str,
    breakpoint_version: str,
    portfolio_rule_version: str,
    searched_family_size: int,
    multiplicity_policy: MultiplicityPolicy,
    code_version: str,
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
) -> FactorConstructionSpecV1:
    fields = tuple(normalize_unique_strings(required_source_fields))
    payload = construction_identity_payload(
        schema_version=schema_version,
        feature_id=feature_id,
        feature_version=feature_version,
        hypothesis_family_id=hypothesis_family_id,
        family=family,
        formula=formula,
        sign=sign,
        required_source_fields=fields,
        pit_lag_ns=pit_lag_ns,
        invalid_denominator_rule=invalid_denominator_rule,
        missingness_rule=missingness_rule,
        winsorization=winsorization,
        transform=transform,
        neutralization=neutralization,
        universe_version=universe_version,
        breakpoint_version=breakpoint_version,
        portfolio_rule_version=portfolio_rule_version,
        searched_family_size=searched_family_size,
        multiplicity_policy=multiplicity_policy,
        code_version=code_version,
    )
    return FactorConstructionSpecV1(
        spec_id=derive_construction_spec_id_from_payload(payload),
        schema_version=schema_version,
        feature_id=feature_id,
        feature_version=feature_version,
        hypothesis_family_id=hypothesis_family_id,
        family=family,
        formula=formula,
        sign=sign,
        required_source_fields=fields,
        pit_lag_ns=pit_lag_ns,
        invalid_denominator_rule=invalid_denominator_rule,
        missingness_rule=missingness_rule,
        winsorization=winsorization,
        transform=transform,
        neutralization=neutralization,
        universe_version=universe_version,
        breakpoint_version=breakpoint_version,
        portfolio_rule_version=portfolio_rule_version,
        searched_family_size=searched_family_size,
        multiplicity_policy=multiplicity_policy,
        code_version=code_version,
        current_universe_backfill_forbidden=True,
    )


_SPEC_ALLOWED = dataclass_field_names(FactorConstructionSpecV1)


def construction_spec_to_dict(spec: FactorConstructionSpecV1) -> dict[str, Any]:
    return {
        "spec_id": spec.spec_id,
        "schema_version": spec.schema_version,
        "feature_id": spec.feature_id,
        "feature_version": spec.feature_version,
        "hypothesis_family_id": spec.hypothesis_family_id,
        "family": spec.family.value,
        "formula": spec.formula,
        "sign": spec.sign.value,
        "required_source_fields": list(spec.required_source_fields),
        "pit_lag_ns": spec.pit_lag_ns,
        "invalid_denominator_rule": spec.invalid_denominator_rule.value,
        "missingness_rule": spec.missingness_rule.value,
        "winsorization": spec.winsorization,
        "transform": spec.transform.value,
        "neutralization": spec.neutralization.value,
        "universe_version": spec.universe_version,
        "breakpoint_version": spec.breakpoint_version,
        "portfolio_rule_version": spec.portfolio_rule_version,
        "searched_family_size": spec.searched_family_size,
        "multiplicity_policy": spec.multiplicity_policy.value,
        "code_version": spec.code_version,
        "current_universe_backfill_forbidden": True,
    }


def construction_spec_from_dict(payload: dict[str, Any]) -> FactorConstructionSpecV1:
    reject_unknown_keys(payload, _SPEC_ALLOWED)
    reject_promotion_fields(dict(payload.get("metadata") or {}))
    return FactorConstructionSpecV1(
        spec_id=str(payload["spec_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        feature_id=str(payload["feature_id"]),
        feature_version=str(payload["feature_version"]),
        hypothesis_family_id=str(payload["hypothesis_family_id"]),
        family=FactorFamily(str(payload["family"])),
        formula=str(payload["formula"]),
        sign=FactorSign(str(payload["sign"])),
        required_source_fields=tuple(payload.get("required_source_fields") or ()),
        pit_lag_ns=int(payload["pit_lag_ns"]),
        invalid_denominator_rule=InvalidDenominatorRule(str(payload["invalid_denominator_rule"])),
        missingness_rule=MissingnessRule(str(payload["missingness_rule"])),
        winsorization=str(payload["winsorization"]),
        transform=CharacteristicTransform(str(payload["transform"])),
        neutralization=Neutralization(str(payload["neutralization"])),
        universe_version=str(payload["universe_version"]),
        breakpoint_version=str(payload["breakpoint_version"]),
        portfolio_rule_version=str(payload["portfolio_rule_version"]),
        searched_family_size=int(payload["searched_family_size"]),
        multiplicity_policy=MultiplicityPolicy(str(payload["multiplicity_policy"])),
        code_version=str(payload["code_version"]),
        current_universe_backfill_forbidden=bool(
            payload.get("current_universe_backfill_forbidden", True)
        ),
    )


__all__ = [
    "FactorConstructionSpecV1",
    "build_construction_spec",
    "construction_identity_payload",
    "construction_spec_from_dict",
    "construction_spec_to_dict",
    "derive_construction_spec_id_from_payload",
]

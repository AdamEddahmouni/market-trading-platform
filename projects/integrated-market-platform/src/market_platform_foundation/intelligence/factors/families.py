"""Ontology for quantitative factor families.

These labels are taxonomy only. They do not implement a strategy, claim
alpha, or admit a factor into Opportunity Engine ranking.
"""

from __future__ import annotations

from enum import StrEnum


class FactorFamily(StrEnum):
    """Canonical factor-family taxonomy from the Quant research primer."""

    PRIOR_RETURN = "PRIOR_RETURN"
    VALUE = "VALUE"
    PROFITABILITY_QUALITY = "PROFITABILITY_QUALITY"
    INVESTMENT = "INVESTMENT"
    DEFENSIVE = "DEFENSIVE"
    CARRY = "CARRY"
    SEASONALITY = "SEASONALITY"
    INTERACTION = "INTERACTION"
    ML_CHALLENGER = "ML_CHALLENGER"


class FactorSign(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class InvalidDenominatorRule(StrEnum):
    REJECT = "REJECT"
    SET_MISSING = "SET_MISSING"
    ABS = "ABS"


class MissingnessRule(StrEnum):
    """Missing values are never silently filled with fabricated numbers."""

    REJECT = "REJECT"
    PROPAGATE = "PROPAGATE"


class CharacteristicTransform(StrEnum):
    RAW = "RAW"
    RANK = "RANK"
    PERCENTILE = "PERCENTILE"
    ZSCORE = "ZSCORE"


class Neutralization(StrEnum):
    NONE = "NONE"
    INDUSTRY = "INDUSTRY"
    SECTOR = "SECTOR"
    COUNTRY = "COUNTRY"
    BETA = "BETA"


class MultiplicityPolicy(StrEnum):
    """Primary inference policy. Raw p-values remain diagnostics only."""

    DECLARED_FDR = "DECLARED_FDR"
    DECLARED_FWER = "DECLARED_FWER"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"


class FactorExpressionClass(StrEnum):
    """How a row may be interpreted. Academic L/S is never operator P&L."""

    CHARACTERISTIC = "CHARACTERISTIC"
    RESEARCH_PORTFOLIO = "RESEARCH_PORTFOLIO"


class FactorEvidenceClass(StrEnum):
    """Software/research evidence class. Not prospective market evidence."""

    RESEARCH_CHARACTERISTIC = "RESEARCH_CHARACTERISTIC"
    SOFTWARE_FIXTURE_ONLY = "SOFTWARE_FIXTURE_ONLY"


__all__ = [
    "CharacteristicTransform",
    "FactorEvidenceClass",
    "FactorExpressionClass",
    "FactorFamily",
    "FactorSign",
    "InvalidDenominatorRule",
    "MissingnessRule",
    "MultiplicityPolicy",
    "Neutralization",
]

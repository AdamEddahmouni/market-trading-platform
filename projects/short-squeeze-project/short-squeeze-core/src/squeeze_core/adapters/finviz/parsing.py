import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.contracts import EarningsSession

from .semantics import PercentageUnit


_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_QUANTITY = re.compile(r"^(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+))(?P<suffix>[KMBTkmbt]?)$")
_MULTIPLIERS = {
    "K": Decimal("1000"),
    "M": Decimal("1000000"),
    "B": Decimal("1000000000"),
    "T": Decimal("1000000000000"),
}


class FinvizParseError(ValueError):
    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedQuantity:
    value: int | None
    approximate: bool = False


@dataclass(frozen=True, slots=True)
class ParsedEarnings:
    earnings_date: date | None
    session: EarningsSession | None


def _decimal(value: Any, code: DiagnosticCode, label: str) -> Decimal:
    if isinstance(value, bool):
        raise FinvizParseError(code, f"{label} must be numeric")
    text = str(value).strip()
    if not _DECIMAL.fullmatch(text):
        raise FinvizParseError(code, f"{label} uses an unsupported numeric format")
    try:
        converted = Decimal(text)
    except InvalidOperation as error:
        raise FinvizParseError(code, f"{label} must be numeric") from error
    if not converted.is_finite():
        raise FinvizParseError(code, f"{label} must be finite")
    return converted


def parse_price(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    converted = _decimal(value, DiagnosticCode.FINVIZ_INVALID_PRICE, "price")
    if converted < 0:
        raise FinvizParseError(DiagnosticCode.FINVIZ_INVALID_PRICE, "price must not be negative")
    return converted


def parse_percentage(
    value: Any,
    unit: PercentageUnit | str | None,
    *,
    allow_negative: bool = False,
) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed_unit = PercentageUnit(unit)
    except (ValueError, TypeError) as error:
        raise FinvizParseError(
            DiagnosticCode.FINVIZ_UNSUPPORTED_PERCENT_UNIT,
            "percentage unit is unsupported or absent",
        ) from error
    text = str(value).strip()
    if parsed_unit is PercentageUnit.FORMATTED_PERCENT_STRING:
        if not text.endswith("%"):
            raise FinvizParseError(
                DiagnosticCode.FINVIZ_UNSUPPORTED_PERCENT_UNIT,
                "formatted percentage must end with percent sign",
            )
        text = text[:-1].strip()
    elif text.endswith("%"):
        raise FinvizParseError(
            DiagnosticCode.FINVIZ_UNSUPPORTED_PERCENT_UNIT,
            "percent sign requires FORMATTED_PERCENT_STRING",
        )
    converted = _decimal(text, DiagnosticCode.INVALID_NUMERIC_VALUE, "percentage")
    if parsed_unit is PercentageUnit.DECIMAL_FRACTION:
        converted *= Decimal("100")
    if converted < 0 and not allow_negative:
        raise FinvizParseError(DiagnosticCode.INVALID_NUMERIC_VALUE, "percentage must not be negative")
    return converted


def parse_quantity(value: Any) -> ParsedQuantity:
    if value is None or value == "":
        return ParsedQuantity(None)
    if isinstance(value, bool):
        raise FinvizParseError(
            DiagnosticCode.FINVIZ_INVALID_QUANTITY_SUFFIX, "quantity must be numeric"
        )
    match = _QUANTITY.fullmatch(str(value).strip())
    if match is None:
        raise FinvizParseError(
            DiagnosticCode.FINVIZ_INVALID_QUANTITY_SUFFIX,
            "quantity format or suffix is unsupported",
        )
    converted = Decimal(match.group("number"))
    suffix = match.group("suffix").upper()
    if converted < 0:
        raise FinvizParseError(
            DiagnosticCode.INVALID_NUMERIC_VALUE, "quantity must not be negative"
        )
    approximate = bool(suffix)
    if suffix:
        converted *= _MULTIPLIERS[suffix]
    if converted != converted.to_integral_value():
        raise FinvizParseError(
            DiagnosticCode.INVALID_NUMERIC_VALUE, "quantity must resolve to a whole number"
        )
    return ParsedQuantity(int(converted), approximate)


def parse_ratio(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    converted = _decimal(value, DiagnosticCode.INVALID_NUMERIC_VALUE, "ratio")
    if converted < 0:
        raise FinvizParseError(DiagnosticCode.INVALID_NUMERIC_VALUE, "ratio must not be negative")
    return converted


def parse_earnings(value: Any) -> ParsedEarnings:
    if value is None or str(value).strip() in {"", "-", "N/A", "Unknown"}:
        return ParsedEarnings(None, None)
    text = str(value).strip()
    parts = text.split()
    try:
        parsed_date = date.fromisoformat(parts[0])
    except ValueError as error:
        raise FinvizParseError(
            DiagnosticCode.FINVIZ_AMBIGUOUS_EARNINGS_VALUE,
            "earnings value does not contain an exact ISO date",
        ) from error
    if len(parts) == 1:
        return ParsedEarnings(parsed_date, EarningsSession.UNKNOWN)
    if len(parts) == 2 and parts[1].upper() in {"BMO", "AMC"}:
        session = (
            EarningsSession.BEFORE_MARKET
            if parts[1].upper() == "BMO"
            else EarningsSession.AFTER_MARKET
        )
        return ParsedEarnings(parsed_date, session)
    raise FinvizParseError(
        DiagnosticCode.FINVIZ_AMBIGUOUS_EARNINGS_VALUE,
        "earnings qualifier is unsupported or ambiguous",
    )

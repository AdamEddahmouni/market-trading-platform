"""Exact integer numeric helpers for prices, quantities, and money."""

from __future__ import annotations


def _decimal_places(minor_unit_scale: int) -> int:
    if minor_unit_scale <= 1:
        raise ValueError("minor unit scale must be greater than 1")
    value = minor_unit_scale
    places = 0
    while value > 1:
        if value % 10 != 0:
            raise ValueError("minor unit scale must be a power of 10")
        value //= 10
        places += 1
    return places


def decimal_to_minor_units(value: str, *, scale: int = 100) -> int:
    text = str(value).strip()
    if not text:
        raise ValueError("empty decimal value")
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    decimal_places = _decimal_places(scale)
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = (frac + "0" * decimal_places)[:decimal_places]
    else:
        whole, frac = text, "0" * decimal_places
    if not whole.isdigit() or not frac.isdigit():
        raise ValueError(f"invalid decimal value: {value}")
    result = int(whole) * scale + int(frac)
    return -result if negative else result


def minor_units_to_decimal(value: int, *, scale: int = 100) -> str:
    decimal_places = _decimal_places(scale)
    negative = value < 0
    amount = abs(value)
    whole = amount // scale
    frac = amount % scale
    text = f"{whole}.{frac:0{decimal_places}d}"
    return f"-{text}" if negative else text


def apply_participation_cap(volume: int, *, numerator: int, denominator: int) -> int:
    if volume <= 0 or numerator <= 0 or denominator <= 0:
        return 0
    return (volume * numerator) // denominator

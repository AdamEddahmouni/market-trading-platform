"""Security identifier checks (CUSIP, ISIN) — deterministic, no network.

An ISIN (ISO 6166) is a two-letter country code, a nine-character national
number (for U.S. and Canadian securities, the CUSIP), and a check digit:
letters become two digits (A=10 … Z=35) and the Luhn algorithm runs over the
resulting digit string. Deriving an ISIN from a CUSIP needs the country code,
so it is done only when the issuer country is known to be ``US``; a derived
ISIN is labeled DERIVED, never presented as provider-reported.
"""

from __future__ import annotations

from .treasury_catalog import cusip_valid

__all__ = ["cusip_valid", "isin_check_digit", "isin_from_cusip", "isin_valid"]


def _expand(body: str) -> str:
    return "".join(str(int(char, 36)) for char in body)


def isin_check_digit(body: str) -> int:
    """Check digit for an 11-character ISIN body (country code + national number)."""

    text = body.strip().upper()
    if len(text) != 11 or not text[:2].isalpha() or not text.isalnum():
        raise ValueError("INVALID_ISIN_BODY")
    digits = [int(char) for char in _expand(text)]
    total = 0
    # Luhn: double every second digit counting from the rightmost digit of the body.
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 0:
            digit *= 2
            digit = digit - 9 if digit > 9 else digit
        total += digit
    return (10 - total % 10) % 10


def isin_valid(value: str | None) -> bool:
    text = (value or "").strip().upper()
    if len(text) != 12 or not text[11].isdigit():
        return False
    try:
        return isin_check_digit(text[:11]) == int(text[11])
    except ValueError:
        return False


def isin_from_cusip(cusip: str, country: str = "US") -> str | None:
    """The ISIN for a valid CUSIP in ``country``; None when the CUSIP fails its check digit."""

    code = cusip.strip().upper()
    # CUSIPs may use *, @, # (private placements); an ISIN body is alphanumeric only.
    if not cusip_valid(code) or not code.isalnum() or len(country) != 2 or not country.isalpha():
        return None
    body = country.upper() + code
    return body + str(isin_check_digit(body))

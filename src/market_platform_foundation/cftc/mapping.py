"""CFTC market → canonical futures contract-family mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Priority markets — deterministic seed mapping; ProductHierarchy extends at runtime.
SEED_MARKET_MAPPINGS: dict[str, str] = {
  # TFF equity indices
  "13874+": "ES",  # E-MINI S&P 500
  "209742": "NQ",  # E-MINI NASDAQ-100
  "12460+": "YM",  # E-MINI DOW
  "239742": "RTY",  # E-MINI RUSSELL 2000
  # Rates
  "020601": "ZN",  # 10-Year T-Note
  "043602": "ZB",  # 30-Year T-Bond
  "042601": "ZF",  # 5-Year T-Note
  "044601": "ZT",  # 2-Year T-Note
  "045601": "UB",  # Ultra T-Bond
  # FX
  "099741": "6E",  # Euro FX
  "097741": "6J",  # Japanese Yen
  "096742": "6B",  # British Pound
  # Energy / metals (Disaggregated)
  "067651": "CL",  # WTI Crude Oil
  "023651": "NG",  # Henry Hub Natural Gas
  "088691": "GC",  # Gold
  "084691": "SI",  # Silver
  # Agriculture
  "002602": "ZC",  # Corn
  "005602": "ZS",  # Soybeans
  "001602": "ZW",  # Wheat
}

# Name-based fallback patterns (uppercase substring match)
NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("E-MINI S&P 500", "ES"),
    ("E-MINI NASDAQ-100", "NQ"),
    ("E-MINI DOW", "YM"),
    ("E-MINI RUSSELL", "RTY"),
    ("10-YEAR", "ZN"),
    ("30-YEAR", "ZB"),
    ("5-YEAR", "ZF"),
    ("2-YEAR", "ZT"),
    ("EURO FX", "6E"),
    ("JAPANESE YEN", "6J"),
    ("BRITISH POUND", "6B"),
    ("CRUDE OIL", "CL"),
    ("NATURAL GAS", "NG"),
    ("GOLD", "GC"),
    ("SILVER", "SI"),
    ("CORN", "ZC"),
    ("SOYBEAN", "ZS"),
    ("WHEAT", "ZW"),
)


@dataclass(frozen=True, slots=True)
class ProductMapping:
    cftc_contract_market_code: str
    contract_family_id: str
    market_and_exchange_names: str
    report_family_hint: str = ""
    resolved: bool = True


class CotProductMapper:
    """Maps CFTC contract market codes to platform futures families."""

    def __init__(self, *, extra_mappings: dict[str, str] | None = None) -> None:
        self._by_code: dict[str, str] = dict(SEED_MARKET_MAPPINGS)
        if extra_mappings:
            self._by_code.update(extra_mappings)

    def load_from_hierarchy_rows(self, rows: list[dict[str, Any]]) -> int:
        added = 0
        for row in rows:
            code = str(row.get("cftc_contract_market_code", "") or row.get("contract_market_code", "")).strip()
            family = str(row.get("canonical_symbol", "") or row.get("instrument_family", "")).strip().upper()
            if code and family and code not in self._by_code:
                self._by_code[code] = family
                added += 1
        return added

    def resolve(
        self,
        *,
        cftc_contract_market_code: str,
        market_and_exchange_names: str = "",
    ) -> ProductMapping:
        code = (cftc_contract_market_code or "").strip()
        if code in self._by_code:
            return ProductMapping(
                cftc_contract_market_code=code,
                contract_family_id=self._by_code[code],
                market_and_exchange_names=market_and_exchange_names,
                resolved=True,
            )
        upper_name = (market_and_exchange_names or "").upper()
        for pattern, family in NAME_PATTERNS:
            if pattern in upper_name:
                return ProductMapping(
                    cftc_contract_market_code=code,
                    contract_family_id=family,
                    market_and_exchange_names=market_and_exchange_names,
                    resolved=True,
                )
        return ProductMapping(
            cftc_contract_market_code=code,
            contract_family_id="",
            market_and_exchange_names=market_and_exchange_names,
            resolved=False,
        )

    def mapping_health(self) -> dict[str, Any]:
        return {
            "seed_mappings": len(SEED_MARKET_MAPPINGS),
            "total_mappings": len(self._by_code),
            "priority_families": sorted(set(SEED_MARKET_MAPPINGS.values())),
        }


def load_mapper_from_fixture(path: Path) -> CotProductMapper:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    mapper = CotProductMapper()
    rows = payload.get("hierarchy_rows", [])
    if isinstance(rows, list):
        mapper.load_from_hierarchy_rows(rows)
    return mapper


__all__ = [
    "CotProductMapper",
    "NAME_PATTERNS",
    "ProductMapping",
    "SEED_MARKET_MAPPINGS",
    "load_mapper_from_fixture",
]

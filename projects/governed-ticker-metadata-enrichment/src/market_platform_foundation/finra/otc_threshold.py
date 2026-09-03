"""Normalize FINRA OTC thresholdList rows. Reg SHO and Rule 4320 remain distinct."""

from __future__ import annotations

from typing import Any

from ..canonical import sha256_bytes
from ..short_intelligence.clocks import clocks_threshold, to_utc_iso
from ..short_intelligence.contracts import ObservationFamily, ThresholdStatusObservation
from ..short_intelligence.identity import SymbolMap

PARSER_VERSION = "finra.otc_threshold/1.0.0"
SOURCE_SRO = "FINRA_OTC"
LISTING_COVERAGE = "OTC"
DATASET = "thresholdList"


def normalize_otc_threshold_row(
    row: dict[str, Any],
    *,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    finra_request_id: str = "",
    record_version: int = 1,
    provider_publication_time: str = "",
) -> ThresholdStatusObservation:
    symbol = str(row.get("issueSymbolIdentifier") or "").strip().upper()
    trade_date = str(row.get("tradeDate") or "")[:10]
    reg_flag = str(row.get("regShoThresholdFlag") or "").strip().upper() or None
    rule_4320 = str(row.get("rule4320Flag") or "").strip().upper() or None
    list_flag = str(row.get("thresholdListFlag") or "").strip().upper() or None
    currently = reg_flag == "Y" or rule_4320 == "Y" or list_flag in {"R", "NR", "Y"}
    resolved = symbol_map.resolve(symbol, as_of=trade_date)
    available = to_utc_iso(provider_publication_time or observed_time or retrieved_time)
    clocks = clocks_threshold(
        trade_date=trade_date,
        file_creation_time=available,
        observed_time=observed_time,
        retrieved_time=retrieved_time,
    )
    clocks = dict(clocks)
    clocks["first_observed_time"] = to_utc_iso(observed_time)
    if provider_publication_time:
        clocks["provider_publication_time"] = to_utc_iso(provider_publication_time)
    payload = dict(row)
    payload["finra_request_id"] = finra_request_id
    content_hash = sha256_bytes(repr(sorted(payload.items())).encode("utf-8"))
    quality: list[str] = ["FTD_QUANTITY_UNKNOWN", "FINRA_OTC_COVERAGE_ONLY"]
    if "IDENTITY_UNRESOLVED" in resolved.quality_flags:
        quality.append("IDENTITY_UNRESOLVED")
    if reg_flag == "Y" and rule_4320 == "Y":
        quality.append("DUAL_RULE_FLAGS_PRESENT")
    if not provider_publication_time:
        quality.append("FINRA_PUBLICATION_TIME_UNKNOWN")
    return ThresholdStatusObservation(
        observation_family=ObservationFamily.THRESHOLD_STATUS,
        instrument_id=resolved.instrument_id,
        provider_symbol=symbol,
        trade_date=trade_date,
        currently_threshold=currently,
        source_sro=SOURCE_SRO,
        listing_coverage=LISTING_COVERAGE,
        market_category=str(row.get("marketCategoryDescription") or row.get("marketClassCode") or "OTC"),
        security_name=str(row.get("issueName") or ""),
        rule_3210_flag=None,
        reg_sho_threshold_flag=reg_flag,
        rule_4320_flag=rule_4320,
        threshold_list_flag=list_flag,
        file_creation_time=available,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        clocks=clocks,
        quality_flags=tuple(dict.fromkeys(quality)),
        source_market=str(row.get("marketClassCode") or "OTC"),
        source_file_or_request_id=finra_request_id or DATASET,
        record_version=record_version,
    )


def normalize_otc_threshold_rows(
    rows: list[dict[str, Any]],
    *,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    finra_request_id: str = "",
    requested_symbols: tuple[str, ...] | None = None,
) -> tuple[ThresholdStatusObservation, ...]:
    wanted = {item.upper() for item in requested_symbols} if requested_symbols else None
    observations = [
        normalize_otc_threshold_row(
            row,
            symbol_map=symbol_map,
            observed_time=observed_time,
            retrieved_time=retrieved_time,
            finra_request_id=finra_request_id,
        )
        for row in rows
        if isinstance(row, dict)
    ]
    if wanted is None:
        return tuple(observations)
    present = {row.provider_symbol for row in observations}
    trade_date = observations[0].trade_date if observations else ""
    if not trade_date and rows:
        trade_date = str(rows[0].get("tradeDate") or "")[:10]
    extras: list[ThresholdStatusObservation] = []
    for symbol in sorted(wanted - present):
        resolved = symbol_map.resolve(symbol, as_of=trade_date)
        clocks = clocks_threshold(
            trade_date=trade_date,
            file_creation_time=observed_time,
            observed_time=observed_time,
            retrieved_time=retrieved_time,
        )
        extras.append(
            ThresholdStatusObservation(
                observation_family=ObservationFamily.THRESHOLD_STATUS,
                instrument_id=resolved.instrument_id,
                provider_symbol=symbol,
                trade_date=trade_date,
                currently_threshold=False,
                source_sro=SOURCE_SRO,
                listing_coverage=LISTING_COVERAGE,
                market_category="OTC",
                security_name="",
                rule_3210_flag=None,
                reg_sho_threshold_flag="N",
                rule_4320_flag="N",
                threshold_list_flag="N",
                file_creation_time=clocks["available_time"],
                content_hash=sha256_bytes(f"absent:{trade_date}:{symbol}".encode()),
                parser_version=PARSER_VERSION,
                clocks=dict(clocks),
                quality_flags=tuple(
                    dict.fromkeys(
                        [
                            "FTD_QUANTITY_UNKNOWN",
                            "FINRA_OTC_COVERAGE_ONLY",
                            "SOURCE_COVERAGE_CONFIRMED_ABSENT",
                            *list(resolved.quality_flags),
                        ]
                    )
                ),
                source_market="OTC",
                source_file_or_request_id=finra_request_id or DATASET,
            )
        )
    return tuple(sorted([*observations, *extras], key=lambda row: row.provider_symbol))

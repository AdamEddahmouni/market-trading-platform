"""Bounded read-only recorder: live observation -> JSONL capture.

Uses OpenQuoteContext only. Duration and record count are hard-capped.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.capture import ProviderEnvelope, append_envelope
from market_platform_foundation.market_data.normalization import canonical_symbol
from market_platform_foundation.market_data.quality import assess_book, assess_quote, assess_ticker

from probe import FORBIDDEN_TRADE_NAMES, confirm_localhost, jsonable, redact

MAX_SECONDS = 20
MAX_RECORDS = 80


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded read-only Moomoo recorder")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--codes", default="US.AAPL")
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--output", default=str(ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"))
    args = parser.parse_args()
    confirm_localhost(args.host, args.port)
    seconds = min(args.seconds, MAX_SECONDS)
    import moomoo as ft

    for name in FORBIDDEN_TRADE_NAMES:
        if name == "unlock_trade":
            continue
    codes = [item.strip() for item in args.codes.split(",") if item.strip()][:3]
    output = Path(args.output)
    if output.exists():
        output.unlink()

    quote_ctx = ft.OpenQuoteContext(host=args.host, port=args.port)
    written = 0
    try:
        quote_ctx.subscribe(
            codes,
            [ft.SubType.QUOTE, ft.SubType.TICKER, ft.SubType.ORDER_BOOK],
            session=ft.Session.ALL,
        )
        deadline = time.time() + seconds
        while time.time() < deadline and written < MAX_RECORDS:
            for code in codes:
                ingested = time.time_ns()
                mapping = canonical_symbol(code)
                ret_q, quote = quote_ctx.get_stock_quote([code])
                if ret_q == ft.RET_OK:
                    rows = jsonable(quote)
                    if isinstance(rows, list) and rows:
                        payload = redact(rows[0])
                        received = time.time_ns()
                        flags = assess_quote(payload)
                        append_envelope(
                            output,
                            ProviderEnvelope(
                                provider="moomoo",
                                instrument_id=mapping.instrument_id,
                                capability="US_EQUITY_L1",
                                provider_symbol=code,
                                sequence=written,
                                clocks={
                                    "available_time_ns": received,
                                    "event_time_ns": received,
                                    "ingested_time_ns": ingested,
                                    "provider_time_ns": received,
                                    "received_time_ns": received,
                                },
                                raw_payload=payload,
                                quality_flags=flags,
                            ),
                            max_records=MAX_RECORDS,
                        )
                        written += 1
                ret_t, ticks = quote_ctx.get_rt_ticker(code, num=3)
                if ret_t == ft.RET_OK:
                    rows = jsonable(ticks)
                    if isinstance(rows, list):
                        for row in rows[-2:]:
                            payload = redact(row)
                            received = time.time_ns()
                            flags = assess_ticker(payload)
                            append_envelope(
                                output,
                                ProviderEnvelope(
                                    provider="moomoo",
                                    instrument_id=mapping.instrument_id,
                                    capability="US_EQUITY_TICKS",
                                    provider_symbol=code,
                                    sequence=payload.get("sequence"),
                                    clocks={
                                        "available_time_ns": received,
                                        "event_time_ns": received,
                                        "ingested_time_ns": ingested,
                                        "provider_time_ns": received,
                                        "received_time_ns": received,
                                    },
                                    raw_payload=payload,
                                    quality_flags=flags,
                                ),
                                max_records=MAX_RECORDS,
                            )
                            written += 1
                ret_b, book = quote_ctx.get_order_book(code, num=10)
                if ret_b == ft.RET_OK and isinstance(book, dict):
                    payload = redact(jsonable(book))
                    received = time.time_ns()
                    flags = assess_book(payload)
                    append_envelope(
                        output,
                        ProviderEnvelope(
                            provider="moomoo",
                            instrument_id=mapping.instrument_id,
                            capability="US_EQUITY_DEPTH",
                            provider_symbol=code,
                            sequence=written,
                            clocks={
                                "available_time_ns": received,
                                "event_time_ns": received,
                                "ingested_time_ns": ingested,
                                "provider_time_ns": received,
                                "received_time_ns": received,
                            },
                            raw_payload=payload,
                            quality_flags=flags,
                        ),
                        max_records=MAX_RECORDS,
                    )
                    written += 1
            time.sleep(1.0)
        quote_ctx.unsubscribe(codes, [ft.SubType.QUOTE, ft.SubType.TICKER, ft.SubType.ORDER_BOOK])
    finally:
        quote_ctx.close()
    print(f"wrote {written} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

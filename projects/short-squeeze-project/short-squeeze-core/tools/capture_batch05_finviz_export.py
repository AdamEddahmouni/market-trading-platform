#!/usr/bin/env python3
"""Capture a fresh Finviz Elite export for Phase 3F Batch 05 external discovery.

Supports live API capture (requires valid FINVIZ_API_KEY) or offline normalization from
a saved CSV (--csv-path). Updates the preregistered normalized discovery artifact with
selected symbols excluding the frozen IBKR cohort.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.research_screener.credentials import default_private_path, load_private_env
from apps.research_screener.private_config import load_provider_credentials
from apps.research_screener.finviz_live import DEFAULT_FILTER, FinvizClient, _parse_row, castdict

BATCH_DIR = ROOT / "intake" / "batches" / "phase-3f-cohort-expansion-05-external"
PREREG_PATH = BATCH_DIR / "normalized" / "batch3f05_external_discovery_preregistration.json"
ROWS_OUT = BATCH_DIR / "normalized" / "batch3f05_external_discovery_rows.json"
RAW_DIR = BATCH_DIR / "raw"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_prereg() -> dict:
    return json.loads(PREREG_PATH.read_text(encoding="utf-8"))


def _rows_from_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if "Ticker" not in tuple(reader.fieldnames or ()):
        raise ValueError("CSV missing Ticker column — not a Finviz export")
    return [_parse_row(castdict(row)).as_dict() for row in reader if row.get("Ticker")]


def _select_symbols(
  parsed_rows: list[dict],
  excluded: set[str],
  *,
  min_symbols: int,
  max_symbols: int,
) -> list[str]:
    selected: list[str] = []
    for row in parsed_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker in excluded:
            continue
        if ticker in selected:
            continue
        selected.append(ticker)
        if len(selected) >= max_symbols:
            break
    if len(selected) < min_symbols:
        raise ValueError(
            f"only {len(selected)} new symbol(s) found; need {min_symbols}–{max_symbols}"
        )
    return selected


def _build_rows(
    parsed_rows: list[dict],
    symbols: list[str],
    observed_at: str,
) -> list[dict]:
    by_ticker = {str(r["ticker"]).upper(): r for r in parsed_rows if r.get("ticker")}
    rows: list[dict] = []
    for index, symbol in enumerate(symbols, start=1):
        source = by_ticker.get(symbol, {})
        rows.append(
            {
                "ticker": symbol,
                "observed_at": observed_at,
                "original_order": index,
                "detection_time_evidence": {},
                "missing_detection_domains": [
                    "PRICE",
                    "RELATIVE_VOLUME",
                    "SHORT_FLOAT_PERCENT",
                    "DAYS_TO_COVER",
                    "FLOAT_SHARES",
                    "IB_BORROW_FEE_RATE",
                    "IB_SHORTABLE_SHARES",
                ],
                "discovery_provenance": {
                    "source": "FRESH_FINVIZ_ELITE_EXPORT",
                    "filter": DEFAULT_FILTER,
                    "short_float_pct": source.get("short_float_pct"),
                    "float_shares": source.get("float_shares"),
                    "rel_volume": source.get("rel_volume"),
                },
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-path",
        type=Path,
        help="Offline Finviz Elite CSV (skip live API)",
    )
    parser.add_argument(
        "--providers-env",
        type=Path,
        default=None,
        help="Private provider file (default: .private/providers.env)",
    )
    parser.add_argument("--min-symbols", type=int, default=3)
    parser.add_argument("--max-symbols", type=int, default=5)
    parser.add_argument(
        "--observed-at",
        help="UTC instant for cohort boundary (default: now)",
    )
    args = parser.parse_args()

    prereg = _load_prereg()
    excluded = set(prereg.get("excluded_symbols") or [])
    observed_at = args.observed_at or datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

    if args.csv_path is not None:
        csv_bytes = args.csv_path.read_bytes()
        text = csv_bytes.decode("utf-8", errors="replace")
        parsed = _rows_from_csv(text)
        sha = _sha256_bytes(csv_bytes)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        dest = RAW_DIR / f"finviz-export-{observed_at[:10]}.csv"
        if not dest.exists():
            dest.write_bytes(csv_bytes)
    else:
        env_path = args.providers_env or default_private_path()
        if env_path is None:
            print("No --csv-path and no .private/providers.env found")
            return 2
        load_private_env(env_path, verbose=False)
        creds = load_provider_credentials(env_path)
        key = creds.values.get("FINVIZ_API_KEY")
        client = FinvizClient(key)
        response = client.fetch_screener(force=True)
        if not response.get("success"):
            print(f"Finviz export failed: {response.get('error')}")
            print("Refresh FINVIZ_API_KEY or pass --csv-path with a saved export CSV")
            return 2
        cached = client.get_cached_rows() or []
        parsed = [row.as_dict() for row in cached]
        text = "\n".join(
            ["Ticker"] + [row["ticker"] for row in parsed]
        )
        sha = _sha256_bytes(text.encode("utf-8"))

    symbols = _select_symbols(
        parsed,
        excluded,
        min_symbols=args.min_symbols,
        max_symbols=args.max_symbols,
    )
    discovery_rows = _build_rows(parsed, symbols, observed_at)

    document = {
        "document": "phase_3f_batch_05_external_discovery_rows",
        "schema_version": "1.0.0",
        "status": "CAPTURED_AWAITING_IDENTITY_AUDIT",
        "discovery_lane": "FRESH_FINVIZ_ELITE_EXPORT",
        "raw_source": {
            "provider": "Finviz Elite",
            "endpoint": "https://elite.finviz.com/export/screener",
            "filter": DEFAULT_FILTER,
            "classification": "EXTERNAL_PROVIDER_EXPORT",
            "capture_timestamp": observed_at,
            "raw_csv_sha256": sha,
            "csv_archive": str(RAW_DIR.relative_to(ROOT)).replace("\\", "/")
            if args.csv_path is not None
            else None,
        },
        "selection_policy": prereg.get("selection_policy"),
        "excluded_symbols": sorted(excluded),
        "rows": discovery_rows,
        "transformation": prereg.get("transformation"),
    }

    ROWS_OUT.parent.mkdir(parents=True, exist_ok=True)
    ROWS_OUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ROWS_OUT.resolve()}")
    print(f"symbols={','.join(symbols)} sha256={sha}")
    print("Next: IBKR identity audit, then acquisition per phase-3f-cohort-expansion-batch-05-external.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

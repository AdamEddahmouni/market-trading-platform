"""Command-line interface for the standalone options engine."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import validate

from main import run_from_request
from options_engine.utils import PROJECT_ROOT, load_json


CONTRACTS_DIR = PROJECT_ROOT / "contracts"
INPUT_SCHEMA_PATH = CONTRACTS_DIR / "input_schema.json"


def _load_input_schema() -> Dict[str, Any]:
    return load_json(INPUT_SCHEMA_PATH, {})


def _validate_payload(payload: Dict[str, Any]) -> None:
    schema = _load_input_schema()
    if schema:
        validate(instance=payload, schema=schema)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone Options Confirmation Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_cmd = subparsers.add_parser("score", help="Score a single ticker")
    score_cmd.add_argument("--ticker", required=True)
    score_cmd.add_argument("--as-of", default=None)

    batch_cmd = subparsers.add_parser("score-batch", help="Score tickers from input JSON file")
    batch_cmd.add_argument("--input", required=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "score":
        payload: Dict[str, Any] = {
            "request_id": datetime.now(timezone.utc).isoformat(),
            "as_of": args.as_of,
            "tickers": [args.ticker.upper().strip()],
        }
    else:
        payload = load_json(Path(args.input), {})
        if not isinstance(payload, dict):
            raise ValueError("Batch input must be a JSON object")

    _validate_payload(payload)
    result = run_from_request(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


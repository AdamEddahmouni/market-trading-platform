"""Contract tests for input and output schemas."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from jsonschema import validate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.utils import load_json


class ContractTests(unittest.TestCase):
    """Validate example payloads against schemas."""

    def test_input_example_matches_schema(self) -> None:
        schema = load_json(PROJECT_ROOT / "contracts" / "input_schema.json", {})
        payload = load_json(PROJECT_ROOT / "contracts" / "examples" / "input_example.json", {})
        validate(instance=payload, schema=schema)

    def test_output_payload_matches_schema(self) -> None:
        schema = load_json(PROJECT_ROOT / "contracts" / "output_schema.json", {})
        payload = {
            "meta": {"updated_at": "2026-01-01T00:00:00+00:00", "request_id": "req-1", "count": 1},
            "items": [
                {
                    "ticker": "AAPL",
                    "request_id": "req-1",
                    "as_of": "2026-01-01T00:00:00+00:00",
                    "options_score": 55.0,
                    "options_bias": "neutral",
                    "feature_values": {"iv_rank": 0.5},
                    "data_quality": {"quality_score": 1.0, "flags": []},
                    "reasoning_summary": "ok",
                }
            ],
        }
        validate(instance=payload, schema=schema)


if __name__ == "__main__":
    unittest.main()


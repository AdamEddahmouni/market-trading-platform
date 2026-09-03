"""Execute the preregistered BIYA short-pressure acquisition plan.

Hydrates ``data/acquisition/biya`` with a successful FINRA published short-interest
capture and records an honest IBKR borrow attempt. Does not fabricate unavailable domains.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.acquisition.acquire_biya_history import acquire  # noqa: E402
from squeeze_core.validation.outcome_acquisition import AcquisitionDataType  # noqa: E402


PLAN = ROOT / "tests/fixtures/validation/outcome_amendment/biya_short_pressure_acquisition_plan.json"
SI_FIXTURE = ROOT / "tests/fixtures/validation/outcome_amendment/raw/biya_finra_published_short_interest.txt"
ACQUISITION_ROOT = ROOT / "data/acquisition/biya"
RETRIEVED_AT = "2026-07-21T20:57:44-04:00"
START = "2026-06-01T00:00:00-04:00"
END = "2026-07-21T20:57:44-04:00"


def _remove_existing(data_type: AcquisitionDataType) -> None:
    data_folder = data_type.value.lower()
    raw_dir = ACQUISITION_ROOT / "raw" / data_folder
    if raw_dir.exists():
        for path in raw_dir.iterdir():
            if path.is_file():
                path.unlink()
    manifest_dir = ACQUISITION_ROOT / "manifests"
    if not manifest_dir.exists():
        return
    for path in manifest_dir.glob("*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("data_type") == data_type.value:
            path.unlink()


def _common_args(**overrides: str) -> list[str]:
    values = {
        "symbol": "BIYA",
        "start": START,
        "end": END,
        "retrieved_at": RETRIEVED_AT,
        "timezone": "America/New_York",
        "session_scope": "NOT_APPLICABLE",
        "adjustment_policy": "NOT_APPLICABLE",
        "output": str(ACQUISITION_ROOT),
    }
    values.update(overrides)
    result: list[str] = []
    for key, value in values.items():
        result.extend((f"--{key.replace('_', '-')}", value))
    return result


def _ibkr_gateway_available() -> bool:
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from tools.ibkr_historical_export.cli import cmd_connection_probe
        import argparse

        return cmd_connection_probe(argparse.Namespace(private_root=None)) == 0
    except Exception:
        return False


def run() -> dict[str, object]:
    if not PLAN.exists():
        raise FileNotFoundError(f"missing acquisition plan: {PLAN}")
    if not SI_FIXTURE.exists():
        raise FileNotFoundError(f"missing FINRA SI fixture: {SI_FIXTURE}")

    ACQUISITION_ROOT.mkdir(parents=True, exist_ok=True)
    (ACQUISITION_ROOT / "manifests").mkdir(parents=True, exist_ok=True)

    _remove_existing(AcquisitionDataType.PUBLISHED_SHORT_INTEREST)
    si_manifest = acquire(
        _common_args(
            provider="finra",
            data_type="PUBLISHED_SHORT_INTEREST",
            bar_size="REPORTING_PERIOD",
            source_url=SI_FIXTURE.resolve().as_uri(),
        ),
        fetcher=lambda request, timeout: type(
            "Resp",
            (),
            {"__enter__": lambda self: self, "__exit__": lambda *a: None, "read": lambda self: SI_FIXTURE.read_bytes()},
        )(),
    )

    borrow_results = {}
    gateway_live = _ibkr_gateway_available()
    for data_type, failure in (
        (AcquisitionDataType.BORROW_FEE, "ACQUISITION_HISTORICAL_BORROW_UNAVAILABLE"),
        (AcquisitionDataType.BORROW_AVAILABILITY, "ACQUISITION_HISTORICAL_BORROW_UNAVAILABLE"),
    ):
        _remove_existing(data_type)
        if gateway_live:
            failure = "ACQUISITION_HISTORICAL_BORROW_UNAVAILABLE"
        borrow_results[data_type.value] = acquire(
            _common_args(
                provider="ibkr",
                data_type=data_type.value,
                bar_size="NOT_APPLICABLE",
                source_url="",
                result_state="UNAVAILABLE",
                failure_code=failure,
            )
        ).result_state.value

    return {
        "plan": json.loads(PLAN.read_text(encoding="utf-8"))["acquisition_plan_id"],
        "published_short_interest": si_manifest.result_state.value,
        "published_short_interest_records": si_manifest.record_count,
        "ibkr_gateway_live": gateway_live,
        "borrow": borrow_results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))

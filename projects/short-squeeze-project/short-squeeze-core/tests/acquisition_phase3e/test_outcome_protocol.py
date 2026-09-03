"""Forward outcome protocol and separate manifest contract."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from squeeze_core.acquisition.stage2.outcomes import (
    build_outcome,
    outcome_manifest_id_for,
    write_outcome_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_ROOT = ROOT / "tests" / "fixtures" / "acquisition" / "batch08" / "synthetic-batch05"


@pytest.mark.parametrize("symbol,case_id", [
    ("XNCR", "BATCH01_XNCR_20260718"),
    ("TRVI", "BATCH01_TRVI_20260718"),
])
def test_outcome_manifest_is_separate_contract(tmp_path, symbol: str, case_id: str):
    result = build_outcome(
        symbol=symbol,
        case_id=case_id,
        batch05_root=SYNTHETIC_ROOT,
        live_intake=False,
        research_case_id=case_id,
    )
    assert result.manifest_id == outcome_manifest_id_for(case_id)
    assert result.manifest["outcome_manifest_id"] != "BATCH01_DISCOVERY_MANIFEST"
    assert result.manifest["captured"] is True
    assert result.forward_source == "frozen_forward_24h"
    assert result.observation.maximum_observed_move_percent is not None
    paths = write_outcome_artifacts(result, tmp_path)
    manifest = (tmp_path / symbol / "outcome-manifest.json").read_bytes()
    observation = (tmp_path / symbol / "outcome-observation.json").read_bytes()
    assert manifest != observation
    assert paths["manifest_id"] == outcome_manifest_id_for(case_id)


def test_outcome_moves_use_decimal_returns():
    result = build_outcome(
        symbol="XNCR",
        case_id="BATCH01_XNCR_20260718",
        batch05_root=SYNTHETIC_ROOT,
        live_intake=False,
        research_case_id="BATCH01_XNCR_20260718",
    )
    assert isinstance(result.observation.maximum_observed_move_percent, Decimal)
    assert isinstance(result.observation.maximum_adverse_move_percent, Decimal)

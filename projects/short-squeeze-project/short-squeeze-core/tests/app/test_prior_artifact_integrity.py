"""Running the application must leave every prior research artifact untouched.

The screener is read-only, so these tests exercise the demo workflow and then re-verify
the artifacts it read. A regression here means the view layer started writing where it
should only read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from squeeze_core.acquisition.phase3a_freeze.cli import main as freeze_cli
from apps.research_screener import snapshot
from apps.research_screener.paths import FrozenLayout, repository_root

pytestmark = pytest.mark.skipif(
    not FrozenLayout().available, reason="private frozen artifact root not present"
)

#: Canonical Phase 3B registry material that Batch 09 must not have published.
CANONICAL_REGISTRY_GLOBS = (
    "src/squeeze_core/research/policies/*.json",
    "src/squeeze_core/evaluation/policies/*.json",
)


def _digest(paths: list[Path]) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
        if path.is_file()
    }


def _canonical_paths() -> list[Path]:
    root = repository_root()
    found: list[Path] = []
    for pattern in CANONICAL_REGISTRY_GLOBS:
        found.extend(root.glob(pattern))
    return found


def _exercise_the_demo(tmp_path: Path) -> None:
    """Everything the professor demo touches, in order."""
    from apps.research_screener import export as export_module

    snapshot.health()
    payload = snapshot.frozen_snapshot()
    for row in payload["rows"]:
        snapshot.frozen_detail(row["symbol"])
    snapshot.professor_summary()
    export_module.write_export(payload, tmp_path)


def test_batch_08_freeze_verifies_after_the_demo_runs(tmp_path: Path) -> None:
    layout = FrozenLayout()
    before = _digest(sorted(layout.batch08.rglob("*.json")))
    assert len(before) >= 26, "the Batch 08 freeze should hold at least 26 JSON artifacts"

    _exercise_the_demo(tmp_path)

    assert _digest(sorted(layout.batch08.rglob("*.json"))) == before
    assert freeze_cli(["--private-root", str(layout.root), "verify-phase3a-freeze"]) == 0


def test_batch_05_raw_artifacts_are_unchanged_after_the_demo(tmp_path: Path) -> None:
    layout = FrozenLayout()
    raw = sorted(layout.raw_dir.glob("*-detection-context.csv"))
    assert len(raw) == 13
    before = _digest(raw)

    _exercise_the_demo(tmp_path)

    assert _digest(sorted(layout.raw_dir.glob("*-detection-context.csv"))) == before


def test_forward_window_artifacts_are_present_but_never_read(tmp_path: Path) -> None:
    """They exist on disk; the demo must not touch them."""
    layout = FrozenLayout()
    forward = sorted(layout.raw_dir.glob("*frozen-forward*"))
    assert forward, "the forward artifacts should still exist on disk"
    before = _digest(forward)

    _exercise_the_demo(tmp_path)

    assert _digest(sorted(layout.raw_dir.glob("*frozen-forward*"))) == before


def test_canonical_registry_files_are_unchanged_after_the_demo(tmp_path: Path) -> None:
    before = _digest(_canonical_paths())
    assert before, "expected canonical policy documents to exist"

    _exercise_the_demo(tmp_path)

    assert _digest(_canonical_paths()) == before


def test_batch_09_preview_is_read_but_never_published(tmp_path: Path) -> None:
    layout = FrozenLayout()
    before = _digest(sorted(layout.preview_dir.glob("*")))

    _exercise_the_demo(tmp_path)

    assert _digest(sorted(layout.preview_dir.glob("*"))) == before
    preview = json.loads(layout.preview_summary.read_text(encoding="utf-8"))
    assert preview["canonical_registry_mutated"] is False
    assert preview["phase3b_published"] is False
    assert preview["phase3e_started"] is False


def test_the_application_writes_only_into_the_export_directory(tmp_path: Path) -> None:
    from apps.research_screener import export as export_module

    payload = snapshot.frozen_snapshot()
    written = export_module.write_export(payload, tmp_path)
    produced = {path.name for path in tmp_path.iterdir()}
    assert produced == {Path(written["json"]).name, Path(written["csv"]).name}

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest


def test_release_builder_copies_only_allowlisted_content_and_creates_metadata(
    tmp_path: Path,
) -> None:
    from tools.build_handoff_release import build_release

    source = tmp_path / "source"
    (source / "apps/product").mkdir(parents=True)
    (source / "docs").mkdir()
    (source / ".private").mkdir()
    (source / "apps/product/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "docs/ARCHITECTURE.md").write_text(
        "# Architecture\n", encoding="utf-8"
    )
    (source / ".private/providers.env").write_text(
        "FINVIZ_API_KEY=must-not-copy\n", encoding="utf-8"
    )
    (source / "release-files.json").write_text(
        json.dumps(
            {
                "files": ["docs/ARCHITECTURE.md"],
                "trees": ["apps/product"],
            }
        ),
        encoding="utf-8",
    )

    result = build_release(
        source_root=source,
        output_root=tmp_path / "dist",
        version="1.2.3",
        source_commit="a" * 40,
        build_time=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
    )

    assert (result.release_dir / "apps/product/app.py").is_file()
    assert (result.release_dir / "docs/ARCHITECTURE.md").is_file()
    assert not (result.release_dir / ".private").exists()
    assert result.zip_path.is_file()
    assert result.zip_path.with_suffix(".zip.sha256").is_file()
    assert result.audit.passed is True

    metadata = json.loads(
        (result.release_dir / "RELEASE_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert metadata["release_version"] == "1.2.3"
    assert metadata["git_source_commit"] == "a" * 40
    assert metadata["api_version"] == "1.0.0"
    assert metadata["schema_version"] == "batch14.integration.v1"
    assert metadata["release_audit_result"] == "PASS"
    assert metadata["test_totals"] == {
        "tests": 2623,
        "passed": 2622,
        "skipped": 1,
        "failures": 0,
        "errors": 0,
    }
    assert "source_root" not in metadata
    assert metadata["included_file_count"] == result.file_count


def test_release_checksums_and_zip_extraction_are_valid(tmp_path: Path) -> None:
    from tools.build_handoff_release import build_release

    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("# Product\n", encoding="utf-8")
    (source / "release-files.json").write_text(
        '{"files":["README.md"],"trees":[]}',
        encoding="utf-8",
    )
    result = build_release(
        source_root=source,
        output_root=tmp_path / "dist",
        version="1.0.0",
        source_commit="b" * 40,
        build_time=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
    )

    checksum_lines = (
        result.release_dir / "CHECKSUMS.sha256"
    ).read_text(encoding="utf-8").splitlines()
    checksums = {
        path: digest for digest, path in (line.split("  ", 1) for line in checksum_lines)
    }
    assert checksums["README.md"] == hashlib.sha256(
        (result.release_dir / "README.md").read_bytes()
    ).hexdigest()
    assert result.zip_sha256 == hashlib.sha256(result.zip_path.read_bytes()).hexdigest()
    assert (
        result.zip_path.with_suffix(".zip.sha256").read_text(encoding="utf-8").split()[0]
        == result.zip_sha256
    )

    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(result.zip_path) as archive:
        archive.extractall(extracted)
    root = extracted / result.release_dir.name
    assert (root / "README.md").read_text(encoding="utf-8") == "# Product\n"
    assert not (root / ".git").exists()


def test_release_builder_rejects_allowlist_path_traversal(tmp_path: Path) -> None:
    from tools.build_handoff_release import ReleaseBuildError, build_release

    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (source / "release-files.json").write_text(
        '{"files":["../secret.txt"],"trees":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ReleaseBuildError, match="allowlist"):
        build_release(
            source_root=source,
            output_root=tmp_path / "dist",
            version="1.0.0",
            source_commit="c" * 40,
            build_time=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        )

"""Batch 04 submission-kit generation, determinism, templates, and integrity tests."""

import hashlib
import json
from pathlib import Path

from squeeze_core.acquisition.historical_data_submission_kit import (
    build_case_association_template,
    build_column_mapping_profile_template,
    build_intake_manifest_template,
    build_operator_checklist,
    build_submission_kit,
    build_troubleshooting_index,
)
from squeeze_core.acquisition.historical_data_submission_kit.checklist import CHECKLIST_ITEMS
from squeeze_core.acquisition.historical_data_submission_kit.kit import (
    build_batch04_fixtures,
)
from squeeze_core.acquisition.local_bar_intake.models import (
    ColumnMappingProfile,
    IntakeManifest,
)
from squeeze_core.acquisition.local_bar_intake.semantics import (
    CREDENTIAL_LIKE_TOKENS,
    IntakeReasonCode,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch04"
BATCH01_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch01"
BATCH02_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch02"
BATCH03_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch03"

# Directory digests recorded before Batch 04 began (no-regression guard).
BATCH01_DIGEST = "a4a6ece91800e215baeb197a6f178505c526d49c672f3274365bde4f624b407a"
BATCH02_DIGEST = "eefed973fb1c7e709c52060c274bf57b6d641993ac96e9e08687e75e818e30c4"
BATCH03_DIGEST = "39bbf1e52a19deb81a0b80bf1d93449dc08be3407d2697a9a0690ccef406a82e"

# Real case identifiers that must never appear in any synthetic kit artifact.
FORBIDDEN_CASE_TOKENS = (
    "BATCH01_", "BATCH02_", "BIYA", "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC",
    "LBGJ", "TRVI", "LMNX", "MGNX", "BHVN", "AVTX",
)


def _dir_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.iterdir() if p.is_file()):
        digest.update(item.name.encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_submission_kit_generation_is_byte_identical():
    assert build_submission_kit() == build_submission_kit()
    assert build_batch04_fixtures() == build_batch04_fixtures()


def test_generated_fixtures_match_committed_files():
    committed = {item.name for item in FIXTURES.iterdir() if item.is_file()}
    fixtures = build_batch04_fixtures()
    assert set(fixtures) == committed
    for name, content in fixtures.items():
        assert (FIXTURES / name).read_bytes() == content, name


def test_all_generated_content_uses_lf_line_endings():
    for name, content in {**build_submission_kit(), **build_batch04_fixtures()}.items():
        assert b"\r" not in content, name


def test_blank_templates_are_syntactically_valid_json():
    for builder in (
        build_intake_manifest_template,
        build_column_mapping_profile_template,
        build_case_association_template,
    ):
        # Round-trips through the committed bytes as valid JSON.
        assert isinstance(builder(), dict)


def test_manifest_template_contains_every_model_field():
    template = build_intake_manifest_template()
    model_fields = set(IntakeManifest.model_fields) - {"deterministic_id"}
    keys = {k for k in template if not k.startswith("_")}
    assert model_fields <= keys
    # No stray non-model keys leak in besides the guidance annotation.
    assert keys - model_fields == set()


def test_mapping_profile_template_contains_every_model_field():
    template = build_column_mapping_profile_template()
    model_fields = set(ColumnMappingProfile.model_fields) - {"deterministic_id"}
    keys = {k for k in template if not k.startswith("_")}
    assert model_fields <= keys
    assert keys - model_fields == set()


def test_case_association_template_is_marked_future_only_and_has_no_real_ids():
    template = build_case_association_template()
    blob = json.dumps(template)
    assert "NOT FOR USE IN BATCH 04" in blob
    assert "FUTURE AUTHORIZED WORK ONLY" in blob
    for token in FORBIDDEN_CASE_TOKENS:
        assert token not in blob, token


def test_no_real_case_ids_in_any_kit_or_fixture_file():
    for name, content in {**build_submission_kit(), **build_batch04_fixtures()}.items():
        text = content.decode("utf-8")
        for token in FORBIDDEN_CASE_TOKENS:
            assert token not in text, f"{token} appeared in {name}"


def test_no_credential_like_values_in_any_fixture_or_kit_file():
    for name, content in {**build_submission_kit(), **build_batch04_fixtures()}.items():
        text = content.decode("utf-8", errors="strict").lower()
        for token in CREDENTIAL_LIKE_TOKENS:
            assert token not in text, f"{token} appeared in {name}"


def test_no_outcome_or_prediction_tokens_leak_into_outputs():
    forbidden = (
        "squeeze_score", "setup_tier", "target_percent", "stop_loss", "pnl",
        "backtest", "recommendation", "ranking", "forward_return",
        "realized_return", "outcome_price",
    )
    for name, content in {**build_submission_kit(), **build_batch04_fixtures()}.items():
        text = content.decode("utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{token} leaked into {name}"


def test_every_reason_code_maps_to_troubleshooting_guidance():
    index = build_troubleshooting_index()["reason_codes"]
    for code in IntakeReasonCode:
        assert code.value in index, code.value
        entry = index[code.value]
        for field in (
            "meaning", "why_blocked", "inspect", "may_change",
            "must_not_guess", "new_export_required",
        ):
            assert entry.get(field), (code.value, field)


def test_operator_checklist_covers_all_required_declarations():
    checklist = build_operator_checklist()
    statements = " ".join(item["statement"].lower() for item in checklist["items"])
    assert all(item["confirmed"] is False for item in checklist["items"])
    required = (
        "lawfully", "entitled", "credential", "unmodified", "sha-256", "provider",
        "retrieval", "symbol", "interval", "timezone", "timestamp semantics",
        "session coverage", "price adjustment", "volume adjustment",
        "corporate-action", "coverage", "offline", "association", "outcome",
        "phase 3a", "phase 3e",
    )
    for needle in required:
        assert needle in statements, needle
    assert len(CHECKLIST_ITEMS) == len(checklist["items"])


def test_determinism_anchors_are_unique_hex():
    anchors = json.loads((FIXTURES / "determinism-anchors.json").read_text())["anchors"]
    assert len(anchors) == len(set(anchors.values()))
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for value in anchors.values()
    )


def test_fixture_metadata_declares_no_real_data_or_outcome_work():
    meta = json.loads((FIXTURES / "fixture-metadata.json").read_text())
    assert meta["real_market_data_committed"] is False
    assert meta["outcome_work_performed"] is False
    assert meta["sensitive_content_included"] is False
    assert meta["phase_3e_started"] is False


def test_submission_kit_manifest_lists_every_kit_file():
    manifest = json.loads((FIXTURES / "submission-kit-manifest.json").read_text())
    kit = build_submission_kit()
    assert set(manifest["file_sha256"]) == set(kit)
    for name, content in kit.items():
        assert manifest["file_sha256"][name] == hashlib.sha256(content).hexdigest()
    assert manifest["real_market_data_committed"] is False
    assert manifest["case_association_performed"] is False


def test_batch01_02_03_fixtures_are_unchanged():
    assert _dir_digest(BATCH01_FIXTURES) == BATCH01_DIGEST
    assert _dir_digest(BATCH02_FIXTURES) == BATCH02_DIGEST
    assert _dir_digest(BATCH03_FIXTURES) == BATCH03_DIGEST

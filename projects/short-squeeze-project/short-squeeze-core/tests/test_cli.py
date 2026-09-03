import json
from pathlib import Path

from squeeze_core.__main__ import main
from squeeze_core.serialization import serialize_jsonl


def write_fixture(path: Path, observations: list[object]) -> None:
    path.write_bytes(serialize_jsonl(observations))


def test_validate_command_prints_machine_readable_success(tmp_path, capsys, make_observation) -> None:
    fixture = tmp_path / "fixture.jsonl"
    write_fixture(fixture, [make_observation("first")])
    exit_code = main(["validate", str(fixture)])
    output = capsys.readouterr()
    assert exit_code == 0
    assert '"valid":true' in output.out
    assert output.err == ""


def test_validate_command_returns_nonzero_for_invalid_jsonl(tmp_path, capsys) -> None:
    fixture = tmp_path / "invalid.jsonl"
    fixture.write_text("not-json\n", encoding="utf-8")
    exit_code = main(["validate", str(fixture)])
    output = capsys.readouterr()
    assert exit_code != 0
    assert '"valid":false' in output.err


def test_replay_command_honors_strict_and_normalized_modes(tmp_path, capsys, make_observation) -> None:
    fixture = tmp_path / "out-of-order.jsonl"
    write_fixture(
        fixture,
        [make_observation("second", offset_seconds=1), make_observation("first")],
    )
    assert main(["replay", str(fixture), "--mode", "strict"]) != 0
    capsys.readouterr()
    assert main(["replay", str(fixture), "--mode", "normalized"]) == 0
    output = capsys.readouterr()
    assert "INPUT_ORDER_NORMALIZED" in output.out


def test_normalize_provider_command_uses_local_files_and_prints_canonical_observations(
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/providers/ibkr")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "ibkr",
            "--input",
            str(fixture_root / "representative_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "ibkr-representative-complete-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.out)

    assert exit_code == 0
    assert parsed["accepted"] is True
    assert len(parsed["observations"]) == 2
    assert {item["event_type"] for item in parsed["observations"]} == {
        "BORROW_FEE",
        "BORROW_AVAILABILITY",
    }
    assert output.err == ""


def test_normalize_provider_command_returns_nonzero_and_structured_diagnostics_on_rejection(
    tmp_path, capsys
) -> None:
    record_path = tmp_path / "record.json"
    context_path = tmp_path / "context.json"
    record_path.write_text(
        json.dumps(
            {
                "source_record_id": "rejected-cli-case",
                "symbol": "TESTA",
                "fee_rate": "1",
                "fee_rate_unit": "PERCENT_POINTS",
                "available_shares": "100",
                "lender_count": None,
                "hard_to_borrow": None,
                "provider_timestamp": "2026-01-02T09:45:00",
                "provider_timezone": None,
                "delay_status": "UNKNOWN",
            }
        ),
        encoding="utf-8",
    )
    context = json.loads(Path("tests/fixtures/providers/ibkr/context.json").read_text())
    context["source_timezone"] = None
    context_path.write_text(json.dumps(context), encoding="utf-8")

    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "ibkr",
            "--input",
            str(record_path),
            "--context",
            str(context_path),
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.err)

    assert exit_code != 0
    assert parsed["accepted"] is False
    assert parsed["diagnostics"][0]["code"] == "UNKNOWN_TIMEZONE"
    assert parsed["observations"] == []


def test_normalize_finviz_provider_command_emits_one_market_snapshot(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/finviz")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "finviz",
            "--input",
            str(fixture_root / "representative_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "finviz-complete-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.out)

    assert exit_code == 0
    assert parsed["provider"] == "finviz"
    assert parsed["accepted"] is True
    assert len(parsed["observations"]) == 1
    assert parsed["observations"][0]["event_type"] == "MARKET_SNAPSHOT"
    assert parsed["observations"][0]["payload"]["short_float_percent"] == "12.5"
    assert output.err == ""


def test_build_evidence_command_emits_stable_strategy_neutral_bundle(capsys) -> None:
    input_path = Path("tests/fixtures/evidence/normalized_point_in_time.jsonl")
    arguments = [
        "build-evidence",
        "--input",
        str(input_path),
        "--symbol",
        "TESTA",
        "--as-of",
        "2026-01-15T15:30:00Z",
    ]
    first_exit = main(arguments)
    first_output = capsys.readouterr()
    second_exit = main(arguments)
    second_output = capsys.readouterr()
    parsed = json.loads(first_output.out)

    assert first_exit == second_exit == 0
    assert first_output.out == second_output.out
    assert parsed["symbol"] == "TESTA"
    assert len(parsed["observations"]) == 3
    assert len(parsed["bundle_hash"]) == 64
    assert parsed["conflicts"] == []
    assert first_output.err == second_output.err == ""
    assert not ({"score", "recommendation", "rank", "entry", "exit"} & parsed.keys())


def test_build_evidence_command_accepts_explicit_local_policy(tmp_path, capsys) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "as_of": "2026-01-15T15:30:00Z",
                "maximum_future_skew_ms": 0,
                "maximum_age_ms_by_event_type": {"MARKET_SNAPSHOT": 1},
                "allow_stale": False,
                "allow_delayed": True,
                "allow_unknown_freshness": True,
                "conflict_tolerance": {},
                "source_priority_metadata": {},
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(
        [
            "build-evidence",
            "--input",
            "tests/fixtures/evidence/normalized_point_in_time.jsonl",
            "--symbol",
            "TESTA",
            "--as-of",
            "2026-01-15T15:30:00Z",
            "--policy",
            str(policy_path),
        ]
    )
    parsed = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert all(item["event_type"] != "MARKET_SNAPSHOT" for item in parsed["observations"])


def test_normalize_finra_provider_command_emits_published_short_interest(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/finra")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "finra",
            "--input",
            str(fixture_root / "representative_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "finra-complete-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.out)

    assert exit_code == 0
    assert parsed["provider"] == "finra"
    assert parsed["accepted"] is True
    assert len(parsed["observations"]) == 1
    observation = parsed["observations"][0]
    assert observation["event_type"] == "PUBLISHED_SHORT_INTEREST"
    assert observation["payload"]["settlement_date"] == "2026-01-15"
    assert observation["effective_timestamp"] == "2026-01-22T20:00:00.000000Z"
    assert output.err == ""


def test_normalize_finra_daily_volume_case_returns_structured_rejection(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/finra")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "finra",
            "--input",
            str(fixture_root / "edge_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "finra-daily-short-volume-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.err)

    assert exit_code == 1
    assert parsed["accepted"] is False
    assert parsed["rejection"]["code"] == "FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED"
    assert parsed["observations"] == []


def test_build_evidence_command_applies_phase_1d_revision_and_age_semantics(capsys) -> None:
    exit_code = main(
        [
            "build-evidence",
            "--input",
            "tests/fixtures/evidence/normalized_phase_1d_point_in_time.jsonl",
            "--symbol",
            "TESTA",
            "--as-of",
            "2026-02-01T15:30:00Z",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.out)

    assert exit_code == 0
    assert len(parsed["observations"]) == 5
    assert len(parsed["observation_ages"]) == 2
    assert len(parsed["revision_relationships"]) == 1
    assert output.err == ""


def test_build_evidence_timeline_command_is_deterministic_and_local(capsys) -> None:
    arguments = [
        "build-evidence-timeline",
        "--input",
        "tests/fixtures/evidence/normalized_phase_1d_point_in_time.jsonl",
        "--symbol",
        "TESTA",
        "--as-of-file",
        "tests/fixtures/evidence/short_interest_publication_timeline.json",
    ]
    first_exit = main(arguments)
    first = capsys.readouterr()
    second_exit = main(arguments)
    second = capsys.readouterr()
    parsed = json.loads(first.out)

    assert first_exit == second_exit == 0
    assert first.out == second.out
    assert set(parsed["bundles"]) == {
        "before_publication",
        "after_publication_before_receipt",
        "after_original_receipt",
        "before_correction_receipt",
        "after_correction_receipt",
    }
    assert len(parsed["bundles"]["after_correction_receipt"]["observations"]) == 5
    assert first.err == second.err == ""


def test_normalize_sec_provider_command_emits_objective_filing_metadata(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/sec")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "sec",
            "--input",
            str(fixture_root / "representative_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "sec-complete-original-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.out)
    assert exit_code == 0
    assert parsed["provider"] == "sec"
    assert parsed["observations"][0]["event_type"] == "SEC_FILING"
    assert parsed["observations"][0]["payload"]["accession_number"] == "0000000001-26-000001"
    assert "sentiment" not in output.out
    assert "catalyst" not in output.out
    assert output.err == ""


def test_normalize_invalid_sec_accession_returns_structured_rejection(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/sec")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "sec",
            "--input",
            str(fixture_root / "edge_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "sec-invalid-accession-v1",
        ]
    )
    output = capsys.readouterr()
    parsed = json.loads(output.err)
    assert exit_code == 1
    assert parsed["rejection"]["code"] == "SEC_INVALID_ACCESSION"


def test_build_sec_evidence_timeline_command_is_deterministic(capsys) -> None:
    arguments = [
        "build-evidence-timeline",
        "--input",
        "tests/fixtures/evidence/normalized_phase_1e_point_in_time.jsonl",
        "--symbol",
        "TESTA",
        "--as-of-file",
        "tests/fixtures/evidence/sec_filing_availability_timeline.json",
    ]
    assert main(arguments) == 0
    first = capsys.readouterr()
    assert main(arguments) == 0
    second = capsys.readouterr()
    parsed = json.loads(first.out)
    assert first.out == second.out
    assert len(parsed["bundles"]["after_amendment_receipt"]["observations"]) == 7
    assert first.err == second.err == ""


def test_normalize_halts_provider_command_emits_objective_lifecycle(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/halts")
    arguments = [
        "normalize-provider",
        "--provider",
        "halts",
        "--input",
        str(fixture_root / "representative_cases.json"),
        "--context",
        str(fixture_root / "context.json"),
        "--case",
        "halt-complete-v1",
    ]
    first_exit = main(arguments)
    first = capsys.readouterr()
    second_exit = main(arguments)
    second = capsys.readouterr()

    assert first_exit == second_exit == 0
    assert first.out == second.out
    parsed = json.loads(first.out)
    assert parsed["provider"] == "halts"
    assert parsed["observations"][0]["event_type"] == "TRADING_HALT"
    assert parsed["observations"][0]["payload"]["halt_status"] == "HALT_ACTIVE"
    assert "score" not in first.out.lower()
    assert "recommendation" not in first.out.lower()
    assert first.err == second.err == ""


def test_normalize_invalid_halt_record_returns_structured_rejection(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/halts")
    exit_code = main(
        [
            "normalize-provider",
            "--provider",
            "halts",
            "--input",
            str(fixture_root / "edge_cases.json"),
            "--context",
            str(fixture_root / "context.json"),
            "--case",
            "halt-invalid-timestamp",
        ]
    )
    captured = capsys.readouterr()
    parsed = json.loads(captured.err)
    assert exit_code == 1
    assert parsed["accepted"] is False
    assert parsed["rejection"]["code"] == "INVALID_NUMERIC_VALUE"
    assert captured.out == ""


def test_normalize_news_provider_command_emits_objective_metadata(capsys) -> None:
    fixture_root = Path("tests/fixtures/providers/news")
    arguments = [
        "normalize-provider", "--provider", "news",
        "--input", str(fixture_root / "representative_cases.json"),
        "--context", str(fixture_root / "context.json"),
        "--case", "news-complete-v1",
    ]
    assert main(arguments) == 0
    first = capsys.readouterr()
    assert main(arguments) == 0
    second = capsys.readouterr()

    assert first.out == second.out
    parsed = json.loads(first.out)
    assert parsed["provider"] == "news"
    assert parsed["observations"][0]["event_type"] == "NEWS_ITEM"
    assert parsed["observations"][0]["payload"]["associated_symbols"] == ["TESTA"]
    for forbidden in ("sentiment", "catalyst", "materiality", "relevance", "recommendation"):
        assert forbidden not in first.out.lower()
    assert first.err == second.err == ""


def test_news_evidence_timeline_command_is_deterministic(capsys) -> None:
    arguments = [
        "build-evidence-timeline",
        "--input", "tests/fixtures/evidence/normalized_phase_1g_point_in_time.jsonl",
        "--symbol", "TESTA",
        "--as-of-file", "tests/fixtures/evidence/news_availability_timeline.json",
    ]
    assert main(arguments) == 0
    first = capsys.readouterr()
    assert main(arguments) == 0
    second = capsys.readouterr()
    parsed = json.loads(first.out)

    assert first.out == second.out
    final = parsed["bundles"]["after_withdrawal_receipt"]
    assert len(final["observations"]) == 15
    assert len(final["news_relationships"]) == 2
    assert first.err == second.err == ""


def test_build_halt_state_command_is_deterministic_and_objective(capsys) -> None:
    arguments = [
        "build-halt-state",
        "--input",
        "tests/fixtures/evidence/normalized_phase_1f_point_in_time.jsonl",
        "--symbol",
        "TESTA",
        "--as-of",
        "2026-01-15T15:41:00Z",
    ]
    first_exit = main(arguments)
    first = capsys.readouterr()
    second_exit = main(arguments)
    second = capsys.readouterr()

    assert first_exit == second_exit == 0
    assert first.out == second.out
    parsed = json.loads(first.out)
    assert parsed["command"] == "build-halt-state"
    assert parsed["halt_state"]["state"] == "TRADING_RESUMED"
    assert len(parsed["halt_state"]["supporting_observation_ids"]) == 5
    for forbidden in ("bullish", "bearish", "prediction", "score", "rank", "recommendation"):
        assert forbidden not in first.out.lower()
    assert first.err == second.err == ""

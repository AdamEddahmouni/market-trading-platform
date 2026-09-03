import json

from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.dataset import build_research_dataset
from squeeze_core.research.serialization import (
    serialize_research_csv,
    serialize_research_json,
    serialize_research_jsonl,
)

from .test_batch import complete_entry, request, write_registry


def dataset(tmp_path):
    return build_research_dataset(
        run_research_batch(request(), write_registry(tmp_path, (complete_entry(),)))
    )


def test_json_and_jsonl_are_canonical_stable_and_preserve_missing_values(tmp_path):
    value = dataset(tmp_path)
    json_bytes = serialize_research_json(value)
    jsonl_bytes = serialize_research_jsonl(value)
    assert json_bytes == serialize_research_json(value)
    assert jsonl_bytes == serialize_research_jsonl(value)
    assert json.loads(json_bytes)["rows"][0]["case_id"] == "CASE-A"
    assert json.loads(jsonl_bytes)["case_id"] == "CASE-A"
    assert jsonl_bytes.endswith(b"\n")


def test_csv_has_stable_columns_lf_decimal_strings_and_no_prohibited_columns(tmp_path):
    value = dataset(tmp_path)
    rendered = serialize_research_csv(value)
    header = rendered.splitlines()[0].decode("utf-8")
    assert b"\r\n" not in rendered
    assert "PRICE_RANGE_outcome" in header
    assert "maximum_observed_move_percent" in header
    assert "score" not in header.lower()
    assert "rank" not in header.lower()
    assert "recommendation" not in header.lower()
    assert rendered == serialize_research_csv(value)


def test_all_exports_contain_no_absolute_paths_or_sensitive_fields(tmp_path):
    value = dataset(tmp_path)
    combined = b"\n".join((
        serialize_research_json(value), serialize_research_jsonl(value),
        serialize_research_csv(value),
    )).lower()
    assert b"c:\\" not in combined
    for prohibited in (b'"pnl"', b'"entry"', b'"exit"', b'"position_size"'):
        assert prohibited not in combined

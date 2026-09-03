"""Generate the additive Phase 2V BIYA outcome fixtures, export, and anchors."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from squeeze_core.serialization import canonical_hash, canonical_json_bytes  # noqa: E402
from squeeze_core.validation.case_spec import build_case_from_spec, load_case_spec  # noqa: E402
from squeeze_core.validation.outcome_acquisition import (  # noqa: E402
    AcquisitionDataType,
    AcquisitionEntitlementState,
    AcquisitionManifest,
    AcquisitionNormalizationState,
    AcquisitionResultState,
    build_acquisition_manifest,
)
from squeeze_core.validation.outcome_amendment import (  # noqa: E402
    BIYA_EARLIEST_BOUNDARY,
    BIYA_LATEST_BOUNDARY,
    OutcomeEvaluationWindow,
    build_boundary_outcome,
)
from squeeze_core.validation.outcome_case import build_biya_outcome_amendment_case  # noqa: E402
from squeeze_core.validation.outcome_context import (  # noqa: E402
    build_unavailable_context,
    normalize_yahoo_news,
    parse_finra_short_sale_volume,
    parse_yahoo_corporate_actions,
)
from squeeze_core.validation.outcome_normalization import normalize_acquired_market_bars  # noqa: E402
from squeeze_core.validation.outcome_public_export import build_public_biya_outcome_export  # noqa: E402
from squeeze_core.validation.public_export import assert_export_is_clean  # noqa: E402


ACQUISITION_ROOT = REPO_ROOT / "data" / "acquisition" / "biya"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "validation" / "outcome_amendment"
CASE_PATH = REPO_ROOT / "tests" / "fixtures" / "validation" / "biya_validation_case.json"
DEMO_PATH = REPO_ROOT / "apps" / "biya-validation-demo" / "data" / "biya-outcome-case.json"


def _manifests() -> tuple[AcquisitionManifest, ...]:
    return tuple(sorted((AcquisitionManifest.model_validate_json(path.read_text(encoding="utf-8"))
                         for path in (ACQUISITION_ROOT / "manifests").glob("*.json")),
                        key=lambda item: item.acquisition_id))


def _find(manifests, data_type, *, provider=None, state=AcquisitionResultState.SUCCESS):
    matches = [item for item in manifests if item.data_type is data_type and item.result_state is state
               and (provider is None or item.provider == provider)]
    if len(matches) != 1:
        raise ValueError(f"expected one {data_type.value}/{provider}/{state.value}, found {len(matches)}")
    return matches[0]


def _raw(manifest: AcquisitionManifest) -> bytes:
    if manifest.raw_relative_path is None:
        raise ValueError(f"manifest {manifest.acquisition_id} has no raw path")
    return (ACQUISITION_ROOT / manifest.raw_relative_path).read_bytes()


def _synthetic_anchor_manifests():
    raw = b'{"fixture":"sanitized"}'
    common = dict(
        symbol="BIYA", provider="fixture-provider",
        data_type=AcquisitionDataType.INTRADAY_MARKET_BARS,
        requested_start=datetime(2026, 7, 16, 4, tzinfo=UTC),
        requested_end=datetime(2026, 7, 21, 21, tzinfo=UTC),
        retrieved_at=datetime(2026, 7, 21, 21, tzinfo=UTC),
        request_timezone="America/New_York", bar_size="1_MINUTE",
        session_scope="REGULAR_AND_EXTENDED", adjustment_policy="PROVIDER_ADJUSTED",
    )
    partial = build_acquisition_manifest(
        **common, result_state=AcquisitionResultState.PARTIAL, raw_bytes=raw,
        raw_relative_path="raw/synthetic/partial.json", record_count=1,
        limitations=("SYNTHETIC_EDGE_CASE: partial session",),
    )
    network = build_acquisition_manifest(
        **common, result_state=AcquisitionResultState.NETWORK_FAILURE,
        errors=("SYNTHETIC_EDGE_CASE: network unavailable",),
    )
    entitlement_values = dict(common)
    entitlement_values["provider"] = "fixture-entitlement-provider"
    entitlement = build_acquisition_manifest(
        **entitlement_values,
        result_state=AcquisitionResultState.ENTITLEMENT_REQUIRED,
        entitlement_state=AcquisitionEntitlementState.UNAVAILABLE,
        errors=("SYNTHETIC_EDGE_CASE: entitlement required",),
    )
    return partial, network, entitlement


def build_artifacts():
    manifests = _manifests()
    intraday_manifest = _find(manifests, AcquisitionDataType.INTRADAY_MARKET_BARS,
                              provider="yahoo-chart")
    daily_manifest = _find(manifests, AcquisitionDataType.DAILY_MARKET_BARS,
                           provider="yahoo-chart")
    news_manifest = _find(manifests, AcquisitionDataType.NEWS, provider="yahoo-search")
    action_manifest = _find(manifests, AcquisitionDataType.CORPORATE_ACTIONS,
                            provider="yahoo-chart")
    intraday = normalize_acquired_market_bars(intraday_manifest, _raw(intraday_manifest))
    daily = normalize_acquired_market_bars(daily_manifest, _raw(daily_manifest))
    news = normalize_yahoo_news(news_manifest, _raw(news_manifest))
    corporate = parse_yahoo_corporate_actions(action_manifest, _raw(action_manifest))
    short_sale = tuple(parse_finra_short_sale_volume(item, _raw(item)) for item in manifests
                       if item.data_type is AcquisitionDataType.FINRA_SHORT_SALE_VOLUME
                       and item.result_state is AcquisitionResultState.SUCCESS)
    unavailable = {}
    for label, kind in (
        ("halt_collection", AcquisitionDataType.TRADING_HALTS),
        ("short_interest_context", AcquisitionDataType.PUBLISHED_SHORT_INTEREST),
        ("borrow_fee_context", AcquisitionDataType.BORROW_FEE),
        ("borrow_availability_context", AcquisitionDataType.BORROW_AVAILABILITY),
    ):
        source = next(item for item in manifests if item.data_type is kind)
        unavailable[label] = build_unavailable_context(label.upper(), source.acquisition_id)
    unavailable["days_to_cover_context"] = build_unavailable_context(
        "DAYS_TO_COVER", unavailable["short_interest_context"].acquisition_manifest_id)
    outcomes = (
        build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, intraday),
        build_boundary_outcome(BIYA_LATEST_BOUNDARY, intraday),
    )
    original = build_case_from_spec(load_case_spec(CASE_PATH))
    context_ids = (
        news.deterministic_id, corporate.deterministic_id,
        *(item.deterministic_id for item in short_sale),
        *(item.deterministic_id for item in unavailable.values()),
    )
    amendment = build_biya_outcome_amendment_case(
        original, outcomes, contextual_evidence_ids=context_ids
    )
    public_context = (
        {"data_type": "NEWS", "record_count": len(news.items),
         "items": tuple({"headline": item.headline, "publisher": item.publisher,
                         "publication_time": item.publication_time, "timing": item.timing.value}
                        for item in news.items)},
        {"data_type": "FINRA_SHORT_SALE_VOLUME",
         "records": tuple(record.model_dump(mode="python") for collection in short_sale
                          for record in collection.records),
         "limitation": "Daily short-sale volume is not published short interest."},
        {"data_type": "CORPORATE_ACTIONS",
         "actions": tuple(item.model_dump(mode="python") for item in corporate.actions),
         "limitation": corporate.limitations[0]},
        {"data_type": "TRADING_HALTS", "availability": "UNAVAILABLE"},
        {"data_type": "PUBLISHED_SHORT_INTEREST", "availability": "UNAVAILABLE"},
        {"data_type": "DAYS_TO_COVER", "availability": "UNAVAILABLE"},
        {"data_type": "BORROW_FEE", "availability": "UNAVAILABLE"},
        {"data_type": "BORROW_AVAILABILITY", "availability": "UNAVAILABLE"},
    )
    public = build_public_biya_outcome_export(original, amendment, context=public_context)
    assert_export_is_clean(canonical_json_bytes(public))
    return {
        "manifests": manifests, "intraday": intraday, "daily": daily, "news": news,
        "corporate": corporate, "short_sale": short_sale, "unavailable": unavailable,
        "original": original, "outcomes": outcomes, "amendment": amendment, "public": public,
    }


def _window(outcome, name):
    return next(item for item in outcome.windows if item.window is name)


def build_anchor_results():
    data = build_artifacts()
    manifests = data["manifests"]
    intraday = data["intraday"]
    daily = data["daily"]
    earliest, latest = data["outcomes"]
    partial, network, entitlement = _synthetic_anchor_manifests()
    success = _find(manifests, AcquisitionDataType.INTRADAY_MARKET_BARS,
                    provider="yahoo-chart")
    short_sale_context = tuple(data["short_sale"])
    results = {
        "successful_acquisition_manifest": success,
        "partial_acquisition_manifest": partial,
        "entitlement_failure_manifest": entitlement,
        "network_failure_manifest": network,
        "normalized_intraday_bars": intraday,
        "normalized_daily_bars": daily,
        "earliest_boundary_reference": earliest.reference,
        "latest_boundary_reference": latest.reference,
        "earliest_boundary_15m_outcome": _window(earliest, OutcomeEvaluationWindow.MINUTES_15),
        "latest_boundary_15m_outcome": _window(latest, OutcomeEvaluationWindow.MINUTES_15),
        "earliest_boundary_1h_outcome": _window(earliest, OutcomeEvaluationWindow.HOUR_1),
        "latest_boundary_1h_outcome": _window(latest, OutcomeEvaluationWindow.HOUR_1),
        "earliest_boundary_session_close": _window(earliest, OutcomeEvaluationWindow.SESSION_CLOSE),
        "latest_boundary_session_close": _window(latest, OutcomeEvaluationWindow.SESSION_CLOSE),
        "next_session_open_outcome": tuple(_window(item, OutcomeEvaluationWindow.NEXT_SESSION_OPEN)
                                           for item in (earliest, latest)),
        "next_session_close_outcome": tuple(_window(item, OutcomeEvaluationWindow.NEXT_SESSION_CLOSE)
                                            for item in (earliest, latest)),
        "twenty_four_hour_outcome": tuple(_window(item, OutcomeEvaluationWindow.HOURS_24)
                                          for item in (earliest, latest)),
        "maximum_through_dataset_end": tuple(_window(item, OutcomeEvaluationWindow.DATASET_END)
                                                for item in (earliest, latest)),
        "news_timing_collection": data["news"],
        "halt_collection": data["unavailable"]["halt_collection"],
        "short_interest_context": data["unavailable"]["short_interest_context"],
        "short_sale_volume_context": short_sale_context,
        "days_to_cover_context": data["unavailable"]["days_to_cover_context"],
        "borrow_context": (data["unavailable"]["borrow_fee_context"],
                           data["unavailable"]["borrow_availability_context"]),
        "corporate_action_context": data["corporate"],
        "biya_outcome_confirmation": data["amendment"].confirmation,
        "biya_updated_validation_case": data["amendment"],
        "biya_updated_public_export": data["public"],
        "mixed_outcome_amendment_output": tuple(sorted((data["amendment"], data["public"]),
                                                        key=lambda item: item.__class__.__name__)),
        "phase_2v_outcome_cli_output": build_biya_outcome_amendment_case(
            data["original"], data["outcomes"]
        ),
        "serialized_outcome_collection": canonical_json_bytes((earliest, latest)),
    }
    return dict(sorted(results.items()))


def _jsonl(path: Path, values) -> None:
    path.write_bytes(b"".join(canonical_json_bytes(item) + b"\n" for item in values))


def write_outputs() -> None:
    data = build_artifacts()
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    normalized_root = ACQUISITION_ROOT / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    normalized_bytes = {
        AcquisitionDataType.INTRADAY_MARKET_BARS: ("biya_intraday_market_dataset.json", canonical_json_bytes(data["intraday"])),
        AcquisitionDataType.DAILY_MARKET_BARS: ("biya_daily_market_dataset.json", canonical_json_bytes(data["daily"])),
        AcquisitionDataType.NEWS: ("biya_news_timing.json", canonical_json_bytes(data["news"])),
        AcquisitionDataType.CORPORATE_ACTIONS: ("biya_corporate_actions.json", canonical_json_bytes(data["corporate"])),
        AcquisitionDataType.FINRA_SHORT_SALE_VOLUME: ("biya_short_sale_volume.json", canonical_json_bytes(data["short_sale"])),
    }
    for filename, rendered in normalized_bytes.values():
        (normalized_root / filename).write_bytes(rendered)
    updated_manifests = []
    for manifest in data["manifests"]:
        normalized = normalized_bytes.get(manifest.data_type)
        if manifest.result_state is AcquisitionResultState.SUCCESS and normalized is not None:
            filename, rendered = normalized
            manifest = manifest.model_copy(update={
                "normalization_status": AcquisitionNormalizationState.SUCCESS,
                "normalized_relative_path": f"normalized/{filename}",
                "normalized_sha256": f"sha256:{hashlib.sha256(rendered).hexdigest()}",
            })
            (ACQUISITION_ROOT / "manifests" / f"{manifest.acquisition_id}.json").write_bytes(
                canonical_json_bytes(manifest))
        updated_manifests.append(manifest)
    data["manifests"] = tuple(updated_manifests)

    _jsonl(FIXTURE_ROOT / "biya_market_bars_intraday.jsonl", data["intraday"].observations)
    _jsonl(FIXTURE_ROOT / "biya_market_bars_daily.jsonl", data["daily"].observations)
    _jsonl(FIXTURE_ROOT / "biya_news.jsonl", data["news"].observations)
    _jsonl(FIXTURE_ROOT / "biya_short_sale_volume.jsonl",
           (record for collection in data["short_sale"] for record in collection.records))
    _jsonl(FIXTURE_ROOT / "biya_corporate_actions.jsonl", data["corporate"].observations)
    for name, key in (("biya_halts.jsonl", "halt_collection"),
                      ("biya_short_interest.jsonl", "short_interest_context"),
                      ("biya_borrow_history.jsonl", "borrow_fee_context")):
        _jsonl(FIXTURE_ROOT / name, (data["unavailable"][key],))
    (FIXTURE_ROOT / "biya_acquisition_manifests.json").write_bytes(canonical_json_bytes(data["manifests"]))
    (FIXTURE_ROOT / "biya_outcome_case.json").write_bytes(canonical_json_bytes(data["amendment"]))
    fixture_metadata = {
        "schema_version": "1.0.0",
        "classification": "SANITIZED_PUBLIC_HISTORICAL_DATA",
        "synthetic_edge_cases": ("partial_acquisition_manifest", "network_failure_manifest",
                                 "entitlement_failure_manifest"),
        "unavailable_domains": ("TRADING_HALTS", "PUBLISHED_SHORT_INTEREST", "DAYS_TO_COVER",
                                "BORROW_FEE", "BORROW_AVAILABILITY"),
        "prohibition": "Unavailable domains contain no invented historical values.",
    }
    (FIXTURE_ROOT / "phase_2v_outcome_fixture_metadata.json").write_bytes(
        canonical_json_bytes(fixture_metadata))
    DEMO_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_PATH.write_bytes(canonical_json_bytes(data["public"]))

    anchors = {}
    for name, value in build_anchor_results().items():
        anchors[name] = (hashlib.sha256(value).hexdigest() if isinstance(value, bytes)
                         else canonical_hash(value))
    metadata = {
        "schema_version": "1.0.0",
        "description": "Additive Phase 2V BIYA outcome amendment anchors; prior anchors are untouched.",
        "anchor_result_order": tuple(sorted(anchors)),
        "anchors": dict(sorted(anchors.items())),
    }
    (FIXTURE_ROOT / "expected_phase_2v_outcome_metadata.json").write_bytes(canonical_json_bytes(metadata))


if __name__ == "__main__":
    write_outputs()

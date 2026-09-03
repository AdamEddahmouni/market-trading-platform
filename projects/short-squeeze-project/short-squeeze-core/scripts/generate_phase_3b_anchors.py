"""Generate Phase 3B registries, research datasets, and deterministic anchors."""

import hashlib
import json
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from squeeze_core.contracts import AssetClass  # noqa: E402
from squeeze_core.acquisition.operation_readiness.evidence_inputs import FROZEN_COHORT  # noqa: E402
from squeeze_core.evaluation import (  # noqa: E402
    CandidateEvaluationResult,
    CategoryEvaluationSummary,
    RuleCategory,
    RuleEvaluationRequest,
    RuleEvaluationResult,
    RuleOutcome,
    evaluate_candidate,
)
from squeeze_core.evaluation.policies import lookup_policy  # noqa: E402
from squeeze_core.evaluation.serialization import (  # noqa: E402
    deserialize_candidate_evaluation,
    serialize_candidate_evaluation,
)
from squeeze_core.metrics import MetricName, MetricUnit  # noqa: E402
from squeeze_core.research.batch import run_research_batch  # noqa: E402
from squeeze_core.research.classification import classify_research_case  # noqa: E402
from squeeze_core.research.dataset import (  # noqa: E402
    build_research_dataset,
    filter_research_dataset,
)
from squeeze_core.research.detection import evaluate_research_detection  # noqa: E402
from squeeze_core.research.matrices import build_rule_outcome_matrix  # noqa: E402
from squeeze_core.research.models import (  # noqa: E402
    BatchEvaluationRequest,
    CandidateCaseRegistryEntry,
    CandidateCaseStatus,
    CandidateCaseType,
    FixtureClassification,
    OrderingPolicy,
    OriginalPlatformStatus,
    OutcomeCompleteness,
    ResearchCaseClassification,
    RetrospectiveOutcomeObservation,
)
from squeeze_core.research.outcomes import label_outcome  # noqa: E402
from squeeze_core.research.policies import (  # noqa: E402
    DETECTION_POLICY_VERSION,
    OUTCOME_POLICY_VERSION,
    load_detection_policy,
    load_outcome_policy,
)
from squeeze_core.research.registry import build_case_registry  # noqa: E402
from squeeze_core.research.serialization import (  # noqa: E402
    serialize_research_csv,
    serialize_research_json,
    serialize_research_jsonl,
    serialize_research_model,
)
from squeeze_core.research.summaries import (  # noqa: E402
    build_category_frequency_summary,
    build_missingness_summary,
    build_outcome_conditioned_rule_summary,
    build_rule_frequency_summary,
)
from squeeze_core.serialization import canonical_hash, canonical_json_bytes  # noqa: E402
from tests.evaluation.helpers import (  # noqa: E402
    AS_OF,
    bar,
    normalized_metric,
    short_interest,
    snapshot,
)


OUT = ROOT / "tests" / "fixtures" / "research"
EVALUATION = ROOT / "tests" / "fixtures" / "evaluation"
OUTCOME_CASE = (
    ROOT / "tests" / "fixtures" / "validation" / "outcome_amendment"
    / "biya_outcome_case.json"
)
PHASE_3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
SYNTHETIC_POLICY = lookup_policy(PHASE_3A_POLICY_VERSION)
REGISTRY_VERSION = "phase_3b_case_registry.v1"
BATCH_VERSION = "phase_3b_batch.v1"


ANCHOR_NAMES = (
    "detection_policy_detected", "detection_policy_not_detected",
    "detection_policy_unevaluable_unknown", "detection_policy_unevaluable_conflicted",
    "detection_policy_unevaluable_insufficient", "outcome_substantial_upward",
    "outcome_no_substantial_upward", "outcome_unknown", "outcome_insufficient",
    "research_true_positive", "research_false_positive", "research_true_negative",
    "research_false_negative", "research_unevaluable", "biya_earliest_research_case",
    "biya_latest_research_case", "historical_case_registry", "synthetic_case_registry",
    "complete_case_registry", "single_case_batch", "multi_case_batch",
    "rule_outcome_matrix", "rule_frequency_summary", "outcome_conditioned_rule_summary",
    "category_frequency_summary", "missingness_summary", "true_positive_dataset",
    "false_positive_dataset", "true_negative_dataset", "false_negative_dataset",
    "unevaluable_dataset", "research_dataset_json", "research_dataset_jsonl",
    "research_dataset_csv", "phase_3b_cli_output", "phase_3b_export_cli_output",
    "mixed_phase_3b_output", "serialized_phase_3b_collection",
)


def _load_evaluation(name: str) -> CandidateEvaluationResult:
    return deserialize_candidate_evaluation((EVALUATION / name).read_bytes())


def _category_summaries(results):
    summaries = []
    for category in RuleCategory:
        counts = Counter(item.outcome for item in results if item.category is category)
        summaries.append(CategoryEvaluationSummary(
            category=category,
            pass_count=counts[RuleOutcome.PASS],
            fail_count=counts[RuleOutcome.FAIL],
            unknown_count=counts[RuleOutcome.UNKNOWN],
            conflicted_count=counts[RuleOutcome.CONFLICTED],
            insufficient_data_count=counts[RuleOutcome.INSUFFICIENT_DATA],
            not_applicable_count=counts[RuleOutcome.NOT_APPLICABLE],
        ))
    return tuple(summaries)


@dataclass(frozen=True)
class SyntheticMetricSpec:
    bar_close: str | None = "8"
    include_bar: bool = True
    bar_status: str = "COMPLETED"
    percentage_return: str | None = "12"
    relative_volume: str | None = "6"
    float_shares: int | None = 10_000_000
    include_short_interest: bool = True


def _with_symbol(observation, symbol: str):
    return observation.model_copy(update={"symbol": symbol})


def _synthetic_evaluation(
    symbol: str,
    metric_spec: SyntheticMetricSpec,
    overrides: dict[str, RuleOutcome],
):
    observations: list = []
    if metric_spec.include_bar and metric_spec.bar_close is not None:
        observations.append(
            _with_symbol(
                bar(metric_spec.bar_close, status=metric_spec.bar_status),
                symbol,
            )
        )
    if metric_spec.float_shares is not None:
        observations.append(_with_symbol(snapshot(float_shares=metric_spec.float_shares), symbol))
    if metric_spec.include_short_interest:
        observations.append(_with_symbol(short_interest(), symbol))

    metrics = []
    if metric_spec.percentage_return is not None:
        metrics.append(
            normalized_metric(
                MetricName.PERCENTAGE_RETURN,
                metric_spec.percentage_return,
                MetricUnit.PERCENT,
            ).model_copy(update={"symbol": symbol})
        )
    if metric_spec.relative_volume is not None:
        metrics.append(
            normalized_metric(
                MetricName.RELATIVE_VOLUME,
                metric_spec.relative_volume,
                MetricUnit.RATIO,
            ).model_copy(update={"symbol": symbol})
        )

    request = RuleEvaluationRequest(
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        policy_version=SYNTHETIC_POLICY.policy_version,
        enabled_rule_ids=SYNTHETIC_POLICY.enabled_rule_ids,
        provider_scope=("provider-a",),
        input_observations=tuple(observations),
        input_metrics=tuple(metrics),
    )
    evaluation = evaluate_candidate(request, SYNTHETIC_POLICY)
    if not overrides:
        return evaluation

    rules = []
    for result in evaluation.rule_results:
        values = result.model_dump(exclude={"deterministic_id"})
        if result.rule_id in overrides:
            values["outcome"] = overrides[result.rule_id]
        rules.append(RuleEvaluationResult(**values))
    values = evaluation.model_dump(exclude={
        "deterministic_id", "symbol", "rule_results", "results_by_category"
    })
    return CandidateEvaluationResult(
        **values,
        symbol=symbol,
        rule_results=tuple(rules),
        results_by_category=_category_summaries(rules),
    )


def _outcome(
    case_id: str,
    symbol: str,
    boundary: datetime,
    maximum: Decimal | None,
    adverse: Decimal | None,
    completeness: OutcomeCompleteness,
    support_id: str,
    reference_price: Decimal = Decimal("4"),
):
    return RetrospectiveOutcomeObservation(
        case_id=case_id,
        symbol=symbol,
        detection_boundary=boundary,
        reference_price_policy=(
            "first_eligible_trade_bar_close_at_or_after_boundary.v1"
        ),
        reference_price=reference_price,
        horizon="24_HOURS",
        maximum_observed_move_percent=maximum,
        maximum_adverse_move_percent=adverse,
        completeness=completeness,
        supporting_observation_ids=(support_id,),
    )


def _biya_outcomes():
    document = json.loads(OUTCOME_CASE.read_text(encoding="utf-8"))
    results = {}
    for label, boundary in zip(("earliest", "latest"), document["boundary_outcomes"], strict=True):
        window = next(item for item in boundary["windows"] if item["window"] == "24_HOURS")
        case_id = f"BIYA_{label.upper()}_BOUNDARY"
        results[label] = _outcome(
            case_id,
            "BIYA",
            datetime.fromisoformat(boundary["boundary"].replace("Z", "+00:00")),
            Decimal(window["maximum_observed_return_percent"]),
            Decimal(window["maximum_adverse_move_percent"]),
            OutcomeCompleteness(window["missing_data_state"]),
            boundary["deterministic_id"],
            Decimal(boundary["reference"]["price"]),
        )
    return results


def _entry(
    case_id,
    symbol,
    case_type,
    case_status,
    platform_status,
    fixture_classification,
    *,
    as_of=None,
    evaluation_path=None,
    outcome_path=None,
    detection_id=None,
    artifacts=(),
    limitations=(),
):
    return CandidateCaseRegistryEntry(
        case_id=case_id,
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        case_type=case_type,
        case_status=case_status,
        original_platform_status=platform_status,
        detection_time_evidence_id=detection_id,
        evaluation_as_of=as_of,
        evaluation_result_path=evaluation_path,
        outcome_observation_path=outcome_path,
        original_platform_artifact_ids=artifacts,
        historical_dataset_ids=(),
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        limitations=limitations,
        fixture_classification=fixture_classification,
    )


def _pilot_cohort_entries(peer_limitations: tuple[str, ...]) -> tuple:
    """Build registry entries for IBKR pilot symbols with generated evaluation fixtures."""
    entries = []
    pilot = tuple(FROZEN_COHORT[:13]) + (("KLRS", "BATCH01_KLRS_20260718"), ("SG", "BATCH01_SG_20260718"))
    surfaced = {"LBGJ", "KLRS", "GPRE"}
    for symbol, batch_case_id in pilot:
        eval_name = f"{symbol.lower()}_boundary_evaluation.json"
        eval_path = EVALUATION / eval_name
        if not eval_path.is_file():
            continue
        evaluation = _load_evaluation(eval_name)
        platform = (
            OriginalPlatformStatus.SURFACED
            if symbol in surfaced
            else OriginalPlatformStatus.UNKNOWN
        )
        case_type = (
            CandidateCaseType.ORIGINAL_PLATFORM_SURFACED
            if symbol in surfaced
            else CandidateCaseType.ORIGINAL_PLATFORM_STATUS_UNKNOWN
        )
        extra_limitations = peer_limitations
        if symbol == "LBGJ":
            extra_limitations = peer_limitations + (
                "IBKR contract resolution verified: LI BANG INT CORP I- A (NASDAQ conId 907000939)",
            )
        entries.append(
            _entry(
                f"{symbol}_ARTIFACT_DISCOVERY",
                symbol,
                case_type,
                CandidateCaseStatus.COMPLETE,
                platform,
                FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
                as_of=evaluation.as_of,
                evaluation_path=f"../evaluation/{eval_name}",
                outcome_path=f"{symbol.lower()}_outcome_observation.json",
                detection_id=batch_case_id,
                artifacts=("archived-app-log",),
                limitations=extra_limitations,
            )
        )
    return tuple(entries)


def _historical_entries():
    earliest = _load_evaluation("biya_earliest_boundary_evaluation.json")
    latest = _load_evaluation("biya_latest_boundary_evaluation.json")
    common_limitations = (
        "original methodology remains unverified",
        "historical borrow evidence remains unavailable",
        "outcome movement does not establish short-squeeze causation",
    )
    peer_limitations = common_limitations + (
        "published short interest evidence is unavailable",
        "detection-context bars may use live IBKR historical intake when operator collection succeeds",
        "absolute price-level semantics remain blocked by Batch 07 readiness",
    )
    complete = (
        _entry(
            "BIYA_EARLIEST_BOUNDARY", "BIYA", CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
            CandidateCaseStatus.COMPLETE, OriginalPlatformStatus.SURFACED,
            FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
            as_of=earliest.as_of,
            evaluation_path="../evaluation/biya_earliest_boundary_evaluation.json",
            outcome_path="biya_earliest_outcome_observation.json",
            detection_id="phase-2v-biya-earliest-boundary",
            artifacts=("archived-app-log", "advisor-meeting-2026-07-17"),
            limitations=common_limitations + (
                "published short interest publication timestamps are date-only uncertain",
            ),
        ),
        _entry(
            "BIYA_LATEST_BOUNDARY", "BIYA", CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
            CandidateCaseStatus.COMPLETE, OriginalPlatformStatus.SURFACED,
            FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
            as_of=latest.as_of,
            evaluation_path="../evaluation/biya_latest_boundary_evaluation.json",
            outcome_path="biya_latest_outcome_observation.json",
            detection_id="phase-2v-biya-latest-boundary",
            artifacts=("archived-app-log", "advisor-meeting-2026-07-17"),
            limitations=common_limitations + (
                "published short interest publication timestamps are date-only uncertain",
            ),
        ),
    ) + _pilot_cohort_entries(peer_limitations)
    discovered = (
        ("KLOS_IDENTITY_CONFLICT", "KLOS", CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
         CandidateCaseStatus.BLOCKED_CONFLICTING_IDENTITY, OriginalPlatformStatus.SURFACED,
         ("advisor-meeting-2026-07-17", "reconstruction-timeline")),
    )
    incomplete = tuple(_entry(
        case_id, symbol, case_type, status, platform, FixtureClassification.SANITIZED_LOCAL_ARTIFACT,
        artifacts=artifacts,
        limitations=(
            "no defensible complete detection snapshot survives",
            "Phase 3A evaluation inputs are unavailable",
            "24-hour outcome observation is unavailable",
        ),
    ) for case_id, symbol, case_type, status, platform, artifacts in discovered)
    return complete + incomplete


_SYNTHETIC = (
    ("SYN_TRUE_POSITIVE", "SYNTP", {}, SyntheticMetricSpec(), Decimal("25"), Decimal("-4"), OutcomeCompleteness.PARTIAL, OriginalPlatformStatus.NOT_SURFACED),
    ("SYN_FALSE_POSITIVE", "SYNFP", {}, SyntheticMetricSpec(percentage_return="3"), Decimal("4"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.SURFACED),
    ("SYN_FALSE_NEGATIVE", "SYNFN", {}, SyntheticMetricSpec(bar_close="25"), Decimal("25"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.SURFACED),
    ("SYN_TRUE_NEGATIVE", "SYNTN", {}, SyntheticMetricSpec(bar_close="25"), Decimal("4"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.NOT_SURFACED),
    ("SYN_UNEVALUABLE_UNKNOWN", "SYNUNK", {}, SyntheticMetricSpec(include_bar=False), Decimal("25"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.UNKNOWN),
    ("SYN_UNEVALUABLE_CONFLICTED", "SYNCFL", {"PRICE_RANGE": RuleOutcome.CONFLICTED}, SyntheticMetricSpec(), Decimal("25"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.UNKNOWN),
    ("SYN_UNEVALUABLE_INSUFFICIENT", "SYNINS", {"PRICE_RANGE": RuleOutcome.INSUFFICIENT_DATA}, SyntheticMetricSpec(), Decimal("25"), Decimal("-4"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.UNKNOWN),
    ("SYN_OUTCOME_UNKNOWN", "SYNOUNK", {}, SyntheticMetricSpec(), None, None, OutcomeCompleteness.UNAVAILABLE, OriginalPlatformStatus.UNKNOWN),
    ("SYN_OUTCOME_INSUFFICIENT", "SYNOINS", {}, SyntheticMetricSpec(), Decimal("4"), Decimal("-4"), OutcomeCompleteness.PARTIAL, OriginalPlatformStatus.UNKNOWN),
    ("SYN_MIXED_VOLATILE", "SYNMIX", {}, SyntheticMetricSpec(), Decimal("25"), Decimal("-25"), OutcomeCompleteness.PARTIAL, OriginalPlatformStatus.UNKNOWN),
    ("SYN_SUBSTANTIAL_DOWNWARD", "SYNDOWN", {}, SyntheticMetricSpec(percentage_return="3"), Decimal("4"), Decimal("-25"), OutcomeCompleteness.COMPLETE, OriginalPlatformStatus.UNKNOWN),
)


def _write_source_fixtures():
    OUT.mkdir(parents=True, exist_ok=True)
    biya = _biya_outcomes()
    for label, observation in biya.items():
        (OUT / f"biya_{label}_outcome_observation.json").write_bytes(
            serialize_research_model(observation)
        )

    synthetic_entries = []
    for case_id, symbol, overrides, metric_spec, maximum, adverse, completeness, platform in _SYNTHETIC:
        evaluation = _synthetic_evaluation(symbol, metric_spec, overrides)
        evaluation_name = f"{case_id.lower()}_evaluation.json"
        outcome_name = f"{case_id.lower()}_outcome.json"
        (OUT / evaluation_name).write_bytes(serialize_candidate_evaluation(evaluation))
        observation = _outcome(
            case_id, symbol, evaluation.as_of, maximum, adverse, completeness,
            f"{case_id.lower()}-observation",
        )
        (OUT / outcome_name).write_bytes(serialize_research_model(observation))
        case_type = CandidateCaseType.SYNTHETIC_EDGE_CASE
        synthetic_entries.append(_entry(
            case_id, symbol, case_type, CandidateCaseStatus.COMPLETE, platform,
            FixtureClassification.SYNTHETIC_EDGE_CASE,
            as_of=evaluation.as_of,
            evaluation_path=evaluation_name,
            outcome_path=outcome_name,
            detection_id=f"{case_id.lower()}-detection",
            limitations=("synthetic edge case; not historical evidence",),
        ))

    historical = _historical_entries()
    all_entries = historical + tuple(synthetic_entries)
    registry = build_case_registry(REGISTRY_VERSION, all_entries)
    (OUT / "phase_3b_case_registry.json").write_bytes(serialize_research_model(registry))
    (OUT / "phase_3b_historical_cases.json").write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0", "cases": historical,
    }))
    (OUT / "phase_3b_synthetic_cases.json").write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0", "cases": tuple(synthetic_entries),
    }))
    policy_dir = ROOT / "src" / "squeeze_core" / "research" / "policies"
    shutil.copyfile(
        policy_dir / "phase_3b_research_detection_policy_v1.json",
        OUT / "phase_3b_detection_policy.json",
    )
    shutil.copyfile(
        policy_dir / "phase_3b_outcome_label_policy_v1.json",
        OUT / "phase_3b_outcome_policy.json",
    )
    return registry, historical, tuple(synthetic_entries)


def _request(case_ids, *, ordering=OrderingPolicy.REQUEST_ORDER):
    return BatchEvaluationRequest(
        batch_version=BATCH_VERSION,
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_POLICY_VERSION,
        case_ids=tuple(case_ids),
        case_registry_version=REGISTRY_VERSION,
        ordering_policy=ordering,
    )


def build_anchor_results():
    registry, historical, synthetic = _write_source_fixtures()
    complete_ids = tuple(
        item.case_id for item in registry.entries if item.case_status is CandidateCaseStatus.COMPLETE
    )
    historical_complete_ids = ("BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY")
    single = run_research_batch(_request(("BIYA_EARLIEST_BOUNDARY",)), OUT / "phase_3b_case_registry.json")
    multi = run_research_batch(_request(complete_ids, ordering=OrderingPolicy.CANONICAL_CASE_ID), OUT / "phase_3b_case_registry.json")
    dataset = build_research_dataset(multi)
    cases = {item.case_id: item for item in multi.case_results}

    detection_policy = load_detection_policy(DETECTION_POLICY_VERSION)
    outcome_policy = load_outcome_policy(OUTCOME_POLICY_VERSION)
    synthetic_evaluations = {
        item.case_id: deserialize_candidate_evaluation((OUT / item.evaluation_result_path).read_bytes())
        for item in synthetic
    }
    synthetic_outcomes = {
        item.case_id: RetrospectiveOutcomeObservation.model_validate_json(
            (OUT / item.outcome_observation_path).read_bytes()
        ) for item in synthetic
    }
    detections = {
        case_id: evaluate_research_detection(value, detection_policy)
        for case_id, value in synthetic_evaluations.items()
    }
    labels = {
        case_id: label_outcome(value, outcome_policy)
        for case_id, value in synthetic_outcomes.items()
    }
    classifications = {
        case_id: classify_research_case(
            case_id, detections[case_id].status, labels[case_id].label,
            str(detections[case_id].deterministic_id), str(labels[case_id].deterministic_id),
        ) for case_id in detections
    }
    historical_registry = build_case_registry(REGISTRY_VERSION, historical)
    synthetic_registry = build_case_registry(REGISTRY_VERSION, synthetic)
    complete_registry = build_case_registry(
        REGISTRY_VERSION,
        tuple(item for item in registry.entries if item.case_status is CandidateCaseStatus.COMPLETE),
    )
    matrix = build_rule_outcome_matrix(multi)
    frequencies = build_rule_frequency_summary(multi)
    conditioned = build_outcome_conditioned_rule_summary(multi)
    categories = build_category_frequency_summary(multi)
    missingness = build_missingness_summary(multi)
    filtered = {
        classification: filter_research_dataset(dataset, classification)
        for classification in ResearchCaseClassification
    }
    results = {
        "detection_policy_detected": detections["SYN_TRUE_POSITIVE"],
        "detection_policy_not_detected": detections["SYN_FALSE_NEGATIVE"],
        "detection_policy_unevaluable_unknown": detections["SYN_UNEVALUABLE_UNKNOWN"],
        "detection_policy_unevaluable_conflicted": detections["SYN_UNEVALUABLE_CONFLICTED"],
        "detection_policy_unevaluable_insufficient": detections["SYN_UNEVALUABLE_INSUFFICIENT"],
        "outcome_substantial_upward": labels["SYN_TRUE_POSITIVE"],
        "outcome_no_substantial_upward": labels["SYN_FALSE_POSITIVE"],
        "outcome_unknown": labels["SYN_OUTCOME_UNKNOWN"],
        "outcome_insufficient": labels["SYN_OUTCOME_INSUFFICIENT"],
        "research_true_positive": classifications["SYN_TRUE_POSITIVE"],
        "research_false_positive": classifications["SYN_FALSE_POSITIVE"],
        "research_true_negative": classifications["SYN_TRUE_NEGATIVE"],
        "research_false_negative": classifications["SYN_FALSE_NEGATIVE"],
        "research_unevaluable": classifications["SYN_UNEVALUABLE_UNKNOWN"],
        "biya_earliest_research_case": cases["BIYA_EARLIEST_BOUNDARY"],
        "biya_latest_research_case": cases["BIYA_LATEST_BOUNDARY"],
        "historical_case_registry": historical_registry,
        "synthetic_case_registry": synthetic_registry,
        "complete_case_registry": complete_registry,
        "single_case_batch": single,
        "multi_case_batch": multi,
        "rule_outcome_matrix": matrix,
        "rule_frequency_summary": frequencies,
        "outcome_conditioned_rule_summary": conditioned,
        "category_frequency_summary": categories,
        "missingness_summary": missingness,
        "true_positive_dataset": filtered[ResearchCaseClassification.TRUE_POSITIVE],
        "false_positive_dataset": filtered[ResearchCaseClassification.FALSE_POSITIVE],
        "true_negative_dataset": filtered[ResearchCaseClassification.TRUE_NEGATIVE],
        "false_negative_dataset": filtered[ResearchCaseClassification.FALSE_NEGATIVE],
        "unevaluable_dataset": filtered[ResearchCaseClassification.UNEVALUABLE],
        "research_dataset_json": serialize_research_json(dataset),
        "research_dataset_jsonl": serialize_research_jsonl(dataset),
        "research_dataset_csv": serialize_research_csv(dataset),
        "phase_3b_cli_output": serialize_research_model(multi),
        "phase_3b_export_cli_output": serialize_research_jsonl(dataset),
    }
    results["mixed_phase_3b_output"] = tuple(
        anchor_hash(results[name]) for name in sorted(results)
    )
    results["serialized_phase_3b_collection"] = canonical_json_bytes(
        [anchor_hash(results[name]) for name in sorted(results)]
    )
    assert tuple(results) == ANCHOR_NAMES
    return results


def anchor_hash(value):
    return hashlib.sha256(value).hexdigest() if isinstance(value, bytes) else canonical_hash(value)


def generate():
    results = build_anchor_results()
    matrix = results["rule_outcome_matrix"]
    dataset_json = results["research_dataset_json"]
    dataset_jsonl = results["research_dataset_jsonl"]
    dataset_csv = results["research_dataset_csv"]
    (OUT / "phase_3b_rule_outcome_matrix.json").write_bytes(serialize_research_model(matrix))
    (OUT / "phase_3b_research_dataset.json").write_bytes(dataset_json)
    (OUT / "phase_3b_research_dataset.jsonl").write_bytes(dataset_jsonl)
    (OUT / "phase_3b_research_dataset.csv").write_bytes(dataset_csv)
    for name, filename in (
        ("false_positive_dataset", "phase_3b_false_positive_cases.json"),
        ("false_negative_dataset", "phase_3b_false_negative_cases.json"),
    ):
        (OUT / filename).write_bytes(serialize_research_json(results[name]))
    (OUT / "phase_3b_batch.json").write_bytes(serialize_research_model(results["multi_case_batch"]))
    metadata = {
        "schema_version": "1.0.0",
        "phase_3a_policy_version": PHASE_3A_POLICY_VERSION,
        "detection_policy_version": DETECTION_POLICY_VERSION,
        "outcome_policy_version": OUTCOME_POLICY_VERSION,
        "hash_algorithm": "sha256-canonical-json-or-raw-bytes",
        "anchors": {name: anchor_hash(results[name]) for name in ANCHOR_NAMES},
    }
    (OUT / "expected_phase_3b_research_metadata.json").write_bytes(canonical_json_bytes(metadata))
    files = tuple(sorted(path.name for path in OUT.iterdir() if path.is_file()))
    fixture_metadata = {
        "schema_version": "1.0.0",
        "files": files,
        "classifications": {
            name: (
                "SYNTHETIC_EDGE_CASE"
                if name.startswith("syn_") or name == "phase_3b_synthetic_cases.json"
                else "SANITIZED_PUBLIC_HISTORICAL_DATA"
                if name.startswith("biya_")
                else "SANITIZED_LOCAL_ARTIFACT"
                if name in {
                    "expected_phase_3b_research_metadata.json",
                    "phase_3b_detection_policy.json",
                    "phase_3b_outcome_policy.json",
                    "phase_3b_fixture_metadata.json",
                }
                else "MIXED_PROVENANCE"
            ) for name in files
        },
        "synthetic_cases_are_historical": False,
    }
    (OUT / "phase_3b_fixture_metadata.json").write_bytes(
        canonical_json_bytes(fixture_metadata)
    )
    return metadata


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True, separators=(",", ":")))

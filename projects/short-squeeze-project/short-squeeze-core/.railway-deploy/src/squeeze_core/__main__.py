import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_record
from squeeze_core.adapters.finviz import normalize_finviz_snapshot_record
from squeeze_core.adapters.finra import normalize_finra_short_interest_record
from squeeze_core.adapters.sec import normalize_sec_filing_record
from squeeze_core.adapters.halts import normalize_trading_halt_record
from squeeze_core.adapters.news import normalize_news_record
from squeeze_core.adapters.market_bars import (
    BarInterval,
    BarSession,
    normalize_market_bar_record,
)
from squeeze_core.adapters.trades_quotes import normalize_trade_quote_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.metrics import build_metric_results
from squeeze_core.evidence import (
    BarSeriesPolicy,
    PointInTimeEvidencePolicy,
    build_bar_series,
    build_point_in_time_evidence,
    TradeQuoteSeriesPolicy,
    build_trade_quote_series,
)
from squeeze_core.readiness import (
    build_conflict_summary,
    build_domain_coverage_snapshot,
    build_evidence_age_alignment,
    build_evidence_readiness_snapshot,
    build_input_sufficiency_result,
    build_missingness_summary,
    build_reporting_period_alignment,
)
from squeeze_core.readiness.reporting_alignment import REPORTING_PERIOD_FIELDS
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="squeeze-core")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("fixture", type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("fixture", type=Path)
    replay.add_argument("--mode", choices=("strict", "normalized"), default="strict")
    normalize = commands.add_parser("normalize-provider")
    normalize.add_argument(
        "--provider", choices=("ibkr", "finviz", "finra", "sec", "halts", "news", "market-bars", "trades-quotes"), required=True
    )
    normalize.add_argument("--input", type=Path, required=True)
    normalize.add_argument("--context", type=Path, required=True)
    normalize.add_argument("--case")
    evidence = commands.add_parser("build-evidence")
    evidence.add_argument("--input", type=Path, required=True)
    evidence.add_argument("--symbol", required=True)
    evidence.add_argument("--as-of", required=True)
    evidence.add_argument("--policy", type=Path)
    timeline = commands.add_parser("build-evidence-timeline")
    timeline.add_argument("--input", type=Path, required=True)
    timeline.add_argument("--symbol", required=True)
    timeline.add_argument("--as-of-file", type=Path, required=True)
    timeline.add_argument("--policy", type=Path)
    halt_state = commands.add_parser("build-halt-state")
    halt_state.add_argument("--input", type=Path, required=True)
    halt_state.add_argument("--symbol", required=True)
    halt_state.add_argument("--as-of", required=True)
    bar_series = commands.add_parser("build-bar-series")
    bar_series.add_argument("--input", type=Path, required=True)
    bar_series.add_argument("--symbol", required=True)
    bar_series.add_argument("--interval", choices=tuple(item.value for item in BarInterval), required=True)
    bar_series.add_argument("--as-of", required=True)
    bar_series.add_argument("--session", action="append", choices=tuple(item.value for item in BarSession), default=[])
    market_metrics = commands.add_parser("build-market-metrics")
    market_metrics.add_argument("--input", type=Path, required=True)
    market_metrics.add_argument("--symbol", required=True)
    market_metrics.add_argument("--as-of", required=True)
    market_metrics.add_argument("--spec", type=Path, required=True)
    readiness = commands.add_parser("build-evidence-readiness")
    readiness.add_argument("--input", type=Path, required=True)
    readiness.add_argument("--symbol", required=True)
    readiness.add_argument("--as-of", required=True)
    readiness.add_argument("--operation", required=True)
    readiness.add_argument("--policy-version")
    readiness.add_argument("--policy", type=Path)
    trade_quote_series = commands.add_parser("build-trade-quote-series")
    trade_quote_series.add_argument("--input", type=Path, required=True)
    trade_quote_series.add_argument("--symbol", required=True)
    trade_quote_series.add_argument("--as-of", required=True)
    trade_quote_series.add_argument("--provider", action="append", default=[])
    trade_quote_series.add_argument("--venue", action="append", default=[])
    trade_quote_series.add_argument(
        "--market-scope",
        action="append",
        choices=("VENUE", "NBBO", "CONSOLIDATED", "PROVIDER_AGGREGATED", "UNKNOWN"),
        default=[],
    )
    candidate_validation = commands.add_parser("build-candidate-validation")
    candidate_validation.add_argument("--case-spec", type=Path, required=True)
    candidate_validation.add_argument("--evidence", type=Path)
    candidate_validation.add_argument("--output", type=Path)
    validation_demo = commands.add_parser("export-validation-demo")
    validation_demo.add_argument("--validation-case", type=Path, required=True)
    validation_demo.add_argument("--output", type=Path)
    outcome_normalize = commands.add_parser("normalize-biya-history")
    outcome_normalize.add_argument("--manifest", type=Path, required=True)
    outcome_normalize.add_argument("--raw", type=Path, required=True)
    outcome_normalize.add_argument("--output", type=Path, required=True)
    outcome_build = commands.add_parser("build-biya-outcome-amendment")
    outcome_build.add_argument("--validation-case", type=Path, required=True)
    outcome_build.add_argument("--market-data", type=Path, required=True)
    outcome_build.add_argument("--output", type=Path, required=True)
    candidate_evaluation = commands.add_parser("build-candidate-evaluation")
    candidate_evaluation.add_argument("--policy", type=Path, required=True)
    candidate_evaluation.add_argument("--evidence", type=Path, required=True)
    candidate_evaluation.add_argument("--symbol", required=True)
    candidate_evaluation.add_argument("--as-of", required=True)
    candidate_evaluation.add_argument("--asset-class", default="EQUITY")
    candidate_evaluation.add_argument("--rule", action="append", default=[])
    candidate_evaluation.add_argument("--provider", action="append", default=[])
    candidate_evaluation.add_argument("--output", type=Path, required=True)
    research_batch = commands.add_parser("build-research-evaluation-batch")
    research_batch.add_argument("--case-registry", type=Path, required=True)
    research_batch.add_argument("--case-id", action="append", required=True)
    research_batch.add_argument("--phase-3a-policy", required=True)
    research_batch.add_argument("--detection-policy", required=True)
    research_batch.add_argument("--outcome-policy", required=True)
    research_batch.add_argument("--canonical-order", action="store_true")
    research_batch.add_argument("--fail-fast", action="store_true")
    research_batch.add_argument("--output", type=Path, required=True)
    research_export = commands.add_parser("export-research-dataset")
    research_export.add_argument("--batch", type=Path, required=True)
    research_export.add_argument("--format", choices=("json", "jsonl", "csv"), required=True)
    research_export.add_argument("--output", type=Path, required=True)
    research_analysis = commands.add_parser("analyze-research-dataset")
    research_analysis.add_argument("--dataset", type=Path)
    research_analysis.add_argument("--case-registry", type=Path)
    research_analysis.add_argument(
        "--cohort",
        choices=(
            "historical-complete",
            "synthetic",
            "all-registered",
            "partial-blocked",
            "mixed-provenance",
        ),
        required=True,
    )
    research_analysis.add_argument(
        "--analysis-unit",
        choices=(
            "case-boundary",
            "unique-symbol",
            "unique-symbol-policy-selected-boundary",
        ),
        required=True,
    )
    research_analysis.add_argument("--boundary-policy", required=True)
    research_analysis.add_argument("--statistics-policy", required=True)
    research_analysis.add_argument("--interval-policy", required=True)
    research_analysis.add_argument("--confidence-level", required=True)
    research_analysis.add_argument("--sample-size-policy", required=True)
    research_analysis.add_argument("--output", type=Path, required=True)
    research_report = commands.add_parser("render-research-analysis-report")
    research_report.add_argument("--analysis", type=Path, required=True)
    research_report.add_argument("--format", choices=("markdown",), required=True)
    research_report.add_argument("--output", type=Path, required=True)
    acquisition_plan = commands.add_parser("validate-acquisition-plan")
    acquisition_plan.add_argument("--plan", type=Path, required=True)
    acquisition_curate = commands.add_parser("curate-historical-cases")
    acquisition_curate.add_argument("--plan", type=Path, required=True)
    acquisition_curate.add_argument("--source-manifest", type=Path, required=True)
    acquisition_curate.add_argument("--artifact-manifest", type=Path, required=True)
    acquisition_curate.add_argument("--output", type=Path, required=True)
    acquisition_audit = commands.add_parser("audit-outcome-leakage")
    acquisition_audit.add_argument("--batch", type=Path, required=True)
    acquisition_audit.add_argument("--output", type=Path, required=True)
    acquisition_report = commands.add_parser("render-acquisition-report")
    acquisition_report.add_argument("--batch", type=Path, required=True)
    acquisition_report.add_argument("--format", choices=("markdown",), required=True)
    acquisition_report.add_argument("--output", type=Path, required=True)
    intake_validate = commands.add_parser("intake-validate-bundle")
    intake_validate.add_argument("--root", type=Path, required=True)
    intake_validate.add_argument("--manifest", type=Path, required=True)
    intake_inspect = commands.add_parser("intake-inspect-artifact")
    intake_inspect.add_argument("--root", type=Path, required=True)
    intake_inspect.add_argument("--manifest", type=Path, required=True)
    intake_normalize = commands.add_parser("intake-normalize-bars")
    intake_normalize.add_argument("--root", type=Path, required=True)
    intake_normalize.add_argument("--manifest", type=Path, required=True)
    intake_normalize.add_argument("--profile", type=Path, required=True)
    intake_normalize.add_argument("--output", type=Path)
    intake_summary = commands.add_parser("intake-summary")
    intake_summary.add_argument("--root", type=Path, required=True)
    intake_summary.add_argument("--manifest", type=Path, required=True)
    intake_summary.add_argument("--profile", type=Path, required=True)
    intake_summary.add_argument("--output", type=Path)
    intake_case = commands.add_parser("intake-validate-case-association")
    intake_case.add_argument("--mapping", type=Path, required=True)
    intake_case.add_argument("--manifest", type=Path)
    intake_case.add_argument("--known-case-id", action="append", default=[])
    intake_case.add_argument("--known-boundary-id", action="append", default=[])
    kit_generate = commands.add_parser("submission-kit-generate")
    kit_generate.add_argument("--output-dir", type=Path)
    kit_generate.add_argument("--fixtures-dir", type=Path)
    bar_hash = commands.add_parser("historical-bar-hash")
    bar_hash.add_argument("--file", type=Path, required=True)
    preflight = commands.add_parser("historical-bar-preflight")
    preflight.add_argument("--root", type=Path, required=True)
    preflight.add_argument("--manifest", type=Path, required=True)
    preflight.add_argument("--profile", type=Path, required=True)
    preflight.add_argument("--output", type=Path)
    preflight_report = commands.add_parser("historical-bar-preflight-report")
    preflight_report.add_argument("--root", type=Path, required=True)
    preflight_report.add_argument("--manifest", type=Path, required=True)
    preflight_report.add_argument("--profile", type=Path, required=True)
    preflight_report.add_argument("--output", type=Path, required=True)
    return parser


def _load_provider_record(path: Path, fixture_id: str | None) -> object:
    document = json.loads(path.read_text(encoding="utf-8"))
    if fixture_id is not None:
        cases = document.get("cases") if isinstance(document, dict) else None
        if not isinstance(cases, list):
            raise ValueError("--case requires an input document containing a cases list")
        matches = [
            case
            for case in cases
            if case.get("metadata", {}).get("fixture_id") == fixture_id
            or case.get("fixture_id") == fixture_id
        ]
        if len(matches) != 1:
            raise ValueError(f"fixture case not found or ambiguous: {fixture_id}")
        return matches[0]["record"]
    if isinstance(document, dict) and "record" in document:
        return document["record"]
    return document


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-acquisition-plan":
            from squeeze_core.acquisition.serialization import (
                deserialize_acquisition_plan, serialize_acquisition_model,
            )

            plan = deserialize_acquisition_plan(args.plan.read_bytes())
            print(serialize_acquisition_model(plan).decode("utf-8"))
            return 0

        if args.command == "curate-historical-cases":
            from squeeze_core.acquisition.runner import curate_historical_cases
            from squeeze_core.acquisition.serialization import (
                deserialize_acquisition_plan, deserialize_artifact_manifest,
                deserialize_source_manifest, serialize_acquisition_model,
            )

            batch = curate_historical_cases(
                deserialize_acquisition_plan(args.plan.read_bytes()),
                deserialize_source_manifest(args.source_manifest.read_bytes()),
                deserialize_artifact_manifest(args.artifact_manifest.read_bytes()),
            )
            rendered = serialize_acquisition_model(batch)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "audit-outcome-leakage":
            from squeeze_core.acquisition.runner import audit_batch_outcome_leakage
            from squeeze_core.acquisition.serialization import (
                deserialize_acquisition_batch, serialize_acquisition_model,
            )

            collection = audit_batch_outcome_leakage(
                deserialize_acquisition_batch(args.batch.read_bytes())
            )
            rendered = serialize_acquisition_model(collection)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            failed = any(not item.passed for item in collection.audits)
            print(rendered.decode("utf-8"), file=sys.stderr if failed else sys.stdout)
            return 1 if failed else 0

        if args.command == "render-acquisition-report":
            from squeeze_core.acquisition.reports import render_acquisition_report
            from squeeze_core.acquisition.serialization import deserialize_acquisition_batch

            rendered = render_acquisition_report(
                deserialize_acquisition_batch(args.batch.read_bytes())
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"), end="")
            return 0

        if args.command in {
            "intake-validate-bundle", "intake-inspect-artifact",
            "intake-normalize-bars", "intake-summary",
            "intake-validate-case-association",
        }:
            from squeeze_core.acquisition.local_bar_intake import (
                CaseAssociationMapping, ColumnMappingProfile, IntakeManifest,
                build_intake_summary, inspect_artifact, normalize_bundle,
                serialize_bars_csv, serialize_bars_jsonl, validate_case_association,
                validate_raw_artifact,
            )
            from squeeze_core.acquisition.local_bar_intake.semantics import (
                IntakeValidationStatus,
            )

            if args.command == "intake-validate-case-association":
                mapping = CaseAssociationMapping.model_validate_json(
                    args.mapping.read_text(encoding="utf-8")
                )
                manifest = (
                    IntakeManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
                    if args.manifest is not None else None
                )
                result = validate_case_association(
                    mapping,
                    known_case_ids=frozenset(args.known_case_id),
                    known_boundary_ids=frozenset(args.known_boundary_id),
                    manifest=manifest,
                )
                rendered = canonical_json_bytes(result)
                print(rendered.decode("utf-8"), file=sys.stdout if result.valid else sys.stderr)
                return 0 if result.valid else 1

            manifest = IntakeManifest.model_validate_json(
                args.manifest.read_text(encoding="utf-8")
            )
            if args.command == "intake-inspect-artifact":
                print(canonical_json_bytes(inspect_artifact(args.root, manifest)).decode("utf-8"))
                return 0
            if args.command == "intake-validate-bundle":
                report = validate_raw_artifact(args.root, manifest)
                accepted = report.status is IntakeValidationStatus.ACCEPTED
                rendered = canonical_json_bytes(report)
                print(rendered.decode("utf-8"), file=sys.stdout if accepted else sys.stderr)
                return 0 if accepted else 1

            profile = ColumnMappingProfile.model_validate_json(
                args.profile.read_text(encoding="utf-8")
            )
            report = validate_raw_artifact(args.root, manifest)
            outcome = normalize_bundle(args.root, manifest, profile)
            if args.command == "intake-summary":
                summary = build_intake_summary(
                    manifest, report, outcome.diagnostics, outcome.bar_set
                )
                rendered = canonical_json_bytes(summary)
                if args.output is not None:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_bytes(rendered + b"\n")
                print(rendered.decode("utf-8"))
                return 0

            rendered = canonical_json_bytes(outcome.diagnostics)
            if args.output is not None:
                args.output.mkdir(parents=True, exist_ok=True)
                (args.output / "normalization-diagnostics.json").write_bytes(rendered + b"\n")
                if outcome.bar_set is not None:
                    (args.output / "normalized-bars.jsonl").write_bytes(
                        serialize_bars_jsonl(outcome.bar_set)
                    )
                    (args.output / "normalized-bars.csv").write_bytes(
                        serialize_bars_csv(outcome.bar_set)
                    )
            rejected = outcome.diagnostics.status is IntakeValidationStatus.REJECTED
            print(rendered.decode("utf-8"), file=sys.stderr if rejected else sys.stdout)
            return 0 if not rejected else 1

        if args.command == "submission-kit-generate":
            from squeeze_core.acquisition.historical_data_submission_kit.kit import (
                KIT_ROOT, build_batch04_fixtures, build_submission_kit,
            )

            repo_root = Path(__file__).resolve().parents[2]
            output_dir = args.output_dir or (repo_root / KIT_ROOT)
            fixtures_dir = args.fixtures_dir or (
                repo_root / "tests" / "fixtures" / "acquisition" / "batch04"
            )
            written = 0
            for name, content in build_submission_kit().items():
                target = output_dir.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                written += 1
            for name, content in build_batch04_fixtures().items():
                target = fixtures_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                written += 1
            print(canonical_json_bytes({
                "command": args.command,
                "kit_files_and_fixtures_written": written,
            }).decode("utf-8"))
            return 0

        if args.command == "historical-bar-hash":
            from squeeze_core.acquisition.historical_data_submission_kit.preflight import (
                hash_file,
            )

            print(canonical_json_bytes(hash_file(args.file)).decode("utf-8"))
            return 0

        if args.command in {"historical-bar-preflight", "historical-bar-preflight-report"}:
            from squeeze_core.acquisition.historical_data_submission_kit.preflight import (
                PreflightStatus, run_preflight,
            )
            from squeeze_core.acquisition.local_bar_intake import (
                ColumnMappingProfile, IntakeManifest,
            )

            manifest = IntakeManifest.model_validate_json(
                args.manifest.read_text(encoding="utf-8")
            )
            profile = ColumnMappingProfile.model_validate_json(
                args.profile.read_text(encoding="utf-8")
            )
            report = run_preflight(args.root, manifest, profile)
            rendered = canonical_json_bytes(report)
            ready = report.status is PreflightStatus.READY_FOR_FUTURE_ASSOCIATION
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(rendered + b"\n")
            if args.command == "historical-bar-preflight-report":
                print(rendered.decode("utf-8"))
                return 0
            print(rendered.decode("utf-8"), file=sys.stdout if ready else sys.stderr)
            return 0 if ready else 1

        if args.command == "analyze-research-dataset":
            from decimal import Decimal

            from squeeze_core.analysis.models import (
                AnalysisCohortDefinition,
                AnalysisCohortType,
                AnalysisProvenanceClassification,
                AnalysisUnit,
                BoundarySelectionPolicy,
                ResearchAnalysisRequest,
            )
            from squeeze_core.analysis.policies import (
                load_interval_policy,
                load_sample_size_policy,
                load_statistics_policy,
            )
            from squeeze_core.analysis.runner import run_research_analysis
            from squeeze_core.analysis.serialization import serialize_analysis_model
            from squeeze_core.research.models import CandidateCaseRegistry
            from squeeze_core.research.serialization import deserialize_research_dataset

            cohort_type = {
                "historical-complete": AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
                "synthetic": AnalysisCohortType.SYNTHETIC_CASES,
                "all-registered": AnalysisCohortType.ALL_REGISTERED_CASES,
                "partial-blocked": AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
                "mixed-provenance": AnalysisCohortType.MIXED_PROVENANCE_CASES,
            }[args.cohort]
            analysis_unit = {
                "case-boundary": AnalysisUnit.CASE_BOUNDARY,
                "unique-symbol": AnalysisUnit.UNIQUE_SYMBOL,
                "unique-symbol-policy-selected-boundary": (
                    AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
                ),
            }[args.analysis_unit]
            boundary_policy = BoundarySelectionPolicy(args.boundary_policy)
            statistics_policy = load_statistics_policy(args.statistics_policy)
            interval_policy = load_interval_policy(args.interval_policy)
            sample_size_policy = load_sample_size_policy(args.sample_size_policy)
            confidence_level = Decimal(args.confidence_level)
            if confidence_level != interval_policy.confidence_level:
                raise ValueError(
                    "ANALYSIS_INTERVAL_CONFIDENCE_UNSUPPORTED:"
                    f"{args.confidence_level}"
                )

            dataset = (
                deserialize_research_dataset(args.dataset.read_bytes())
                if args.dataset is not None else None
            )
            registry = (
                CandidateCaseRegistry.model_validate_json(
                    args.case_registry.read_text(encoding="utf-8")
                )
                if args.case_registry is not None else None
            )
            if cohort_type in {
                AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
                AnalysisCohortType.SYNTHETIC_CASES,
                AnalysisCohortType.MIXED_PROVENANCE_CASES,
            } and dataset is None:
                raise ValueError("ANALYSIS_SOURCE_DATASET_REQUIRED")
            if cohort_type in {
                AnalysisCohortType.ALL_REGISTERED_CASES,
                AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
            } and registry is None:
                raise ValueError("ANALYSIS_SOURCE_REGISTRY_REQUIRED")

            provenance = {
                AnalysisCohortType.HISTORICAL_COMPLETED_CASES: (
                    AnalysisProvenanceClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
                ),
                AnalysisCohortType.SYNTHETIC_CASES: (
                    AnalysisProvenanceClassification.SYNTHETIC_EDGE_CASE,
                ),
                AnalysisCohortType.ALL_REGISTERED_CASES: (
                    AnalysisProvenanceClassification.MIXED_PROVENANCE,
                ),
                AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES: (
                    AnalysisProvenanceClassification.SANITIZED_LOCAL_ARTIFACT,
                ),
                AnalysisCohortType.MIXED_PROVENANCE_CASES: (
                    AnalysisProvenanceClassification.MIXED_PROVENANCE,
                ),
            }[cohort_type]
            dataset_statistics = (
                "CONFUSION_MATRIX",
                "DETECTION_PREVALENCE",
                "MISSINGNESS",
                "OUTCOME_PREVALENCE",
                "RESEARCH_CLASSIFICATION_PREVALENCE",
                "RULE_OUTCOME_PREVALENCE",
            )
            included_statistics = (
                ("DATA_QUALITY",)
                if cohort_type in {
                    AnalysisCohortType.ALL_REGISTERED_CASES,
                    AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
                }
                else dataset_statistics
            )
            definition = AnalysisCohortDefinition(
                cohort_type=cohort_type,
                analysis_unit=analysis_unit,
                boundary_selection_policy_version=boundary_policy,
                provenance_classifications=provenance,
                required_complete_cases=cohort_type in {
                    AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
                    AnalysisCohortType.SYNTHETIC_CASES,
                },
            )
            request = ResearchAnalysisRequest(
                source_dataset_id=(
                    str(dataset.deterministic_id) if dataset is not None else None
                ),
                source_registry_id=(
                    str(registry.deterministic_id) if registry is not None else None
                ),
                cohort_definition=definition,
                analysis_unit=analysis_unit,
                boundary_selection_policy_version=boundary_policy,
                statistics_policy_version=statistics_policy.policy_version,
                interval_policy_version=interval_policy.policy_version,
                confidence_level=confidence_level,
                sample_size_policy_version=sample_size_policy.policy_version,
                included_statistics=included_statistics,
                excluded_statistics=(
                    "PREDICTIVE_VALIDATION",
                    "THRESHOLD_OPTIMIZATION",
                ),
            )
            rendered = serialize_analysis_model(
                run_research_analysis(request, dataset=dataset, registry=registry)
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "render-research-analysis-report":
            from squeeze_core.analysis.reports import render_markdown_report
            from squeeze_core.analysis.serialization import deserialize_analysis_result

            result = deserialize_analysis_result(args.analysis.read_bytes())
            rendered = render_markdown_report(result)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"), end="" if rendered.endswith(b"\n") else "\n")
            return 0

        if args.command == "build-research-evaluation-batch":
            from squeeze_core.research.batch import run_research_batch
            from squeeze_core.research.models import BatchEvaluationRequest, OrderingPolicy
            from squeeze_core.research.serialization import serialize_research_model

            request = BatchEvaluationRequest(
                batch_version="phase_3b_batch.v1",
                phase_3a_policy_version=args.phase_3a_policy,
                research_detection_policy_version=args.detection_policy,
                outcome_label_policy_version=args.outcome_policy,
                case_ids=tuple(args.case_id),
                case_registry_version="phase_3b_case_registry.v1",
                ordering_policy=(
                    OrderingPolicy.CANONICAL_CASE_ID
                    if args.canonical_order else OrderingPolicy.REQUEST_ORDER
                ),
                fail_fast=args.fail_fast,
            )
            rendered = serialize_research_model(
                run_research_batch(request, args.case_registry)
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "export-research-dataset":
            from squeeze_core.research.dataset import build_research_dataset
            from squeeze_core.research.serialization import (
                deserialize_batch_result,
                serialize_research_csv,
                serialize_research_json,
                serialize_research_jsonl,
            )

            dataset = build_research_dataset(
                deserialize_batch_result(args.batch.read_bytes())
            )
            serializer = {
                "json": serialize_research_json,
                "jsonl": serialize_research_jsonl,
                "csv": serialize_research_csv,
            }[args.format]
            rendered = serializer(dataset)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"), end="" if rendered.endswith(b"\n") else "\n")
            return 0

        if args.command == "build-candidate-evaluation":
            from squeeze_core.contracts import AssetClass
            from squeeze_core.evaluation import (
                RuleEvaluationRequest, evaluate_candidate, serialize_candidate_evaluation,
            )
            from squeeze_core.evaluation.io import load_evaluation_evidence
            from squeeze_core.evaluation.policies import load_policy

            policy = load_policy(args.policy)
            observations, metrics, readiness_results, defaults = load_evaluation_evidence(
                args.evidence
            )
            enabled = tuple(args.rule) if args.rule else policy.enabled_rule_ids
            request = RuleEvaluationRequest(
                symbol=args.symbol,
                asset_class=AssetClass(args.asset_class),
                as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
                policy_version=policy.policy_version,
                enabled_rule_ids=enabled,
                provider_scope=tuple(args.provider),
                input_observations=observations,
                input_metrics=metrics,
                input_readiness_results=readiness_results,
                default_substitution_fields=defaults,
            )
            rendered = serialize_candidate_evaluation(evaluate_candidate(request, policy))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "normalize-biya-history":
            from squeeze_core.validation.outcome_acquisition import (
                deserialize_acquisition_manifest,
            )
            from squeeze_core.validation.outcome_normalization import (
                normalize_acquired_market_bars,
            )

            manifest = deserialize_acquisition_manifest(args.manifest.read_bytes())
            dataset = normalize_acquired_market_bars(manifest, args.raw.read_bytes())
            rendered = canonical_json_bytes(dataset)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(canonical_json_bytes({
                "command": args.command,
                "deterministic_id": dataset.deterministic_id,
                "observation_count": len(dataset.observations),
                "output": args.output.name,
            }).decode("utf-8"))
            return 0

        if args.command == "build-biya-outcome-amendment":
            from squeeze_core.validation import deserialize_validation_case
            from squeeze_core.validation.outcome_amendment import (
                BIYA_EARLIEST_BOUNDARY,
                BIYA_LATEST_BOUNDARY,
                build_boundary_outcome,
            )
            from squeeze_core.validation.outcome_case import (
                build_biya_outcome_amendment_case,
            )
            from squeeze_core.validation.outcome_normalization import HistoricalMarketDataset

            case_document = json.loads(args.validation_case.read_text(encoding="utf-8"))
            if isinstance(case_document, dict) and "case_status" in case_document:
                original = deserialize_validation_case(canonical_json_bytes(case_document))
            else:
                from squeeze_core.validation.case_spec import build_case_from_spec, load_case_spec

                original = build_case_from_spec(load_case_spec(args.validation_case))
            dataset = HistoricalMarketDataset.model_validate_json(args.market_data.read_text(encoding="utf-8"))
            outcomes = (
                build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, dataset),
                build_boundary_outcome(BIYA_LATEST_BOUNDARY, dataset),
            )
            amendment = build_biya_outcome_amendment_case(original, outcomes)
            rendered = canonical_json_bytes(amendment)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "normalize-provider":
            context = AdapterContext.model_validate_json(args.context.read_text(encoding="utf-8"))
            provider_record = _load_provider_record(args.input, args.case)
            if args.provider == "ibkr":
                result = normalize_ibkr_borrow_record(provider_record, context)
            elif args.provider == "finviz":
                result = normalize_finviz_snapshot_record(provider_record, context)
            elif args.provider == "finra":
                result = normalize_finra_short_interest_record(provider_record, context)
            elif args.provider == "sec":
                result = normalize_sec_filing_record(provider_record, context)
            elif args.provider == "halts":
                result = normalize_trading_halt_record(provider_record, context)
            elif args.provider == "market-bars":
                result = normalize_market_bar_record(provider_record, context)
            elif args.provider == "trades-quotes":
                result = normalize_trade_quote_record(provider_record, context)
            else:
                result = normalize_news_record(provider_record, context)
            output = {
                "command": "normalize-provider",
                "provider": args.provider,
                "accepted": result.accepted,
                "observations": result.observations,
                "diagnostics": result.diagnostics,
                "rejection": result.rejection,
            }
            rendered = canonical_json_bytes(output).decode("utf-8")
            print(rendered, file=sys.stdout if result.accepted else sys.stderr)
            return 0 if result.accepted else 1

        if args.command == "build-candidate-validation":
            from squeeze_core.validation import serialize_validation_case
            from squeeze_core.validation.case_spec import build_case_from_spec, load_case_spec

            spec = load_case_spec(args.case_spec)
            observations = load_fixture(args.evidence) if args.evidence is not None else ()
            case = build_case_from_spec(spec, observations)
            rendered = serialize_validation_case(case)
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "export-validation-demo":
            from squeeze_core.validation import (
                assert_export_is_clean,
                build_public_validation_case,
                deserialize_validation_case,
                serialize_public_case,
            )

            case = deserialize_validation_case(args.validation_case.read_bytes())
            public = build_public_validation_case(case)
            rendered = serialize_public_case(public)
            # Projection is the primary guard; this is the last line of defence before
            # bytes leave the deterministic core for a published page.
            assert_export_is_clean(rendered)
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(rendered)
            print(rendered.decode("utf-8"))
            return 0

        if args.command == "build-evidence-readiness":
            observations = load_fixture(args.input)
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            policy_values = (
                None if args.policy is None else json.loads(args.policy.read_text(encoding="utf-8"))
            )
            if policy_values is None:
                # Every optional evidence domain is explicitly enabled by default so
                # a genuinely absent domain resolves MISSING rather than UNKNOWN --
                # a readiness-focused CLI should not silently under-evaluate.
                evidence_policy = PointInTimeEvidencePolicy(
                    as_of=as_of,
                    allow_stale=True,
                    allow_delayed=True,
                    allow_unknown_freshness=True,
                    include_published_short_interest_domain=True,
                    include_sec_filings_domain=True,
                    include_trading_halts_domain=True,
                    include_news_domain=True,
                    include_market_bars_domain=True,
                    include_trades_domain=True,
                    include_quotes_domain=True,
                )
            else:
                values = dict(policy_values)
                values["as_of"] = as_of
                evidence_policy = PointInTimeEvidencePolicy.model_validate(values)
            bundle = build_point_in_time_evidence(args.symbol, observations, evidence_policy)

            from squeeze_core.readiness.policies import lookup_policy

            policy = lookup_policy(args.operation, args.policy_version)
            snapshot = build_evidence_readiness_snapshot(
                bundle, args.operation, policy_version=args.policy_version
            )
            coverage_snapshot = build_domain_coverage_snapshot(bundle, policy.required_domains)
            conflict_summary = build_conflict_summary(bundle, policy.required_domains)
            missingness_summary = build_missingness_summary(
                bundle, coverage_snapshot, policy=policy
            )
            age_alignment = build_evidence_age_alignment(bundle, policy.required_domains)
            reporting_domains = tuple(
                domain for domain in policy.required_domains if domain in REPORTING_PERIOD_FIELDS
            )
            reporting_alignment = (
                build_reporting_period_alignment(bundle, reporting_domains)
                if reporting_domains
                else None
            )

            output = {
                "command": "build-evidence-readiness",
                "operation": snapshot.operation,
                "policy_version": snapshot.policy_version,
                "structural_state": snapshot.structural_state,
                "required_domains": snapshot.required_domains,
                "required_metrics": snapshot.required_metrics,
                "missing_inputs": snapshot.missing_inputs,
                "conflicted_inputs": snapshot.conflicted_inputs,
                "incompatible_inputs": snapshot.incompatible_inputs,
                "insufficient_history_inputs": snapshot.insufficient_history_inputs,
                "coverage_snapshot": coverage_snapshot,
                "age_alignment": age_alignment,
                "reporting_alignment": reporting_alignment,
                "conflict_summary": conflict_summary,
                "missingness_summary": missingness_summary,
                "input_observation_ids": snapshot.input_observation_ids,
                "input_metric_ids": snapshot.input_metric_ids,
                "quality": snapshot.quality,
                "diagnostics": snapshot.diagnostics,
                "deterministic_id": snapshot.deterministic_id,
            }
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        if args.command == "build-trade-quote-series":
            observations = load_fixture(args.input)
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            series = build_trade_quote_series(
                observations,
                TradeQuoteSeriesPolicy(
                    symbol=args.symbol,
                    as_of=as_of,
                    providers=tuple(args.provider),
                    venues=tuple(args.venue),
                    market_scopes=tuple(args.market_scope),
                ),
            )
            output = {"command": "build-trade-quote-series", "series": series}
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        if args.command == "build-market-metrics":
            observations = load_fixture(args.input)
            spec_document = json.loads(args.spec.read_text(encoding="utf-8"))
            cases = spec_document.get("cases") if isinstance(spec_document, dict) else spec_document
            if not isinstance(cases, list) or not cases:
                raise ValueError("--spec must contain a nonempty cases list")
            specs = []
            for case in cases:
                if not isinstance(case, dict):
                    raise ValueError("each spec case must be a JSON object")
                spec = dict(case)
                spec.setdefault("symbol", args.symbol)
                spec.setdefault("as_of", args.as_of)
                specs.append(spec)
            results = build_metric_results(observations, specs)
            output = {"command": "build-market-metrics", "results": results}
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        if args.command == "build-bar-series":
            observations = load_fixture(args.input)
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            series = build_bar_series(
                observations,
                BarSeriesPolicy(
                    symbol=args.symbol,
                    as_of=as_of,
                    interval=args.interval,
                    sessions=tuple(args.session),
                ),
            )
            output = {"command": "build-bar-series", "series": series}
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        if args.command == "build-halt-state":
            observations = load_fixture(args.input)
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            bundle = build_point_in_time_evidence(
                args.symbol,
                observations,
                PointInTimeEvidencePolicy(
                    as_of=as_of,
                    allow_stale=True,
                    allow_delayed=True,
                    allow_unknown_freshness=True,
                    include_trading_halts_domain=True,
                ),
            )
            output = {
                "command": "build-halt-state",
                "symbol": args.symbol.strip().upper(),
                "as_of": as_of,
                "halt_state": bundle.halt_state,
            }
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        if args.command in {"build-evidence", "build-evidence-timeline"}:
            observations = load_fixture(args.input)
            policy_values = (
                None
                if args.policy is None
                else json.loads(args.policy.read_text(encoding="utf-8"))
            )

            def policy_for(as_of: datetime) -> PointInTimeEvidencePolicy:
                if policy_values is None:
                    return PointInTimeEvidencePolicy(
                        as_of=as_of,
                        maximum_future_skew_ms=0,
                        maximum_age_ms_by_event_type={},
                        allow_stale=True,
                        allow_delayed=True,
                        allow_unknown_freshness=True,
                    )
                values = dict(policy_values)
                values["as_of"] = as_of
                return PointInTimeEvidencePolicy.model_validate(values)

            if args.command == "build-evidence":
                as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
                bundle = build_point_in_time_evidence(
                    args.symbol, observations, policy_for(as_of)
                )
                print(canonical_json_bytes(bundle).decode("utf-8"))
                return 0

            timeline_document = json.loads(args.as_of_file.read_text(encoding="utf-8"))
            as_of_values = (
                timeline_document.get("as_of")
                if isinstance(timeline_document, dict) and "as_of" in timeline_document
                else timeline_document
            )
            if not isinstance(as_of_values, dict) or not as_of_values:
                raise ValueError("as-of file must contain a nonempty object of named timestamps")
            bundles = {}
            for label in sorted(as_of_values):
                raw_as_of = as_of_values[label]
                if not isinstance(raw_as_of, str):
                    raise ValueError(f"as-of value must be an ISO timestamp: {label}")
                as_of = datetime.fromisoformat(raw_as_of.replace("Z", "+00:00"))
                bundles[label] = build_point_in_time_evidence(
                    args.symbol, observations, policy_for(as_of)
                )
            output = {
                "command": "build-evidence-timeline",
                "symbol": args.symbol.strip().upper(),
                "bundles": bundles,
            }
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        observations = load_fixture(args.fixture)
        if args.command == "validate":
            ReplayEngine(mode=ReplayMode.NORMALIZED).replay(observations)
            raw_hash = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
            output = {
                "command": "validate",
                "fixture_hash": raw_hash,
                "observation_count": len(observations),
                "valid": True,
            }
            print(canonical_json_bytes(output).decode("utf-8"))
            return 0

        mode = ReplayMode.STRICT if args.mode == "strict" else ReplayMode.NORMALIZED
        result = ReplayEngine(mode=mode).replay(observations)
        print(result.to_bytes().decode("utf-8"))
        return 0
    except Exception as error:
        output = {
            "command": args.command,
            "error": str(error),
            "valid": False,
        }
        print(canonical_json_bytes(output).decode("utf-8"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

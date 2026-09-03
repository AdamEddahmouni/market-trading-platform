"""RT-01 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .baseline import compare_baselines, run_baseline
from .completeness import classify_completeness
from .enums import SamplingMode
from .equivalence import prove_equivalence
from .export import export_document, read_export, spans_from_export, write_export
from .overhead import measure_overhead
from .profiles import ALL_PROFILES, profile_by_id
from .tracer import Tracer, configure_tracer, get_tracer
from .workloads import (
    fixture_ingest_domain_hash,
    quality_replay_domain_hash,
    run_fixture_ingest_workload,
    run_quality_replay_workload,
)

CAPABILITY_IDS = frozenset(
    {
        "RT01.OP.STATUS",
        "RT01.OP.VALIDATE_TRACE",
        "RT01.OP.SHOW_TRACE",
        "RT01.OP.BASELINE",
        "RT01.OP.COMPARE",
        "RT01.OP.SAMPLING_STATUS",
        "RT01.OP.EXPORT",
        "RT01.OP.OVERHEAD",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    capability_id: str
    verification: Mapping[str, Any]


def _sampling_mode(raw: str | None) -> SamplingMode:
    if raw is None:
        return SamplingMode.FULL
    try:
        return SamplingMode(raw.upper())
    except ValueError:
        return SamplingMode.FULL


def execute(capability_id: str, arguments: Mapping[str, Any] | None = None) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        return OperationResult("INVALID", capability_id, {"error": "unknown capability"})
    args = dict(arguments or {})
    tracer = get_tracer()
    if capability_id == "RT01.OP.STATUS":
        return OperationResult(
            "OK",
            capability_id,
            {
                "sampling_mode": tracer.mode.value,
                "collector_counts": tracer.collector.counts.to_dict(),
                "span_count": len(tracer.collector.spans),
            },
        )
    if capability_id == "RT01.OP.SAMPLING_STATUS":
        return OperationResult(
            "OK",
            capability_id,
            {
                "sampling_mode": tracer.mode.value,
                "sample_rate": tracer.sample_rate,
            },
        )
    if capability_id == "RT01.OP.VALIDATE_TRACE":
        findings = tracer.collector.validate()
        return OperationResult(
            "OK" if not findings else "INVALID",
            capability_id,
            {"findings": findings, "span_count": len(tracer.collector.spans)},
        )
    if capability_id == "RT01.OP.SHOW_TRACE":
        limit = int(args.get("limit", 50))
        spans = tracer.collector.export_spans()[:limit]
        completeness = classify_completeness(tracer.collector.spans)
        return OperationResult(
            "OK",
            capability_id,
            {"spans": spans, "completeness": completeness.value},
        )
    if capability_id == "RT01.OP.EXPORT":
        path = args.get("path")
        document = export_document(
            tracer.collector.spans,
            counts=tracer.collector.counts.to_dict(),
            metadata={"capability": capability_id},
        )
        if path:
            write_export(Path(str(path)), document)
        return OperationResult("OK", capability_id, {"exported": len(tracer.collector.spans), "path": path})
    if capability_id == "RT01.OP.BASELINE":
        profile_id = str(args.get("profile_id", "receive_to_canonical_state"))
        sampling = _sampling_mode(args.get("sampling"))
        configure_tracer(Tracer(mode=sampling))
        workload = run_fixture_ingest_workload
        report = run_baseline(
            profile_id=profile_id,
            workload_fn=lambda: workload(),
            iterations=int(args.get("iterations", 3)),
            warmup_iterations=int(args.get("warmup", 1)),
            sampling=sampling,
        )
        return OperationResult("OK", capability_id, report)
    if capability_id == "RT01.OP.COMPARE":
        left = args.get("left")
        right = args.get("right")
        if isinstance(left, str):
            left = read_export(Path(left))
        if isinstance(right, str):
            right = read_export(Path(right))
        if not isinstance(left, dict) or not isinstance(right, dict):
            return OperationResult("INVALID", capability_id, {"error": "left and right baseline documents required"})
        return OperationResult("OK", capability_id, compare_baselines(left, right))
    if capability_id == "RT01.OP.OVERHEAD":
        configure_tracer(Tracer(mode=SamplingMode.OFF))
        report = measure_overhead(run_fixture_ingest_workload, iterations=int(args.get("iterations", 5)))
        equiv = prove_equivalence(fixture_ingest_domain_hash, iterations=2)
        report["domain_equivalence"] = equiv
        return OperationResult("OK", capability_id, report)
    return OperationResult("INVALID", capability_id, {"error": "unhandled"})


def status_payload() -> dict[str, Any]:
    tracer = get_tracer()
    return {
        "subsystem": "rt01",
        "sampling_mode": tracer.mode.value,
        "profiles": [p.profile_id for p in ALL_PROFILES],
        "collector_counts": tracer.collector.counts.to_dict(),
    }


__all__ = ["CAPABILITY_IDS", "OperationResult", "execute", "status_payload"]

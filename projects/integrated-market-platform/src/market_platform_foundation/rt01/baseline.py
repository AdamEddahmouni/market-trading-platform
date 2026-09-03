"""RT-01 baseline runner — produces measured latency evidence."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .enums import SamplingMode, TraceStage
from .profiles import LatencyProfile, profile_by_id
from .span import TraceSpan
from .stats import distribution_stats
from .tracer import Tracer, configure_tracer


@dataclass(frozen=True, slots=True)
class BaselineEnvironment:
    git_head: str
    dirty: bool
    python_version: str


def _git_head(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_dirty(repo_root: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _is_ancestor(ancestor_id: str, descendant: TraceSpan, by_id: dict[str, TraceSpan]) -> bool:
    current = descendant.parent_span_id
    while current is not None:
        if current == ancestor_id:
            return True
        parent = by_id.get(current)
        if parent is None:
            return False
        current = parent.parent_span_id
    return False


def collect_profile_samples(
    spans: list[TraceSpan],
    profile: LatencyProfile,
) -> list[int]:
    if profile.profile_id == "queue_wait":
        waits: list[int] = []
        for span in spans:
            if span.stage == TraceStage.QUEUE:
                if span.queue_enqueue_mono_ns is not None and span.queue_dequeue_mono_ns is not None:
                    waits.append(span.queue_dequeue_mono_ns - span.queue_enqueue_mono_ns)
        return waits

    root_stage = profile.root_stage
    terminal_stage = profile.terminal_stages[0]
    by_trace: dict[str, list[TraceSpan]] = {}
    for span in spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    samples: list[int] = []
    for trace_spans in by_trace.values():
        by_id = {s.span_id: s for s in trace_spans}
        roots = [s for s in trace_spans if s.stage == root_stage]
        terminals = [s for s in trace_spans if s.stage == terminal_stage]
        for terminal in terminals:
            matched_root = None
            for root in roots:
                if _is_ancestor(root.span_id, terminal, by_id):
                    matched_root = root
                    break
            if matched_root is None and len(roots) == 1 and len(terminals) == 1:
                matched_root = roots[0]
            if matched_root is None:
                continue
            elapsed = terminal.clocks.end_monotonic_ns - matched_root.clocks.start_monotonic_ns
            if elapsed >= 0:
                samples.append(elapsed)
    return samples


def run_baseline_iteration(
    workload_fn: Callable[[], list[TraceSpan]],
    *,
    warmup: bool = False,
) -> list[TraceSpan]:
    _ = warmup
    return workload_fn()


def run_baseline(
    *,
    profile_id: str,
    workload_fn: Callable[[], list[TraceSpan]],
    iterations: int = 5,
    warmup_iterations: int = 1,
    repo_root: Path | None = None,
    sampling: SamplingMode = SamplingMode.FULL,
) -> dict[str, Any]:
    profile = profile_by_id(profile_id)
    if profile is None:
        raise ValueError(f"unknown profile_id: {profile_id}")
    repo_root = repo_root or Path(__file__).resolve().parents[3]
    tracer = Tracer(mode=sampling)
    configure_tracer(tracer)
    all_samples: list[int] = []
    for i in range(warmup_iterations):
        run_baseline_iteration(workload_fn, warmup=True)
        tracer.collector.clear()
    for i in range(iterations):
        spans = run_baseline_iteration(workload_fn)
        samples = collect_profile_samples(spans, profile)
        all_samples.extend(samples)
        tracer.collector.clear()
    stats = distribution_stats(all_samples)
    import sys

    env = BaselineEnvironment(
        git_head=_git_head(repo_root),
        dirty=_git_dirty(repo_root),
        python_version=sys.version.split()[0],
    )
    return {
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "clock_basis": profile.clock_basis,
        "sampling": sampling.value,
        "workload": profile.workload,
        "aggregation": profile.aggregation,
        "iterations": iterations,
        "warmup_iterations": warmup_iterations,
        "environment": {
            "git_head": env.git_head,
            "dirty": env.dirty,
            "python_version": env.python_version,
        },
        "statistics": stats.to_dict(),
        "raw_sample_count": len(all_samples),
        "measurement_class": "MEASURED_BASELINE" if all_samples else "NOT_EXERCISED",
    }


def compare_baselines(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    compatible = (
        left.get("profile_id") == right.get("profile_id")
        and left.get("profile_version") == right.get("profile_version")
        and left.get("clock_basis") == right.get("clock_basis")
        and left.get("workload") == right.get("workload")
    )
    delta: dict[str, Any] = {"compatible": compatible}
    if not compatible:
        delta["reason"] = "incompatible_profile_or_workload"
        return delta
    left_stats = left.get("statistics") or {}
    right_stats = right.get("statistics") or {}
    for key in ("median_ns", "mean_ns", "p95_ns"):
        lval = left_stats.get(key)
        rval = right_stats.get(key)
        if isinstance(lval, (int, float)) and isinstance(rval, (int, float)):
            delta[f"delta_{key}"] = rval - lval
    return delta


__all__ = [
    "collect_profile_samples",
    "compare_baselines",
    "run_baseline",
    "run_baseline_iteration",
]

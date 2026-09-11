"""Safe observability for intelligence inference — no secrets or full prompts by default."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import InferenceRecord, IntelligenceResult, ParsingStatus


@dataclass
class InferenceObservability:
    inference_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    cache_hit_count: int = 0
    parse_failure_count: int = 0
    total_latency_ms: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    by_task_type: dict[str, int] = field(default_factory=dict)
    by_provider: dict[str, int] = field(default_factory=dict)

    def record(self, record: InferenceRecord) -> None:
        self.inference_count += 1
        task = record.input_packet.task_type.value
        self.by_task_type[task] = self.by_task_type.get(task, 0) + 1
        if record.cache_hit:
            self.cache_hit_count += 1
        if record.result is not None:
            self.success_count += 1
            self.by_provider[record.result.provider_id] = (
                self.by_provider.get(record.result.provider_id, 0) + 1
            )
            if record.result.latency_ms:
                self.total_latency_ms += record.result.latency_ms
            if record.result.tokens_input:
                self.total_tokens_input += record.result.tokens_input
            if record.result.tokens_output:
                self.total_tokens_output += record.result.tokens_output
            if record.result.parsing_status != ParsingStatus.VALID:
                self.parse_failure_count += 1
        elif record.failure is not None:
            self.failure_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "inference_count": self.inference_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "cache_hit_count": self.cache_hit_count,
            "parse_failure_count": self.parse_failure_count,
            "total_latency_ms": self.total_latency_ms,
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "by_task_type": dict(self.by_task_type),
            "by_provider": dict(self.by_provider),
        }


def result_summary(result: IntelligenceResult) -> dict[str, Any]:
    return {
        "result_id": result.result_id,
        "task_type": result.task_type.value,
        "status": result.status.value,
        "provider_id": result.provider_id,
        "model_id": result.model_id,
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "article_count": len(result.source_event_ids),
        "truncated": False,
        "parse_status": result.parsing_status.value,
        "latency_ms": result.latency_ms,
        "tokens_input": result.tokens_input,
        "tokens_output": result.tokens_output,
    }


__all__ = ["InferenceObservability", "result_summary"]

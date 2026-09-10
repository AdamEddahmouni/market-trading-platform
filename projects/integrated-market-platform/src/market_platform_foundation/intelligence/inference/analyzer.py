"""Canonical news intelligence analyzer — curated input to structured analysis only."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from market_platform_foundation.news.contracts import NewsArticleEvent, PipelineConfig
from market_platform_foundation.news.timestamps import epoch_ns_from_iso, is_observable_at, parse_utc_iso, to_utc_iso

from .config import IntelligenceInferenceConfig, verify_inference_config
from .contracts import (
    InferenceFailure,
    InferenceRecord,
    InferenceStatus,
    IntelligenceInputPacket,
    IntelligenceResult,
    IntelligenceTaskType,
    ParsingStatus,
)
from .errors import InferenceErrorCode
from .hashing import inference_config_hash, raw_response_hash
from .input_builder import build_input_packet
from .observability import InferenceObservability, result_summary
from .parsing import parse_structured_output
from .prompts import PromptRegistry
from .provider import InferenceProvider, render_prompt_for_packet
from .records import InMemoryInferenceRecordRepository


@dataclass
class AnalyzeOutcome:
    record: InferenceRecord
    result: IntelligenceResult | None = None
    failure: InferenceFailure | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "failure": self.failure.to_dict() if self.failure else None,
        }


class NewsIntelligenceAnalyzer:
    """
    Analysis-only intelligence service over curated NewsArticleEvents.

    Responsibilities: as-of safety, input limits, prompt selection, provider call,
    structured validation, inference record creation.

    Explicitly excluded: news collection, broker/Paper/Live execution, strategy signals.
    """

    def __init__(
        self,
        *,
        provider: InferenceProvider,
        prompt_registry: PromptRegistry | None = None,
        repository: InMemoryInferenceRecordRepository | None = None,
        observability: InferenceObservability | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompt_registry or PromptRegistry()
        self._repository = repository or InMemoryInferenceRecordRepository()
        self._observability = observability or InferenceObservability()

    @property
    def repository(self) -> InMemoryInferenceRecordRepository:
        return self._repository

    @property
    def observability(self) -> InferenceObservability:
        return self._observability

    def analyze(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of: str,
        pipeline_config: PipelineConfig,
        inference_config: IntelligenceInferenceConfig | None = None,
        task_type: IntelligenceTaskType | None = None,
        input_id: str | None = None,
    ) -> AnalyzeOutcome:
        config = inference_config or IntelligenceInferenceConfig(
            provider_id=getattr(self._provider, "provider_id", "unknown"),
            model_id=getattr(self._provider, "model_id", "unknown"),
        )
        issues = verify_inference_config(config)
        if issues:
            return self._fail_fast(
                input_id=input_id or f"inp-{uuid.uuid4().hex[:16]}",
                error_code=InferenceErrorCode.PROMPT_CONFIG_INVALID,
                message=",".join(issues),
                parsing_status=ParsingStatus.PROVIDER_ERROR,
            )

        parsed_as_of = parse_utc_iso(as_of)
        if parsed_as_of is None:
            return self._fail_fast(
                input_id=input_id or f"inp-{uuid.uuid4().hex[:16]}",
                error_code=InferenceErrorCode.INVALID_INPUT,
                message=f"AS_OF_INVALID:{as_of}",
                parsing_status=ParsingStatus.PROVIDER_ERROR,
            )
        as_of_iso = to_utc_iso(parsed_as_of)
        as_of_ns = epoch_ns_from_iso(as_of_iso)
        if as_of_ns is None:
            return self._fail_fast(
                input_id=input_id or f"inp-{uuid.uuid4().hex[:16]}",
                error_code=InferenceErrorCode.INVALID_INPUT,
                message=f"AS_OF_INVALID:{as_of}",
                parsing_status=ParsingStatus.PROVIDER_ERROR,
            )

        for event in events:
            if not is_observable_at(event, as_of_ns):
                return self._fail_fast(
                    input_id=input_id or f"inp-{uuid.uuid4().hex[:16]}",
                    error_code=InferenceErrorCode.UNOBSERVABLE_EVENT,
                    message=f"event {event.event_id} not observable at {as_of_iso}",
                    parsing_status=ParsingStatus.PROVIDER_ERROR,
                )

        selected_task = task_type or config.default_task_type
        packet = build_input_packet(
            events=events,
            as_of=as_of_iso,
            as_of_ns=as_of_ns,
            task_type=selected_task,
            pipeline_config=pipeline_config,
            inference_config=config,
            prompt_registry=self._prompts,
            input_id=input_id,
        )
        if not packet.articles:
            return self._fail_with_packet(
                packet,
                error_code=InferenceErrorCode.INVALID_INPUT,
                message="no articles supplied after selection",
                parsing_status=ParsingStatus.MISSING_FIELDS,
            )

        config_hash = inference_config_hash(
            provider_id=self._provider.provider_id,
            model_id=self._provider.model_id,
            timeout_seconds=config.timeout_seconds,
            max_tokens=config.max_tokens,
        )
        if config.enable_cache:
            cached = self._repository.find_cached(
                input_hash=packet.input_hash,
                prompt_hash=packet.prompt_hash,
                provider_id=self._provider.provider_id,
                model_id=self._provider.model_id,
                inference_config_hash=config_hash,
            )
            if cached and cached.result is not None:
                cached_record = InferenceRecord(
                    record_id=f"rec-{uuid.uuid4().hex[:16]}",
                    input_packet=packet,
                    result=cached.result,
                    cache_hit=True,
                )
                self._observability.record(cached_record)
                return AnalyzeOutcome(record=cached_record, result=cached.result)

        requested_time = as_of_iso
        rendered = render_prompt_for_packet(packet, prompt_registry=self._prompts)
        provider_response = self._provider.infer(
            packet,
            rendered_prompt=rendered,
            config=config,
        )
        completed_time = as_of_iso

        if provider_response.error_code is not None:
            failure = InferenceFailure(
                failure_id=f"fail-{uuid.uuid4().hex[:16]}",
                input_id=packet.input_id,
                error_code=provider_response.error_code.value,
                message=provider_response.error_message,
                parsing_status=provider_response.parsing_status,
                provider_id=provider_response.provider_id,
                model_id=provider_response.model_id,
                requested_time=requested_time,
                completed_time=completed_time,
            )
            record = InferenceRecord(
                record_id=f"rec-{uuid.uuid4().hex[:16]}",
                input_packet=packet,
                failure=failure,
            )
            self._repository.put(record)
            self._observability.record(record)
            return AnalyzeOutcome(record=record, failure=failure)

        output, parse_status, parse_message = parse_structured_output(provider_response.raw_text)
        if output is None or parse_status != ParsingStatus.VALID:
            failure = InferenceFailure(
                failure_id=f"fail-{uuid.uuid4().hex[:16]}",
                input_id=packet.input_id,
                error_code=InferenceErrorCode.OUTPUT_SCHEMA_INVALID.value,
                message=parse_message or "schema validation failed",
                parsing_status=parse_status,
                provider_id=provider_response.provider_id,
                model_id=provider_response.model_id,
                requested_time=requested_time,
                completed_time=completed_time,
            )
            record = InferenceRecord(
                record_id=f"rec-{uuid.uuid4().hex[:16]}",
                input_packet=packet,
                failure=failure,
            )
            self._repository.put(record)
            self._observability.record(record)
            return AnalyzeOutcome(record=record, failure=failure)

        result = IntelligenceResult(
            result_id=f"res-{uuid.uuid4().hex[:16]}",
            input_id=packet.input_id,
            status=InferenceStatus.SUCCESS,
            task_type=packet.task_type,
            as_of=packet.as_of,
            output=output,
            parsing_status=ParsingStatus.VALID,
            provider_id=provider_response.provider_id,
            model_id=provider_response.model_id,
            prompt_id=packet.prompt_id,
            prompt_version=packet.prompt_version,
            prompt_hash=packet.prompt_hash,
            input_hash=packet.input_hash,
            inference_config_hash=config_hash,
            requested_time=requested_time,
            completed_time=completed_time,
            source_event_ids=tuple(article.event_id for article in packet.articles),
            instrument_ids=packet.instrument_ids,
            tokens_input=provider_response.tokens_input,
            tokens_output=provider_response.tokens_output,
            latency_ms=provider_response.latency_ms,
            raw_response_hash=raw_response_hash(provider_response.raw_text),
            provider_request_id=provider_response.provider_request_id,
            provider_response_id=provider_response.provider_response_id,
        )
        record = InferenceRecord(record_id=f"rec-{uuid.uuid4().hex[:16]}", input_packet=packet, result=result)
        self._repository.put(record)
        self._observability.record(record)
        return AnalyzeOutcome(record=record, result=result)

    def _fail_fast(
        self,
        *,
        input_id: str,
        error_code: InferenceErrorCode,
        message: str,
        parsing_status: ParsingStatus,
    ) -> AnalyzeOutcome:
        failure = InferenceFailure(
            failure_id=f"fail-{uuid.uuid4().hex[:16]}",
            input_id=input_id,
            error_code=error_code.value,
            message=message,
            parsing_status=parsing_status,
        )
        placeholder = IntelligenceInputPacket(
            input_id=input_id,
            task_type=IntelligenceTaskType.NEWS_SENTIMENT,
            as_of="",
            articles=(),
            instrument_ids=(),
            prompt_id="",
            prompt_version="",
            prompt_hash="",
            output_schema_version="",
            model_policy_id="",
        )
        record = InferenceRecord(record_id=f"rec-{uuid.uuid4().hex[:16]}", input_packet=placeholder, failure=failure)
        self._observability.record(record)
        return AnalyzeOutcome(record=record, failure=failure)

    def _fail_with_packet(
        self,
        packet: IntelligenceInputPacket,
        *,
        error_code: InferenceErrorCode,
        message: str,
        parsing_status: ParsingStatus,
    ) -> AnalyzeOutcome:
        failure = InferenceFailure(
            failure_id=f"fail-{uuid.uuid4().hex[:16]}",
            input_id=packet.input_id,
            error_code=error_code.value,
            message=message,
            parsing_status=parsing_status,
        )
        record = InferenceRecord(record_id=f"rec-{uuid.uuid4().hex[:16]}", input_packet=packet, failure=failure)
        self._repository.put(record)
        self._observability.record(record)
        return AnalyzeOutcome(record=record, failure=failure)


__all__ = ["AnalyzeOutcome", "NewsIntelligenceAnalyzer", "result_summary"]

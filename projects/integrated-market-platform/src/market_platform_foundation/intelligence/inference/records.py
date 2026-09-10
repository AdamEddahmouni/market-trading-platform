"""In-memory inference record repository for replay and idempotency."""

from __future__ import annotations

import threading
from typing import Any

from .contracts import InferenceRecord


class InMemoryInferenceRecordRepository:
    """Fixture repository — durable persistence deferred to a later increment."""

    def __init__(self) -> None:
        self._records: dict[str, InferenceRecord] = {}
        self._cache_index: dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def cache_key(
        *,
        input_hash: str,
        prompt_hash: str,
        provider_id: str,
        model_id: str,
        inference_config_hash: str,
    ) -> str:
        return "|".join([input_hash, prompt_hash, provider_id, model_id, inference_config_hash])

    def put(self, record: InferenceRecord) -> str:
        with self._lock:
            self._records[record.record_id] = record
            if record.result is not None:
                key = self.cache_key(
                    input_hash=record.input_packet.input_hash,
                    prompt_hash=record.input_packet.prompt_hash,
                    provider_id=record.result.provider_id,
                    model_id=record.result.model_id,
                    inference_config_hash=record.result.inference_config_hash,
                )
                self._cache_index[key] = record.record_id
            return record.record_id

    def get(self, record_id: str) -> InferenceRecord | None:
        with self._lock:
            return self._records.get(record_id)

    def find_cached(
        self,
        *,
        input_hash: str,
        prompt_hash: str,
        provider_id: str,
        model_id: str,
        inference_config_hash: str,
    ) -> InferenceRecord | None:
        key = self.cache_key(
            input_hash=input_hash,
            prompt_hash=prompt_hash,
            provider_id=provider_id,
            model_id=model_id,
            inference_config_hash=inference_config_hash,
        )
        with self._lock:
            record_id = self._cache_index.get(key)
            if not record_id:
                return None
            return self._records.get(record_id)

    def list_records(self) -> tuple[InferenceRecord, ...]:
        with self._lock:
            return tuple(self._records.values())

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "record_count": len(self._records),
                "cache_index_size": len(self._cache_index),
            }


__all__ = ["InMemoryInferenceRecordRepository"]

"""Deterministic hashes for governed inference input and configuration."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import IntelligenceInputPacket


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prompt_hash(*, prompt_id: str, version: str, template: str) -> str:
    canonical = json.dumps(
        {"prompt_id": prompt_id, "version": version, "template": template},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_hex(canonical)


def input_hash_from_dict(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_hex(canonical)


def compute_input_hash(packet: IntelligenceInputPacket) -> str:
    """Hash material inference input — excludes volatile request IDs."""
    articles = []
    for article in packet.articles:
        articles.append(
            {
                "event_id": article.event_id,
                "headline": article.headline,
                "summary": article.summary,
                "published_time": article.published_time,
                "retrieved_time": article.retrieved_time,
                "instrument_ids": list(article.instrument_ids),
                "deterministic_catalyst_ids": list(article.deterministic_catalyst_ids),
                "source_id": article.source_id,
            }
        )
    payload = {
        "as_of": packet.as_of,
        "task_type": packet.task_type.value,
        "articles": articles,
        "instrument_ids": list(packet.instrument_ids),
        "prompt_id": packet.prompt_id,
        "prompt_version": packet.prompt_version,
        "output_schema_version": packet.output_schema_version,
        "model_policy_id": packet.model_policy_id,
    }
    return input_hash_from_dict(payload)


def inference_config_hash(*, provider_id: str, model_id: str, timeout_seconds: float, max_tokens: int) -> str:
    payload = {
        "provider_id": provider_id,
        "model_id": model_id,
        "timeout_seconds": timeout_seconds,
        "max_tokens": max_tokens,
    }
    return input_hash_from_dict(payload)


def raw_response_hash(text: str) -> str:
    return sha256_hex(text)


__all__ = [
    "compute_input_hash",
    "inference_config_hash",
    "input_hash_from_dict",
    "prompt_hash",
    "raw_response_hash",
    "sha256_hex",
]

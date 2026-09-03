"""RT-01 deterministic sampling."""

from __future__ import annotations

import hashlib

from .enums import SamplingMode


def sampling_decision(
    *,
    mode: SamplingMode,
    stable_key: str,
    rate: int = 100,
) -> bool:
    if mode == SamplingMode.OFF:
        return False
    if mode == SamplingMode.FULL:
        return True
    if rate <= 0:
        return False
    digest = hashlib.sha256(stable_key.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % rate
    return bucket == 0


__all__ = ["sampling_decision"]

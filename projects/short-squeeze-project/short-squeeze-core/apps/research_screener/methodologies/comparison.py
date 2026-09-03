from __future__ import annotations

from .adam_v1 import evaluate_adam
from .evidence import EvidenceInput
from .legacy import evaluate_legacy
from .peer_reference import describe_peer


def compare_candidate(
    inputs: dict[str, EvidenceInput], *, as_of: str | None = None
) -> list[dict]:
    return [
        evaluate_legacy(inputs, as_of=as_of).as_dict(),
        describe_peer(inputs, as_of=as_of).as_dict(),
        evaluate_adam(inputs, as_of=as_of).as_dict(),
    ]

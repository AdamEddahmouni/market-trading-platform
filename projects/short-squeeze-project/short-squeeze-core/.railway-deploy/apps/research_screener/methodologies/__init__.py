"""Independent, backend-only methodology projections for the research screener."""

from .adam_v1 import ADAM_POLICY_ID, evaluate_adam
from .comparison import compare_candidate
from .legacy import LEGACY_ID, evaluate_legacy
from .peer_reference import PEER_ID, describe_peer

__all__ = [
    "ADAM_POLICY_ID",
    "LEGACY_ID",
    "PEER_ID",
    "compare_candidate",
    "describe_peer",
    "evaluate_adam",
    "evaluate_legacy",
]

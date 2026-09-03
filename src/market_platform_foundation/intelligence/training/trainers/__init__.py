"""Candidate trainers (BUILD 18)."""

from .base import CandidateTrainer, get_trainer, register_trainer, supported_trainer_kinds

__all__ = [
    "CandidateTrainer",
    "get_trainer",
    "register_trainer",
    "supported_trainer_kinds",
]

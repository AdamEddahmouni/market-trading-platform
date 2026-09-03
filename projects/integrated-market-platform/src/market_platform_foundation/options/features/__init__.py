"""Options feature conditioning helpers."""

from .squeeze_context import augment_features_with_context, build_squeeze_context_for_options

__all__ = [
    "augment_features_with_context",
    "build_squeeze_context_for_options",
]

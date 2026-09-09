"""Deterministic canonical instrument identity serialization for UI routes."""

from __future__ import annotations

from urllib.parse import quote, unquote


def encode_instrument_route_param(canonical_id: str) -> str:
    """URL-safe encoding preserving round-trip identity."""
    text = str(canonical_id or "").strip()
    if not text:
        return ""
    return quote(text, safe="")


def decode_instrument_route_param(route_param: str) -> str:
    """Decode a route/query instrument reference to canonical id."""
    text = str(route_param or "").strip()
    if not text:
        return ""
    return unquote(text).strip()


__all__ = ["decode_instrument_route_param", "encode_instrument_route_param"]

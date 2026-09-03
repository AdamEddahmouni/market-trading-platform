"""Offline observation contracts and deterministic replay."""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("short-squeeze-core")
except PackageNotFoundError:
    __version__ = "0.0.0"


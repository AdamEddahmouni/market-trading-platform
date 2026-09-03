"""Compatibility wrapper for the canonical manifest-driven full suite."""

from __future__ import annotations

import sys

try:  # Supports module import and direct script execution.
    from tools.validate import main as validate_main
except ModuleNotFoundError:  # pragma: no cover - direct script execution path.
    from validate import main as validate_main


def main(argv: list[str] | None = None) -> int:
    """Delegate to ``validate.py full`` while preserving its exit status."""

    forwarded = list(sys.argv[1:] if argv is None else argv)
    return validate_main(["full", *forwarded])


if __name__ == "__main__":
    raise SystemExit(main())

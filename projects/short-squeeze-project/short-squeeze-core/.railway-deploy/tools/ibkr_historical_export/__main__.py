"""Entry point: ``python -m tools.ibkr_historical_export <command>``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

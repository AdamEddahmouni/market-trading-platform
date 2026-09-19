"""Item 9 operator CLIs (read-only preflight and corpus status)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("usage: item9 next-rth-preflight [--json]", file=sys.stderr)
        return 2
    if args[0] == "next-rth-preflight":
        from item9_next_rth_preflight import main as next_rth_preflight_main  # noqa: E402

        return int(next_rth_preflight_main(args))
    if args[0] in {"corpus-status", "status", "classify", "validate"}:
        from item9_corpus_status import main as corpus_main  # type: ignore[import-not-found]

        return int(corpus_main(args))
    print(f"unknown item9 command: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

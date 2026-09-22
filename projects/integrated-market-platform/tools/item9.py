"""Item 9 operator CLIs (read-only preflight, corpus status, readiness)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(
            "usage: item9 <next-rth-preflight|corpus-status|readiness-snapshot|"
            "calibration-preflight> ...",
            file=sys.stderr,
        )
        return 2
    if args[0] == "next-rth-preflight":
        from item9_next_rth_preflight import main as next_rth_preflight_main  # noqa: E402

        return int(next_rth_preflight_main(args))
    if args[0] in {"corpus-status", "status", "classify", "validate"}:
        from item9_corpus_status import main as corpus_main  # type: ignore[import-not-found]

        return int(corpus_main(args))
    if args[0] == "readiness-snapshot":
        from item9_readiness_snapshot import main as readiness_main  # noqa: E402

        return int(readiness_main(args[1:]))
    if args[0] == "calibration-preflight":
        from item9_calibration_preflight import main as preflight_main  # noqa: E402

        return int(preflight_main(args[1:]))
    print(f"unknown item9 command: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Discover and run all per-phase unittest directories."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

TEST_DIRECTORIES: tuple[str, ...] = (
    "postroot",
    "phase0",
    "phase0a",
    "phase1",
    "phase2",
    "phase3",
    "phase4",
    "phase5",
    "phase5r",
    "phase6",
    "phase7",
    "phase8",
    "phase9",
    "phase10",
    "phase11",
    "storage",
    "assistant",
    "donor_bridge",
    "donor_patterns",
    "order_flow",
    "contracts",
    "cross_lane",
    "distribution",
    "gridiq",
    "integration",
    "providers",
    "ui1",
    "ui2",
    "mra001",
    "mra002",
)


def run_directory(directory: str) -> subprocess.CompletedProcess[str]:
    env = dict(**__import__("os").environ)
    existing = env.get("PYTHONPATH", "")
    roots = [str(REPOSITORY_ROOT / "src"), str(REPOSITORY_ROOT)]
    env["PYTHONPATH"] = ";".join(roots + ([existing] if existing else []))
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", f"tests/{directory}", "-v"],
        cwd=str(REPOSITORY_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def main() -> int:
    tests_root = REPOSITORY_ROOT / "tests"
    failures: list[str] = []
    total_run = 0

    for directory in TEST_DIRECTORIES:
        target = tests_root / directory
        if not target.is_dir():
            print(f"SKIP {directory}: directory not found")
            continue
        print(f"\n=== tests/{directory} ===")
        result = run_directory(directory)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            failures.append(directory)
        else:
            for line in reversed(result.stdout.splitlines()):
                if line.startswith("Ran "):
                    try:
                        total_run += int(line.split()[1])
                    except (IndexError, ValueError):
                        pass
                    break

    print("\n=== summary ===")
    print(f"directories: {len(TEST_DIRECTORIES)}")
    print(f"tests run (approx): {total_run}")
    if failures:
        print(f"failed directories: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

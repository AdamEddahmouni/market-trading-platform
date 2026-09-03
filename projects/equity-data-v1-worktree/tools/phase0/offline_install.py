"""Copy a manifest-selected local Phase 0 package without a package manager."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.offline_guard import install_guard


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    events: list[dict[str, str]] = []
    install_guard(events)
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--inventory", required=True)
    args = parser.parse_args()
    source_root = Path(args.source_root).resolve()
    destination = Path(args.destination).resolve() if args.destination else Path(sysconfig.get_path("purelib"))
    destination.mkdir(parents=True, exist_ok=True)
    package_destination = destination / "market_platform_foundation"
    if package_destination.exists() and any(package_destination.iterdir()):
        raise SystemExit("destination package directory is not empty")
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    installed: list[dict[str, object]] = []
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.parts[:2] != ("src", "market_platform_foundation"):
            continue
        source = source_root / relative
        if _sha256(source) != row["sha256"]:
            raise SystemExit("source hash mismatch")
        target = destination / Path(*relative.parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if _sha256(target) != row["sha256"]:
            raise SystemExit("installed hash mismatch")
        installed.append(
            {"byte_length": target.stat().st_size, "path": Path(*relative.parts[1:]).as_posix(), "sha256": row["sha256"]}
        )
    data = (json.dumps({"events": events, "files": installed}, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    Path(args.inventory).write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

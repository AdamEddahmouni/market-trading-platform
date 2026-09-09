"""G15 BL-0803 — dead-route caller census (archive-first evidence)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

ROUTE_CANDIDATES = (
    "/paper/account",
    "/paper/positions",
    "/paper/fills",
    "/paper/risk",
    "/paper/orders",
    "/capabilities",
)

SEARCH_ROOTS = (
    ROOT / "ui",
    ROOT / "src",
    ROOT / "tests",
    ROOT / "tools",
    ROOT / "docs",
)

ROUTE_PATTERN = re.compile(
    r'["\'](/paper/(?:account|positions|fills|risk|orders)|/capabilities)["\']'
)


@dataclass(frozen=True)
class RouteCensusRow:
    route: str
    frontend_callers: int
    backend_handlers: int
    test_callers: int
    doc_references: int
    classification: str
    disposition: str

    def to_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "callers": {
                "frontend": self.frontend_callers,
                "backend": self.backend_handlers,
                "tests": self.test_callers,
                "docs": self.doc_references,
            },
            "classification": self.classification,
            "disposition": self.disposition,
        }


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".js", ".md", ".json"}:
                if "node_modules" in path.parts or ".venv" in path.parts:
                    continue
                yield path


def _count_route_hits(route: str, path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return text.count(route)


def classify_route(
    route: str,
    *,
    frontend: int,
    backend: int,
    tests: int,
    docs: int,
) -> tuple[str, str]:
    if route == "/paper/orders":
        if frontend > 0:
            return "ACTIVE", "KEEP — POST submit boundary"
        if tests > 0:
            return "TEST_ONLY", "KEEP — GET list used in tests only"
        return "COMPATIBILITY", "ARCHIVE_FIRST — GET superseded by /paper/portfolio"
    if route == "/capabilities":
        if frontend > 0:
            return "ACTIVE", "KEEP — caller still present"
        return "COMPATIBILITY", "ARCHIVE_FIRST — superseded by /context capability_states"
    if frontend > 0:
        return "ACTIVE", "KEEP"
    if tests > 0 and backend > 0:
        return "TEST_ONLY", "ARCHIVE_FIRST — no production frontend callers"
    if backend > 0 and docs > 0:
        return "COMPATIBILITY", "ARCHIVE_FIRST — legacy read surface"
    if backend > 0:
        return "COMPATIBILITY", "ARCHIVE_FIRST"
    return "UNKNOWN", "REVIEW"


def build_census(repository_root: Path = ROOT) -> list[RouteCensusRow]:
    rows: list[RouteCensusRow] = []
    files = list(_iter_files(SEARCH_ROOTS))
    for route in ROUTE_CANDIDATES:
        frontend = 0
        backend = 0
        tests = 0
        docs = 0
        for path in files:
            hits = _count_route_hits(route, path)
            if hits == 0:
                continue
            relative = path.relative_to(repository_root).as_posix()
            if relative.startswith("ui/"):
                if relative.endswith("vite.config.ts"):
                    continue
                frontend += hits
            elif relative.startswith("src/"):
                backend += hits
            elif relative.startswith("tests/"):
                tests += hits
            elif relative.startswith("docs/"):
                docs += hits
        classification, disposition = classify_route(
            route,
            frontend=frontend,
            backend=backend,
            tests=tests,
            docs=docs,
        )
        rows.append(
            RouteCensusRow(
                route=route,
                frontend_callers=frontend,
                backend_handlers=backend,
                test_callers=tests,
                doc_references=docs,
                classification=classification,
                disposition=disposition,
            )
        )
    return rows


def write_census_report(output: Path, repository_root: Path = ROOT) -> dict[str, object]:
    rows = build_census(repository_root)
    payload = {
        "schema_version": "1.0",
        "report_type": "g15_dead_route_census",
        "routes": [row.to_dict() for row in rows],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload

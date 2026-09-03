"""Private, Git-ignored output layout for the collection tool.

All provider data lives under ``intake/local-bars/ibkr-batch-05/`` which is covered by
the repository's ``intake/local-bars/`` .gitignore rule. Nothing here is ever committed.
"""

from __future__ import annotations

from pathlib import Path

from .cohort import DETECTION_CONTEXT, FROZEN_FORWARD

# request_name -> file slug
REQUEST_FILE_SLUG: dict[str, str] = {
    DETECTION_CONTEXT: "detection-context",
    FROZEN_FORWARD: "frozen-forward-24h",
}


def repo_root() -> Path:
    # tools/ibkr_historical_export/paths.py -> repo root is three parents up.
    return Path(__file__).resolve().parents[2]


def default_private_root() -> Path:
    return repo_root() / "intake" / "local-bars" / "ibkr-batch-05"


class PrivateLayout:
    """Resolves private artifact paths under a chosen root."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        for sub in ("connection", "contracts", "raw", "requests", "errors", "provenance", "preflight"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # connection
    @property
    def probe_result(self) -> Path:
        return self.root / "connection" / "probe-result.json"

    # contracts
    def contract_candidates(self, symbol: str) -> Path:
        return self.root / "contracts" / f"{symbol}-contract-candidates.json"

    # raw
    def raw_jsonl(self, symbol: str, request_name: str) -> Path:
        return self.root / "raw" / f"{symbol}-{REQUEST_FILE_SLUG[request_name]}.jsonl"

    def raw_csv(self, symbol: str, request_name: str) -> Path:
        return self.root / "raw" / f"{symbol}-{REQUEST_FILE_SLUG[request_name]}.csv"

    def raw_relative_csv(self, symbol: str, request_name: str) -> str:
        return f"raw/{symbol}-{REQUEST_FILE_SLUG[request_name]}.csv"

    # requests / errors / provenance
    @property
    def request_manifest(self) -> Path:
        return self.root / "requests" / "request-manifest.json"

    @property
    def api_diagnostics(self) -> Path:
        return self.root / "errors" / "api-diagnostics.jsonl"

    @property
    def artifact_manifest(self) -> Path:
        return self.root / "provenance" / "artifact-manifest.json"

    @property
    def sha256_manifest(self) -> Path:
        return self.root / "provenance" / "sha256-manifest.json"

    # preflight
    def preflight_report(self, symbol: str, request_name: str) -> Path:
        directory = self.root / "preflight" / symbol / REQUEST_FILE_SLUG[request_name]
        return directory / "readiness-report.json"

    @property
    def collection_summary(self) -> Path:
        return self.root / "collection-summary.json"

    @property
    def collection_plan(self) -> Path:
        return self.root / "collection-plan.json"


__all__ = [
    "REQUEST_FILE_SLUG",
    "repo_root",
    "default_private_root",
    "PrivateLayout",
]

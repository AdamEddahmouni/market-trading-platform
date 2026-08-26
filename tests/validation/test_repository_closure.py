"""Contract tests for the post-BUILD35 repository closure audit."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from tools.repository_closure import ClosureAuditError, load_closure_audit
except ModuleNotFoundError as exc:  # RED: expose the missing validator clearly.
    ClosureAuditError = ValueError  # type: ignore[assignment,misc]
    load_closure_audit = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parents[2]


class RepositoryClosureValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"repository closure validator is missing: {IMPORT_ERROR}")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for relative in (
            "src/foundation/active",
            "src/foundation/legacy",
            "tools/phase0",
            "ui",
        ):
            (self.root / relative).mkdir(parents=True)
        (self.root / "src/foundation/kernel.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.audit_path = self.root / "audit.json"

    def valid_payload(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "campaign": "POST-BUILD35-REPOSITORY-CLOSURE-001",
            "predecessor": "BUILD35",
            "classification_time_changes": "NONE",
            "coverage_rules": [
                {
                    "root": "src/foundation",
                    "include": "CHILD_DIRECTORIES",
                    "exclude": [],
                },
                {
                    "root": "src/foundation",
                    "include": "PYTHON_FILES",
                    "exclude": ["__init__.py"],
                },
                {
                    "root": "tools",
                    "include": "CHILD_DIRECTORIES",
                    "exclude": ["__pycache__"],
                },
            ],
            "required_paths": ["ui"],
            "entries": [
                {
                    "id": "active",
                    "classification": "CANONICAL",
                    "scope": ["src/foundation/active"],
                    "responsibility": "active decisions",
                    "evidence": ["runtime composition"],
                    "disposition": "KEEP",
                },
                {
                    "id": "support",
                    "classification": "RETAINED_SUPPORTING",
                    "scope": ["src/foundation/kernel.py", "tools/phase0"],
                    "responsibility": "contracts and historical evidence",
                    "evidence": ["validation manifest"],
                    "disposition": "KEEP",
                },
                {
                    "id": "legacy",
                    "classification": "SUPERSEDED",
                    "scope": ["src/foundation/legacy"],
                    "responsibility": "legacy decisions",
                    "evidence": ["replacement evidence"],
                    "canonical_target": "active",
                    "disposition": "PRESERVE_HISTORY",
                },
                {
                    "id": "detached-ui",
                    "classification": "UNINTEGRATED",
                    "scope": ["ui"],
                    "responsibility": "detached interface",
                    "evidence": ["no composition import"],
                    "disposition": "DEFER",
                },
            ],
        }

    def write_payload(self, payload: dict[str, object]) -> None:
        self.audit_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_loads_complete_exact_coverage(self) -> None:
        self.write_payload(self.valid_payload())

        audit = load_closure_audit(self.audit_path, repository_root=self.root)

        self.assertEqual(audit.campaign, "POST-BUILD35-REPOSITORY-CLOSURE-001")
        self.assertEqual(len(audit.entries), 4)
        self.assertEqual(audit.covered_paths, audit.discovered_paths)

    def test_rejects_missing_discovered_path(self) -> None:
        payload = self.valid_payload()
        payload["entries"] = [
            row for row in payload["entries"] if row["id"] != "legacy"  # type: ignore[index]
        ]
        self.write_payload(payload)

        with self.assertRaisesRegex(ClosureAuditError, "unclassified path: src/foundation/legacy"):
            load_closure_audit(self.audit_path, repository_root=self.root)

    def test_rejects_invalid_classification(self) -> None:
        payload = self.valid_payload()
        payload["entries"][0]["classification"] = "ACTIVE"  # type: ignore[index]
        self.write_payload(payload)

        with self.assertRaisesRegex(ClosureAuditError, "invalid classification for active"):
            load_closure_audit(self.audit_path, repository_root=self.root)

    def test_wrapper_requires_existing_canonical_target(self) -> None:
        payload = self.valid_payload()
        payload["entries"][2]["classification"] = "WRAPPED"  # type: ignore[index]
        payload["entries"][2]["canonical_target"] = "missing"  # type: ignore[index]
        payload["entries"][2]["disposition"] = "KEEP_WRAPPER"  # type: ignore[index]
        self.write_payload(payload)

        with self.assertRaisesRegex(ClosureAuditError, "unknown canonical_target for legacy: missing"):
            load_closure_audit(self.audit_path, repository_root=self.root)


class CanonicalRepositoryClosureAuditTests(unittest.TestCase):
    def test_canonical_audit_is_complete_non_destructive_and_uses_closed_vocabulary(self) -> None:
        audit = load_closure_audit(
            ROOT
            / "artifacts"
            / "repository-closure"
            / "POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json",
            repository_root=ROOT,
        )

        self.assertEqual(audit.predecessor, "BUILD35")
        self.assertEqual(audit.classification_time_changes, "NONE")
        self.assertEqual(
            {entry.classification for entry in audit.entries},
            {
                "CANONICAL",
                "WRAPPED",
                "RETAINED_SUPPORTING",
                "SUPERSEDED",
                "DUPLICATE",
                "DEAD",
                "UNINTEGRATED",
            },
        )
        self.assertEqual(audit.covered_paths, audit.discovered_paths)


if __name__ == "__main__":
    unittest.main()

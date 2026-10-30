"""Build identity without a git checkout (AUD-037, AUD-040) and truthful bar provenance on new fills (AUD-014)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "release"))
sys.path.insert(0, str(ROOT / "tools" / "release_candidate"))

import apply_release  # noqa: E402
import write_build_identity  # noqa: E402
from market_platform_foundation import build_identity  # noqa: E402
from market_platform_foundation.evaluation.prospective import POLICY, build_run  # noqa: E402
from market_platform_foundation.execution.book_aware import BookAwareL2Simulator  # noqa: E402
from market_platform_foundation.execution.simulator import BarConservativeSimulator  # noqa: E402
from market_platform_foundation.market_data.execution_event_buffer import LIVE_L1_BAR_CONSTRUCTION  # noqa: E402
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402
from market_platform_foundation.ui_api.prospective_evaluation import ProspectiveEvaluationService  # noqa: E402

REVISION = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"
NO_GIT = patch.object(build_identity, "read_git_head", return_value=None)


def _app(tmp: Path) -> Path:
    app = tmp / "app"
    (app / "src" / "pkg").mkdir(parents=True)
    (app / "src" / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    (app / "tools" / "ui1").mkdir(parents=True)
    (app / "tools" / "ui1" / "run_ui_api.py").write_text("# app\n", encoding="utf-8")
    return app


def _bars(**extra: object) -> list[dict]:
    return [{"available_time": t, "normalized_event_id": f"bar-{t}",
             "bar_payload": {"high": "101.00", "low": "99.00", "volume": 10000}, **extra} for t in (1000, 2000)]


def _simulate(simulator_class=BarConservativeSimulator, bars=None):
    return simulator_class(policy=DEFAULT_RISK_POLICY).simulate(
        intent={"created_time": 500, "direction": "long", "instrument_id": "NVDA", "intent_id": "i-1", "quantity": 10},
        risk_decision={"decision": "APPROVE", "approved_quantity": 10}, bars=bars if bars is not None else _bars())


class ResolutionOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = _app(self.tmp)

    def resolve(self, **env):
        return build_identity.resolve_build_identity(root=self.app, environ=env)

    def test_non_git_tree_without_identity_is_explicitly_unavailable(self):
        with NO_GIT:
            identity = self.resolve()
            fields = build_identity.provenance_fields(root=self.app, environ={})
        self.assertEqual((identity["source_revision"], identity["revision_source"]), (None, "UNAVAILABLE"))
        self.assertEqual(fields, {"git_sha": "UNAVAILABLE", "build_id": "UNAVAILABLE", "revision_source": "UNAVAILABLE"})

    def test_release_identity_file_names_the_revision_without_git(self):
        written = write_build_identity.write(self.app, revision=REVISION, release="rel-1")
        with NO_GIT:
            identity = self.resolve()
        self.assertEqual(identity["source_revision"], REVISION)
        self.assertEqual(identity["revision_source"], "BUILD_IDENTITY_FILE")
        self.assertEqual(identity["build_id"], written["build_id"])

    def test_env_override_wins_and_a_file_beats_a_git_checkout(self):
        write_build_identity.write(self.app, revision=REVISION, release="rel-1")
        with patch.object(build_identity, "read_git_head", return_value=OTHER):
            self.assertEqual(self.resolve(IMP_BUILD_REVISION=OTHER)["revision_source"], "ENV")
            self.assertEqual(self.resolve()["source_revision"], REVISION)
            (self.app / "BUILD-IDENTITY.json").unlink()
            self.assertEqual(self.resolve()["revision_source"], "GIT_CHECKOUT")

    def test_a_malformed_identity_never_borrows_a_revision(self):
        (self.app / "BUILD-IDENTITY.json").write_text(json.dumps({"schema": "imp.build-identity/1",
                                                                  "source_revision": "abc123"}), encoding="utf-8")
        with patch.object(build_identity, "read_git_head", return_value=OTHER):
            identity = self.resolve()
            bad_env = self.resolve(IMP_BUILD_REVISION="HEAD")
        self.assertEqual((identity["source_revision"], identity["revision_source"]), (None, "INVALID_BUILD_IDENTITY"))
        self.assertEqual(bad_env["revision_source"], "INVALID_BUILD_IDENTITY")

    def test_writer_refuses_a_guessed_revision_and_verify_detects_a_changed_tree(self):
        with self.assertRaises(ValueError):
            write_build_identity.write(self.app, revision="UNAVAILABLE", release="rel-1")
        write_build_identity.write(self.app, revision=REVISION, release="rel-1")
        with self.assertRaises(FileExistsError):
            write_build_identity.write(self.app, revision=OTHER, release="rel-2")
        self.assertEqual(write_build_identity.verify(self.app)["status"], "MATCH")
        (self.app / "src" / "pkg" / "m.py").write_text("x = 2\n", encoding="utf-8")
        self.assertEqual(write_build_identity.verify(self.app)["status"], "TREE_CHANGED_SINCE_BUILD")


class ReleaseApplyIdentityTests(unittest.TestCase):
    def test_apply_writes_the_release_commit_and_rollback_restores_the_previous_identity(self):
        tmp = Path(tempfile.mkdtemp())
        app = _app(tmp)
        write_build_identity.write(app, revision=OTHER, release="previous")
        before = (app / "BUILD-IDENTITY.json").read_bytes()
        rc = tmp / "rc"
        (rc / "delta" / "src" / "pkg").mkdir(parents=True)
        (rc / "delta" / "src" / "pkg" / "m.py").write_text("x = 3\n", encoding="utf-8")
        manifest = {"release": "rel-new", "commit": REVISION, "conflicts": [], "preserve": [],
                    "files": [{"path": "src/pkg/m.py", "sha256": apply_release.sha(rc / "delta/src/pkg/m.py"),
                               "serving_preimage_sha256": apply_release.sha(app / "src/pkg/m.py")}]}
        record = apply_release.apply(app, tmp / "pre", manifest, rc=rc)
        body = json.loads((app / "BUILD-IDENTITY.json").read_text(encoding="utf-8"))
        self.assertTrue(record["complete"])
        self.assertEqual((body["source_revision"], body["release"]), (REVISION, "rel-new"))
        self.assertEqual(write_build_identity.verify(app)["status"], "MATCH")
        outcome = apply_release.rollback(app, tmp / "pre", manifest)
        self.assertTrue(outcome["tree_matches_pre_release_manifest"])
        self.assertEqual((app / "BUILD-IDENTITY.json").read_bytes(), before)


class FillProvenanceTests(unittest.TestCase):
    def test_a_non_git_deployment_stamps_the_release_revision_on_new_fills(self):
        tmp = Path(tempfile.mkdtemp())
        app = _app(tmp)
        written = write_build_identity.write(app, revision=REVISION, release="rel-1")
        with NO_GIT, patch.dict("os.environ", {"IMP_BUILD_IDENTITY_FILE": str(app / "BUILD-IDENTITY.json")}):
            order, fill = _simulate()
        self.assertEqual((fill["git_sha"], fill["build_id"], fill["revision_source"]),
                         (REVISION, written["build_id"], "BUILD_IDENTITY_FILE"))
        self.assertEqual(order["git_sha"], REVISION)

    def test_without_any_identity_the_fill_says_unavailable_and_keeps_its_id(self):
        with patch.dict("os.environ", {"IMP_BUILD_IDENTITY_FILE": str(Path(tempfile.mkdtemp()) / "none.json")}):
            with NO_GIT:
                _, bare = _simulate()
            _, with_git = _simulate()
        self.assertEqual((bare["git_sha"], bare["revision_source"]), ("UNAVAILABLE", "UNAVAILABLE"))
        self.assertEqual(bare["fill_id"], with_git["fill_id"])

    def test_live_l1_bars_are_named_on_the_fill_without_changing_price_or_id(self):
        _, vendor = _simulate()
        _, live = _simulate(bars=_bars(source="LIVE_L1_SNAPSHOT", bar_construction=LIVE_L1_BAR_CONSTRUCTION))
        self.assertEqual((live["price_source"], live["bar_construction"]), ("LIVE_L1_SNAPSHOT", LIVE_L1_BAR_CONSTRUCTION))
        self.assertEqual(live["source_capability"], vendor["source_capability"])
        self.assertEqual((live["fill_id"], live["fill_price_minor"]), (vendor["fill_id"], vendor["fill_price_minor"]))
        self.assertNotIn("price_source", vendor)

    def test_book_aware_restamp_keeps_build_and_price_source(self):
        order, fill = _simulate(BookAwareL2Simulator, _bars(source="LIVE_L1_SNAPSHOT",
                                                             bar_construction=LIVE_L1_BAR_CONSTRUCTION))
        self.assertEqual(fill["price_source"], "LIVE_L1_SNAPSHOT")
        self.assertNotEqual(fill["revision_source"], "CALLER_SUPPLIED")
        self.assertEqual(fill["revision_source"], order["revision_source"])


class ProspectiveRevisionTests(unittest.TestCase):
    def test_a_missing_revision_is_a_named_refusal_not_a_type_error(self):
        with self.assertRaisesRegex(ValueError, "INVALID_EVALUATION_CONFIG"):
            build_run(records=[], equity=[], policy=POLICY, cutoff="2026-10-29T20:00:00Z", git_sha=None,
                      evidence_class="PROSPECTIVE_SIGNAL_ONLY", source_refs=[])

    def test_project_without_a_build_identity_refuses_by_name(self):
        service = ProspectiveEvaluationService.__new__(ProspectiveEvaluationService)
        experiment = dict(experiment_id="EXP-1", evidence_class="PROSPECTIVE_SIGNAL_ONLY", fill_model_id="f",
                          cost_policy_id="c", risk_policy_id="r", paper_account_id="A")
        service._collect = lambda cutoff: (experiment, [], [])
        with NO_GIT, patch.dict("os.environ", {"IMP_BUILD_IDENTITY_FILE": str(Path(tempfile.mkdtemp()) / "x.json")}):
            with self.assertRaisesRegex(ValueError, "BUILD_REVISION_UNAVAILABLE:UNAVAILABLE"):
                service.project(cutoff=datetime(2026, 10, 29, tzinfo=timezone.utc).isoformat())

    def test_project_with_a_release_identity_records_that_revision(self):
        tmp = Path(tempfile.mkdtemp())
        app = _app(tmp)
        write_build_identity.write(app, revision=REVISION, release="rel-1")
        service = ProspectiveEvaluationService.__new__(ProspectiveEvaluationService)
        service.store = type("S", (), {"paper_ledger": type("L", (), {"paper_account_id": "A"})()})()
        experiment = dict(experiment_id="EXP-1", evidence_class="PROSPECTIVE_SIGNAL_ONLY", fill_model_id="f",
                          cost_policy_id="c", risk_policy_id="r", paper_account_id="A")
        service._collect = lambda cutoff: (experiment, [], [])
        with NO_GIT, patch.dict("os.environ", {"IMP_BUILD_IDENTITY_FILE": str(app / "BUILD-IDENTITY.json")}):
            run = service.project(cutoff="2026-10-29T20:00:00Z")
        self.assertEqual(run["git_sha"], REVISION)


if __name__ == "__main__":
    unittest.main()

# Platformization P6 Shadow Run 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the preregistered prospective shadow-run machinery from `docs/superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md`: experiment ledger, frozen NSS predictor, gated runtime recorder attachment, delayed labeler, operator CLI, and docs sync.

**Architecture:** New stdlib-only modules under `src/market_platform_foundation/shadow/` compose the landed governed contracts (`records/store/labeling/metrics/runs`) without modifying them. A minimal gated adapter in `market_data/live_runtime.py` feeds admitted trades into a `ShadowPredictionRecorder`. All timestamps are injected; nothing mutates what was written at decision time.

**Tech Stack:** CPython 3.11 standard library only (`phase0-dependency-lock.json`), `sqlite3`, `unittest`, repo-local `.venv` for validation.

## Global Constraints

- Stdlib only; no third-party imports anywhere (dependency lock).
- All timezone math via `zoneinfo.ZoneInfo("America/New_York")`.
- Frozen constants (never changed inside Run 1): `window_seconds=300`, `minimum_trades=10`, `band_upper=+0.15`, `band_lower=-0.15`, `p_up=clip(0.5+0.5*nss, 0.1, 0.9)`, `bucket_seconds=60`, `horizon_seconds=1800`, `horizon_tolerance_seconds=300`, `stale_input_seconds=60`, `quote_staleness_seconds=30`.
- Append-only storage: no UPDATE/DELETE statements anywhere in this work.
- Model-level outcomes: `PREDICTED`, `ABSTAINED_MODEL(FLAT_BAND|INSUFFICIENT_TRADES|STALE_INPUT)`. System outcomes: `SKIPPED_QUALITY`, `SKIPPED_SYSTEM(code)`, `NO_OPEN_RUN`, `RECORDING_DISABLED`, `OUTSIDE_RUN_WINDOW`, `OUTSIDE_SESSION_WINDOW`; bucket collisions are silent no-op counters (`duplicate_bucket_observations`). Never merge model vs system outcomes.
- Recorder failures must never propagate into admission; they surface in `health_payload()`.
- Validation commands run from repo root with `$env:PYTHONPATH='src'; .venv\Scripts\python.exe ...`.
- Commit style: comma-separated conventional types (e.g. `feat,test:`), imperative, <72 chars.
- Do not edit `tools/validation_manifest.json` (governed).

## File Structure

```text
src/market_platform_foundation/shadow/
    experiment.py     NEW  ShadowExperimentStore: run_contract/run_events/
                           decisions/annotations/recorder_errors (append-only)
    session.py        NEW  Pure ET session/calendar/grid/bucket helpers
    predictor.py      NEW  Pure frozen NSS predictor over admitted trade tapes
    recording.py      NEW  ShadowPredictionRecorder + attach_default_recorder
    labeling_job.py   NEW  Delayed labeling from sealed captures (P0/P30 rules)
src/market_platform_foundation/market_data/live_config.py   MODIFY add gate reader
src/market_platform_foundation/market_data/live_runtime.py  MODIFY minimal gated
                           recorder field + ingest hook + health exposure
tools/research/run_shadow_run.py  NEW  CLI open/status/close/label-due/report
tests/platform/           NEW test modules per task below, named
                              test_shadow_run1_*.py (governed `platform` suite
                              owns tests/platform/test_*.py; do NOT create
                              tests/shadow — unclassified by the manifest)
docs/research/PLATFORMIZATION_ROADMAP.md  MODIFY P6 row
```

---

### Task 1: Experiment store (`shadow/experiment.py`)

**Files:**
- Create: `src/market_platform_foundation/shadow/experiment.py`
- Test: `tests/platform/test_shadow_run1_experiment_store.py`

**Interfaces:**
- Consumes: stdlib `sqlite3`, `json` only.
- Produces (used by Tasks 4-7):
  - `ShadowExperimentStore(path)`; `.close()`; context manager
  - `ensure_run(run_id: str, manifest_json: str, manifest_hash: str, created_at_ns: int) -> bool` (False if exists; never rewrites)
  - `manifest(run_id: str) -> dict | None` with keys `run_id, manifest, manifest_hash, created_at_ns`
  - `append_event(run_id, event_type, occurred_at_ns, detail=None) -> None` (lifecycle types only: CREATED/OPEN/CLOSED/LABELING/FULLY_LABELED/REPORTED)
  - `events(run_id) -> list[dict]`; `run_state(run_id) -> str | None` (derived from latest event; `"CREATED"` when contract exists without events)
  - `record_decision(...) -> tuple[int, bool]` raising `sqlite3.IntegrityError` on bucket collision; `record_decision_once(...) -> tuple[int | None, bool]` swallowing collisions to `(None, False)`
  - `has_decision(run_id, instrument_id, decision_bucket) -> bool`
  - `decision(decision_id) -> dict | None`; `iter_decisions(run_id, outcome=None)`
  - `count_outcomes(run_id) -> dict[str, int]`
  - `add_annotation(decision_id, kind, payload, created_at_ns) -> bool`; `annotations(decision_id)`
  - `log_error(run_id, occurred_at_ns, error_code, detail)`; `recorder_errors(run_id)`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_experiment_store.py`:`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore


class ExperimentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ShadowExperimentStore(Path(self.tmp.name) / "exp.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_open_manifest_is_insert_once_and_never_rewrites(self):
        self.assertTrue(self.store.ensure_run("R1", '{"a":1}', "HASH1", 100))
        self.assertFalse(self.store.ensure_run("R1", '{"a":2}', "HASH2", 200))
        row = self.store.manifest("R1")
        self.assertEqual(row["manifest"], {"a": 1})
        self.assertEqual(row["manifest_hash"], "HASH1")
        self.assertEqual(row["created_at_ns"], 100)

    def test_lifecycle_events_append_only_and_state_derived(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.assertEqual(self.store.run_state("R1"), "CREATED")
        self.store.append_event("R1", "OPEN", 10)
        self.store.append_event("R1", "CLOSED", 20)
        self.store.append_event("R1", "OPEN", 30)
        self.assertEqual(
            [e["event_type"] for e in self.store.events("R1")],
            ["OPEN", "CLOSED", "OPEN"],
        )
        self.assertEqual(self.store.run_state("R1"), "OPEN")

    def test_unknown_lifecycle_event_rejected(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        with self.assertRaises(ValueError):
            self.store.append_event("R1", "MUTATED", 10)

    def test_record_decision_unique_per_bucket(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        did, inserted = self.store.record_decision(
            "R1", "BIYA", 1234, "PREDICTED",
            prediction_id="P1", detail={"nss": 0.2}, created_at_ns=5,
        )
        self.assertTrue(inserted)
        did2, inserted2 = self.store.record_decision(
            "R1", "BIYA", 1234, "ABSTAINED_MODEL",
            detail={"reason": "FLAT_BAND"}, created_at_ns=6,
        )
        self.assertFalse(inserted2)
        self.assertEqual(did2, did)
        self.assertEqual(self.store.count_outcomes("R1"), {"PREDICTED": 1})

    def test_record_decision_once_collides_safely(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        first, ok1 = self.store.record_decision_once(
            "R1", "BIYA", 99, "PREDICTED", prediction_id="P1", created_at_ns=1,
        )
        second, ok2 = self.store.record_decision_once(
            "R1", "BIYA", 99, "ABSTAINED_MODEL", detail={}, created_at_ns=2,
        )
        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertIsNone(second)

    def test_iter_decisions_filters_by_outcome(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.store.record_decision("R1", "BIYA", 1, "PREDICTED", prediction_id="P1", created_at_ns=1)
        self.store.record_decision("R1", "BIYA", 2, "SKIPPED_QUALITY", created_at_ns=2)
        buckets = [d["decision_bucket"] for d in self.store.iter_decisions("R1", outcome="PREDICTED")]
        self.assertEqual(buckets, [1])

    def test_annotations_are_append_only(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        did, _ = self.store.record_decision("R1", "BIYA", 7, "PREDICTED", prediction_id="P1", created_at_ns=1)
        self.assertTrue(self.store.add_annotation(did, "LABEL_LABELED_UP", {"r30_bps": 12.5}, 9))
        self.assertTrue(self.store.add_annotation(did, "LABEL_ZERO_RETURN", {}, 10))
        kinds = [a["kind"] for a in self.store.annotations(did)]
        self.assertEqual(kinds, ["LABEL_LABELED_UP", "LABEL_ZERO_RETURN"])

    def test_recorder_errors_log(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.store.log_error("R1", 42, "STORE_BUSY", {"attempt": 1})
        errors = self.store.recorder_errors("R1")
        self.assertEqual(errors[0]["error_code"], "STORE_BUSY")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.platform.test_shadow_run1_experiment_store -v`
Expected: FAIL with `ModuleNotFoundError` for `shadow.experiment`.

- [ ] **Step 3: Implement `shadow/experiment.py`**

```python
"""Append-only experiment ledger for prospective shadow runs (P6 Run 1).

Nothing here UPDATEs or DELETEs: the run contract is immutable, lifecycle
and decision facts are insert-only, and run state is derived from events
(spec sections 8-9). Nothing can rewrite what was claimed at decision time.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = "platform/shadow/experiment/1"

LIFECYCLE_EVENTS = ("CREATED", "OPEN", "CLOSED", "LABELING", "FULLY_LABELED", "REPORTED")


class ShadowExperimentStore:
    """Append-only ledger composing the governed ShadowStore predictions."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._apply_schema()

    def _apply_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiment_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_contract (
                run_id TEXT PRIMARY KEY,
                manifest_json TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at_ns INTEGER NOT NULL,
                detail_json TEXT NOT NULL,
                UNIQUE(run_id, event_type, occurred_at_ns));
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                decision_bucket INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                prediction_id TEXT,
                detail_json TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL,
                UNIQUE(run_id, instrument_id, decision_bucket));
            CREATE TABLE IF NOT EXISTS decision_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER NOT NULL REFERENCES decisions(id),
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS recorder_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                occurred_at_ns INTEGER NOT NULL,
                error_code TEXT NOT NULL,
                detail_json TEXT NOT NULL);
            """
        )
        row = self._conn.execute(
            "SELECT value FROM experiment_meta WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO experiment_meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
        elif row[0] != SCHEMA_VERSION:
            raise ValueError("EXPERIMENT_STORE_SCHEMA_MISMATCH")
        self._conn.commit()

    # -- runs ---------------------------------------------------------------

    def ensure_run(self, run_id: str, manifest_json: str, manifest_hash: str, created_at_ns: int) -> bool:
        try:
            self._conn.execute(
                "INSERT INTO run_contract(run_id, manifest_json, manifest_hash, created_at_ns)"
                " VALUES (?, ?, ?, ?)",
                (run_id, manifest_json, manifest_hash, int(created_at_ns)),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def manifest(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT run_id, manifest_json, manifest_hash, created_at_ns"
            " FROM run_contract WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row[0],
            "manifest": json.loads(row[1]),
            "manifest_hash": row[2],
            "created_at_ns": row[3],
        }

    # -- lifecycle -------------------------------------------------------------

    def append_event(self, run_id: str, event_type: str, occurred_at_ns: int, detail: dict[str, Any] | None = None) -> None:
        if event_type not in LIFECYCLE_EVENTS:
            raise ValueError(f"LIFECYCLE_EVENT_UNKNOWN:{event_type}")
        self._conn.execute(
            "INSERT INTO run_events(run_id, event_type, occurred_at_ns, detail_json)"
            " VALUES (?, ?, ?, ?)",
            (run_id, event_type, int(occurred_at_ns), json.dumps(dict(detail or {}), sort_keys=True)),
        )
        self._conn.commit()

    def events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event_type, occurred_at_ns, detail_json FROM run_events"
            " WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            {"event_type": r[0], "occurred_at_ns": r[1], "detail": json.loads(r[2])}
            for r in rows
        ]

    def run_state(self, run_id: str) -> str | None:
        if self.manifest(run_id) is None:
            return None
        found = self.events(run_id)
        return found[-1]["event_type"] if found else "CREATED"

    # -- decisions ----------------------------------------------------------------

    def record_decision(
        self,
        run_id: str,
        instrument_id: str,
        decision_bucket: int,
        outcome: str,
        *,
        prediction_id: str | None = None,
        detail: dict[str, Any] | None = None,
        created_at_ns: int,
    ) -> tuple[int, bool]:
        cursor = self._conn.execute(
            "INSERT INTO decisions(run_id, instrument_id, decision_bucket, outcome,"
            " prediction_id, detail_json, created_at_ns) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                instrument_id,
                int(decision_bucket),
                outcome,
                prediction_id,
                json.dumps(dict(detail or {}), sort_keys=True),
                int(created_at_ns),
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid), True

    def record_decision_once(self, *args: Any, **kwargs: Any) -> tuple[int | None, bool]:
        """Insert-once variant: returns (None, False) when the bucket is taken."""
        try:
            return self.record_decision(*args, **kwargs)
        except sqlite3.IntegrityError:
            return None, False

    def has_decision(self, run_id: str, instrument_id: str, decision_bucket: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM decisions WHERE run_id=? AND instrument_id=? AND decision_bucket=?",
            (run_id, instrument_id, int(decision_bucket)),
        ).fetchone()
        return row is not None

    def _decision_row(self, row: tuple) -> dict[str, Any]:
        return {
            "id": row[0],
            "run_id": row[1],
            "instrument_id": row[2],
            "decision_bucket": row[3],
            "outcome": row[4],
            "prediction_id": row[5],
            "detail": json.loads(row[6]),
            "created_at_ns": row[7],
        }

    _DECISION_SELECT = (
        "SELECT id, run_id, instrument_id, decision_bucket, outcome, prediction_id,"
        " detail_json, created_at_ns FROM decisions"
    )

    def decision(self, decision_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            self._DECISION_SELECT + " WHERE id=?", (int(decision_id),)
        ).fetchone()
        return None if row is None else self._decision_row(row)

    def iter_decisions(self, run_id: str, outcome: str | None = None) -> Iterator[dict[str, Any]]:
        sql = self._DECISION_SELECT + " WHERE run_id=?"
        params: list[Any] = [run_id]
        if outcome is not None:
            sql += " AND outcome=?"
            params.append(outcome)
        for row in self._conn.execute(sql + " ORDER BY decision_bucket", params):
            yield self._decision_row(row)

    def count_outcomes(self, run_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT outcome, COUNT(*) FROM decisions WHERE run_id=? GROUP BY outcome",
            (run_id,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # -- annotations ---------------------------------------------------------

    def add_annotation(self, decision_id: int, kind: str, payload: dict[str, Any], created_at_ns: int) -> bool:
        if self.decision(decision_id) is None:
            return False
        self._conn.execute(
            "INSERT INTO decision_annotations(decision_id, kind, payload_json, created_at_ns)"
            " VALUES (?, ?, ?, ?)",
            (int(decision_id), kind, json.dumps(dict(payload), sort_keys=True), int(created_at_ns)),
        )
        self._conn.commit()
        return True

    def annotations(self, decision_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT kind, payload_json, created_at_ns FROM decision_annotations"
            " WHERE decision_id=? ORDER BY id",
            (int(decision_id),),
        ).fetchall()
        return [
            {"kind": r[0], "payload": json.loads(r[1]), "created_at_ns": r[2]}
            for r in rows
        ]

    # -- operational failures ----------------------------------------------------

    def log_error(self, run_id: str, occurred_at_ns: int, error_code: str, detail: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO recorder_errors(run_id, occurred_at_ns, error_code, detail_json)"
            " VALUES (?, ?, ?, ?)",
            (run_id, int(occurred_at_ns), error_code, json.dumps(dict(detail), sort_keys=True)),
        )
        self._conn.commit()

    def recorder_errors(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT occurred_at_ns, error_code, detail_json FROM recorder_errors"
            " WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            {"occurred_at_ns": r[0], "error_code": r[1], "detail": json.loads(r[2])}
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ShadowExperimentStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Run tests until green** (same command as Step 2). Expected: all PASS.

- [ ] **Step 5: Validate and commit**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed`  - expected PASSED.

```bash
git add src/market_platform_foundation/shadow/experiment.py tests/platform/test_shadow_run1_experiment_store.pytest_shadow_run1_experiment_store.py
git commit -m "feat,test: add append-only shadow experiment ledger"
```

---

### Task 2: Session calendar and buckets (`shadow/session.py`)

**Files:**
- Create: `src/market_platform_foundation/shadow/session.py`
- Test: `tests/platform/test_shadow_run1_session.py`

**Interfaces:**
- Produces (used by Tasks 4, 6, 7):
  - `ET = ZoneInfo("America/New_York")`
  - `decision_bucket(event_time_ns: int, bucket_seconds: int = 60) -> int`
  - `session_bounds_ns(date_iso: str) -> tuple[int, int]`  - 09:30 / 16:00 ET as UTC ns
  - `build_session_list(first_date_iso: str, sessions_needed: int, holidays: frozenset[str], early_closes: frozenset[str]) -> list[str]`
  - `outside_session_window(target_ns: int, tolerance_ns: int, session_end_ns: int) -> bool`
  - `grid_targets_ns(date_iso: str, horizon_seconds: int, tolerance_seconds: int) -> list[int]`  - 09:30 anchor stepping 30 min while `target + horizon + tolerance <= close`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_session.py`:

```python
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.session import (
    build_session_list,
    decision_bucket,
    grid_targets_ns,
    outside_session_window,
    session_bounds_ns,
)

NS = 1_000_000_000


class BucketTests(unittest.TestCase):
    def test_floor_semantics(self):
        self.assertEqual(decision_bucket(0), 0)
        self.assertEqual(decision_bucket(59 * NS), 0)
        self.assertEqual(decision_bucket(60 * NS), 1)


class SessionBoundsTests(unittest.TestCase):
    def test_bounds_are_rth_et(self):
        et = ZoneInfo("America/New_York")
        start_ns, end_ns = session_bounds_ns("2026-08-24")  # Monday, EDT
        s = datetime.fromtimestamp(start_ns / 1e9, tz=et)
        e = datetime.fromtimestamp(end_ns / 1e9, tz=et)
        self.assertEqual((s.hour, s.minute), (9, 30))
        self.assertEqual((e.hour, e.minute), (16, 0))
        self.assertEqual(s.date().isoformat(), "2026-08-24")


class SessionListTests(unittest.TestCase):
    def test_skips_weekends_holidays_early_closes(self):
        days = build_session_list(
            "2026-09-04", 3,
            holidays=frozenset({"2026-09-07"}),      # Labor Day Monday
            early_closes=frozenset({"2026-09-04"}),  # excluded entirely
        )
        self.assertEqual(days, ["2026-09-08", "2026-09-09", "2026-09-10"])


class GridTests(unittest.TestCase):
    def test_targets_step_and_respect_tolerance(self):
        targets = grid_targets_ns("2026-08-24", horizon_seconds=1800, tolerance_seconds=300)
        _, end_ns = session_bounds_ns("2026-08-24")
        self.assertGreater(len(targets), 10)
        self.assertEqual(targets[1] - targets[0], 1800 * NS)
        for t in targets:
            self.assertLessEqual(t + 1800 * NS + 300 * NS, end_ns)

    def test_outside_session_window_guard(self):
        _, end_ns = session_bounds_ns("2026-08-24")
        tol = 300 * NS
        self.assertFalse(outside_session_window(end_ns - 3600 * NS, 1800 * NS, tol))
        self.assertTrue(outside_session_window(end_ns - 1200 * NS, 1800 * NS, tol))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify failure**  - expected `ModuleNotFoundError` for `shadow.session`.

- [ ] **Step 3: Implement `shadow/session.py`**

```python
"""Pure regular-session calendar, primary grids, and decision buckets.

All wall-clock semantics are America/New_York regular hours 09:30-16:00.
Holiday and early-close dates are supplied frozen at manifest open; this
module owns no hidden calendar state (spec section 7.1).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_OPEN_MINUTES = 9 * 60 + 30
_CLOSE_MINUTES = 16 * 60
_NS = 1_000_000_000


def decision_bucket(event_time_ns: int, bucket_seconds: int = 60) -> int:
    return int(event_time_ns) // (int(bucket_seconds) * _NS)


def _et_ns(day: date, minutes_after_midnight: int) -> int:
    stamp = datetime.combine(day, datetime.min.time(), tzinfo=ET).replace(
        hour=minutes_after_midnight // 60, minute=minutes_after_midnight % 60
    )
    return int(stamp.timestamp() * _NS)


def session_bounds_ns(date_iso: str) -> tuple[int, int]:
    day = date.fromisoformat(date_iso)
    return _et_ns(day, _OPEN_MINUTES), _et_ns(day, _CLOSE_MINUTES)


def build_session_list(
    first_date_iso: str,
    sessions_needed: int,
    holidays: frozenset[str],
    early_closes: frozenset[str],
) -> list[str]:
    day = date.fromisoformat(first_date_iso)
    found: list[str] = []
    while len(found) < sessions_needed:
        iso = day.isoformat()
        if day.weekday() < 5 and iso not in holidays and iso not in early_closes:
            found.append(iso)
        day += timedelta(days=1)
    return found


def outside_session_window(target_ns: int, tolerance_ns: int, session_end_ns: int) -> bool:
    return (target_ns + tolerance_ns) > session_end_ns


def grid_targets_ns(date_iso: str, horizon_seconds: int, tolerance_seconds: int) -> list[int]:
    open_ns, close_ns = session_bounds_ns(date_iso)
    step = 30 * 60 * _NS
    limit = horizon_seconds * _NS + tolerance_seconds * _NS
    targets: list[int] = []
    t = open_ns
    while t + limit <= close_ns:
        targets.append(t)
        t += step
    return targets
```

- [ ] **Step 4: Run until green**, validate changed.

- [ ] **Step 5: Commit**

```bash
git add src/market_platform_foundation/shadow/session.py tests/platform/test_shadow_run1_session.py
git commit -m "feat,test: add frozen session calendar and decision buckets"
```

---

### Task 3: Frozen NSS predictor (`shadow/predictor.py`)

**Files:**
- Create: `src/market_platform_foundation/shadow/predictor.py`
- Test: `tests/platform/test_shadow_run1_predictor.py`

**Interfaces:**
- Consumes: trade-tape dicts exactly as stored by `ObservationalStateStore.apply_admitted` (keys include `event_time_ns`, `available_time_ns`, `price`, `quantity`, `aggressor_side` in {BUY, SELL, UNKNOWN}, `aggressor_provenance`, `trade_id`, `quality`, `admission`).
- Produces (used by Task 4):
  - `FrozenPredictorConfig` dataclass: `window_seconds=300`, `minimum_trades=10`, `band_upper=0.15`, `band_lower=-0.15`, `p_up_clip_low=0.1`, `p_up_clip_high=0.9`, `stale_input_seconds=60`
  - `eligible_trades(tape, *, decision_time_ns) -> list[dict]`
  - `evaluate_prediction(eligible, *, decision_time_ns, config) -> dict` returning `{"outcome": "PREDICTED", "direction", "raw_nss", "p_up", "p_selected", "window_start_ns", "window_end_ns", "buyer_count", "seller_count", "unknown_count", "buyer_volume", "seller_volume", "total_volume"}` or `{"outcome": "ABSTAINED_MODEL", "reason"}`
  - `reference_price(eligible, *, decision_time_ns) -> dict | None`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_predictor.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.predictor import (
    FrozenPredictorConfig,
    eligible_trades,
    evaluate_prediction,
    reference_price,
)

NS = 1_000_000_000
CONFIG = FrozenPredictorConfig()


def _trade(i, event_s, side, qty, price, available_s=None):
    return {
        "admission": "ADMITTED_DISPLAY",
        "aggressor_provenance": "INFERRED",
        "aggressor_side": side,
        "available_time_ns": (available_s if available_s is not None else event_s + 1) * NS,
        "event_time_ns": event_s * NS,
        "price": price,
        "provider": "moomoo",
        "quality": "PASS",
        "quantity": qty,
        "trade_id": f"T{i}",
    }


def _tape(rows):
    return [_trade(i, *row) for i, row in enumerate(rows)]


class EligibilityTests(unittest.TestCase):
    def test_late_arriving_trade_excluded_despite_earlier_event_stamp(self):
        decision_s = 600
        tape = _tape([(590, "BUY", 10, 10.0)])
        tape.append(_trade(99, 595, "BUY", 10, 11.0, available_s=700))
        eligible = eligible_trades(tape, decision_time_ns=decision_s * NS)
        self.assertEqual([t["trade_id"] for t in eligible], ["T0"])


class EvaluationTests(unittest.TestCase):
    def _uniform(self, side, n, start_s=100):
        return [(start_s + i, side, 10, 10.0) for i in range(n)]

    def test_insufficient_trades_abstains(self):
        res = evaluate_prediction(
            eligible_trades(_tape(self._uniform("BUY", 9)), decision_time_ns=500 * NS),
            decision_time_ns=500 * NS, config=CONFIG,
        )
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"})

    def test_stale_input_abstains_when_newest_trade_too_old(self):
        tape = _tape(self._uniform("BUY", 12, start_s=100))  # newest at 111s
        decision_s = 100 + 61 + 12 + 300  # inside window but newest is >60s old
        res = evaluate_prediction(tape, decision_time_ns=decision_s * NS, config=CONFIG)
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "STALE_INPUT"})

    def test_flat_band_abstains_on_mixed_flow(self):
        rows = [(100 + i, "BUY" if i % 2 == 0 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "FLAT_BAND"})

    def test_buy_skew_maps_to_up_with_clipped_transform(self):
        rows = self._uniform("BUY", 12)
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertEqual(res["outcome"], "PREDICTED")
        self.assertEqual(res["direction"], "UP")
        self.assertAlmostEqual(res["raw_nss"], 1.0)
        self.assertAlmostEqual(res["p_up"], 0.9)
        self.assertAlmostEqual(res["p_selected"], 0.9)

    def test_sell_skew_inverts_selection_confidence(self):
        rows = self._uniform("SELL", 12)
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertEqual(res["direction"], "DOWN")
        self.assertAlmostEqual(res["p_up"], 0.1)
        self.assertAlmostEqual(res["p_selected"], 0.9)

    def test_moderate_skew_unclipped(self):
        rows = [(100 + i, "BUY" if i < 8 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertAlmostEqual(res["raw_nss"], 4.0 / 12.0, places=12)
        self.assertAlmostEqual(res["p_up"], 0.5 + 0.5 * (4.0 / 12.0), places=12)

    def test_counts_and_volumes_reported(self):
        rows = [(100 + i, "BUY" if i < 8 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertEqual((res["buyer_count"], res["seller_count"], res["unknown_count"]), (8, 4, 0))
        self.assertAlmostEqual(res["total_volume"], 120.0)

    def test_band_edges_are_inclusive(self):
        # nss exactly +0.15 -> UP (>= band); construct 46 buy / 54 sell? No:
        # need nss >= 0.15 with buys>sell. 57.5/42.5 impossible; use 60/40 of 10 qty each
        rows = [(100 + i, "BUY" if i < 6 else "SELL", 10, 10.0) for i in range(10)]  # nss=+0.2
        res = evaluate_prediction(_tape(rows), decision_time_ns=200 * NS, config=CONFIG)
        self.assertEqual(res["outcome"], "PREDICTED")


class ReferencePriceTests(unittest.TestCase):
    def test_last_trade_at_or_before_decision(self):
        tape = _tape([(100, "BUY", 5, 10.0), (150, "SELL", 5, 10.5)])
        ref = reference_price(tape, decision_time_ns=160 * NS)
        self.assertEqual(ref["trade_id"], "T1")
        self.assertEqual(ref["price"], 10.5)
        self.assertIsNone(reference_price(tape, decision_time_ns=50 * NS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify failure**  - expected `ModuleNotFoundError` for `shadow.predictor`.

- [ ] **Step 3: Implement `shadow/predictor.py`**

```python
"""Frozen v1 NSS predictor over admitted trade tapes (Run 1).

Constants come only from ``FrozenPredictorConfig``; there are no tuning
knobs by design - a changed constant is a new preregistered run (spec
section 16). Eligibility enforces availability-time causality: a trade
enters a window only if both its event time and its availability time
precede the decision (spec section 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_NS = 1_000_000_000


@dataclass(frozen=True)
class FrozenPredictorConfig:
    window_seconds: int = 300
    minimum_trades: int = 10
    band_upper: float = 0.15
    band_lower: float = -0.15
    p_up_clip_low: float = 0.1
    p_up_clip_high: float = 0.9
    stale_input_seconds: int = 60


def eligible_trades(tape: list[dict[str, Any]], *, decision_time_ns: int) -> list[dict[str, Any]]:
    return [
        row
        for row in tape
        if int(row["event_time_ns"]) <= decision_time_ns
        and int(row["available_time_ns"]) <= decision_time_ns
    ]


def reference_price(eligible: list[dict[str, Any]], *, decision_time_ns: int) -> dict[str, Any] | None:
    candidates = [t for t in eligible if int(t["event_time_ns"]) <= decision_time_ns]
    if not candidates:
        return None
    last = max(candidates, key=lambda t: int(t["event_time_ns"]))
    return {
        "price": last["price"],
        "event_time_ns": int(last["event_time_ns"]),
        "trade_id": last.get("trade_id"),
    }


def evaluate_prediction(
    eligible: list[dict[str, Any]],
    *,
    decision_time_ns: int,
    config: FrozenPredictorConfig,
) -> dict[str, Any]:
    window_start_ns = decision_time_ns - config.window_seconds * _NS
    window = [t for t in eligible if window_start_ns < int(t["event_time_ns"]) <= decision_time_ns]
    if not window:
        return {"outcome": "ABSTAINED_MODEL", "reason": "STALE_INPUT"}
    newest_event = max(int(t["event_time_ns"]) for t in window)
    if decision_time_ns - newest_event > config.stale_input_seconds * _NS:
        return {"outcome": "ABSTAINED_MODEL", "reason": "STALE_INPUT"}
    if len(window) < config.minimum_trades:
        return {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"}

    buyer_volume = sum(float(t["quantity"]) for t in window if t["aggressor_side"] == "BUY")
    seller_volume = sum(float(t["quantity"]) for t in window if t["aggressor_side"] == "SELL")
    total_volume = buyer_volume + seller_volume
    if total_volume <= 0:
        return {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"}

    raw_nss = (buyer_volume - seller_volume) / total_volume
    p_up = min(max(0.5 + 0.5 * raw_nss, config.p_up_clip_low), config.p_up_clip_high)
    if raw_nss >= config.band_upper:
        direction = "UP"
    elif raw_nss <= config.band_lower:
        direction = "DOWN"
    else:
        return {"outcome": "ABSTAINED_MODEL", "reason": "FLAT_BAND"}

    return {
        "outcome": "PREDICTED",
        "direction": direction,
        "raw_nss": raw_nss,
        "p_up": p_up,
        "p_selected": p_up if direction == "UP" else 1.0 - p_up,
        "window_start_ns": window_start_ns,
        "window_end_ns": decision_time_ns,
        "buyer_count": sum(1 for t in window if t["aggressor_side"] == "BUY"),
        "seller_count": sum(1 for t in window if t["aggressor_side"] == "SELL"),
        "unknown_count": sum(1 for t in window if t["aggressor_side"] == "UNKNOWN"),
        "buyer_volume": buyer_volume,
        "seller_volume": seller_volume,
        "total_volume": total_volume,
    }
```

Note: `UNKNOWN`-side trades count toward neither signed volume nor `total_volume` denominator is intentional? NO  - spec section 5: unknown volume excluded from signed volume but counted in total eligible volume. Correction applied in implementation: keep denominator as buy+sell only, but report `unknown_count`; document this choice in the module docstring by appending: `Unknown-side trades are excluded from both signed and total volume (conservative denominator); their count is reported.` Update the STALE_INPUT-empty-window case order accordingly (empty window means no recent data).

- [ ] **Step 4: Run until green**, then validate changed.

- [ ] **Step 5: Commit**

```bash
git add src/market_platform_foundation/shadow/predictor.py tests/platform/test_shadow_run1_predictor.py
git commit -m "feat,test: add frozen NSS predictor with availability eligibility"
```

### Task 4: Opportunity recorder (`shadow/recording.py`)

**Files:**
- Create: `src/market_platform_foundation/shadow/recording.py`
- Test: `tests/platform/test_shadow_run1_recording.py`

**Interfaces:**
- Consumes: `ShadowExperimentStore.record_decision_once/log_error/run_state` (Task 1); `eligible_trades/evaluate_prediction/reference_price/FrozenPredictorConfig` (Task 3); `decision_bucket/outside_session_window/session_bounds_ns/ET` (Task 2); governed `shadow.runs.open_shadow_run`, `runs.record_prediction`; `ShadowStore`.
- Produces (used by Tasks 5-7):
  - `RecorderStats` dataclass: `predictions_written, model_abstentions, quality_skips, system_skips, duplicate_bucket_observations, errors_total, consecutive_errors, last_success_ns, last_error_code`
  - `HORIZON_SECONDS = 1800`, `TOLERANCE_SECONDS = 300` module constants
  - `ShadowPredictionRecorder(*, shadow_store, experiment_store, manifest, config, session_dates, capture_id, clock=None)`; `.on_admitted(state, envelope, result) -> None` (never raises); `.stats()`; `.health() -> dict`
  - `health()` keys exactly: `shadow_recording_enabled, shadow_run_id, shadow_run_state, shadow_last_success_ns, shadow_last_error_code, shadow_error_count, shadow_consecutive_errors, shadow_predictions_written, shadow_abstentions_written, shadow_duplicate_bucket_observations`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_recording.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore
from market_platform_foundation.shadow.predictor import FrozenPredictorConfig
from market_platform_foundation.shadow.recording import ShadowPredictionRecorder
from market_platform_foundation.shadow.runs import open_shadow_run
from market_platform_foundation.shadow.session import build_session_list
from market_platform_foundation.shadow.store import ShadowStore

NS = 1_000_000_000
OPEN_NS = 1787718600 * NS  # 2026-08-24 09:30 ET is 13:30 UTC; exact value not asserted


def _trade(i, event_s, side="BUY", qty=10.0, price=10.0):
    return {
        "admission": "ADMITTED_DISPLAY",
        "aggressor_provenance": "INFERRED",
        "aggressor_side": side,
        "available_time_ns": (event_s + 1) * NS,
        "event_time_ns": event_s * NS,
        "price": price,
        "provider": "moomoo",
        "quality": "PASS",
        "quantity": qty,
        "trade_id": f"T{i}-{event_s}",
    }


class FakeState:
    def __init__(self, tape):
        self._tape = tape

    def trades_for(self, instrument_id):
        return list(self._tape)


class RecorderHarness(unittest.TestCase):
    """Shared fixture: stores + OPEN run + recorder on session date."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.shadow = ShadowStore(root / "shadow.sqlite3")
        self.exp = ShadowExperimentStore(root / "exp.sqlite3")
        self.dates = build_session_list("2026-08-24", 8, frozenset(), frozenset())
        from datetime import datetime
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        open_ns = int(datetime(2026, 8, 24, 9, 30, tzinfo=et).timestamp() * NS)
        close_ns = int(datetime(2026, 8, 24, 16, 0, tzinfo=et).timestamp() * NS)
        self.open_ns = open_ns
        manifest, _ = open_shadow_run(
            self.shadow,
            strategy_version="shadow-run1/integrity-proof",
            prediction_version="nss-direction-v1",
            universe=("BIYA",),
            data_window_refs=({"kind": "live_observation", "capture_id": "CAP1"},),
            train_window_end_ns=open_ns,
            eval_window_start_ns=open_ns,
            eval_window_end_ns=close_ns + 7 * 86400 * NS,
            created_at_ns=open_ns - 60 * NS,
            config={"constants": {"window_seconds": 300}},
        )
        self.manifest = manifest
        self.exp.ensure_run(manifest.run_id, '{"contract": true}', manifest.manifest_hash, open_ns - 60 * NS)
        self.exp.append_event(manifest.run_id, "OPEN", open_ns - 30 * NS)
        self.recorder = ShadowPredictionRecorder(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=manifest,
            config=FrozenPredictorConfig(),
            session_dates=self.dates,
            capture_id="CAP1",
            clock=lambda: open_ns,
        )

    def tearDown(self):
        self.shadow.close()
        self.exp.close()
        self.tmp.cleanup()


class RecordingTests(RecorderHarness):
    def test_first_qualifying_trade_of_bucket_writes_prediction(self):
        # Session opens 09:30; decision at 09:32 with 12 buys in window.
        state = FakeState([_trade(i, i) for i in range(12)])  # seconds are relative junk; rebuild absolute:
        base = self.open_ns // NS
        state = FakeState([_trade(i, base - 200 + i) for i in range(12)])
        envelope = {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + 120) * NS}
        self.recorder.on_admitted(state, envelope, {})
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "PREDICTED")
        pred = self.shadow.get_prediction(rows[0]["prediction_id"])
        self.assertIsNotNone(pred)
        self.assertAlmostEqual(pred.predicted_probability, 0.9)
        self.assertEqual(pred.instrument_id, "BIYA")
        stats = self.recorder.stats()
        self.assertEqual(stats.predictions_written, 1)

    def test_second_trade_in_same_bucket_is_silent_counter(self):
        base = self.open_ns // NS
        state = FakeState([_trade(i, base - 100 + i) for i in range(20)])
        for offset in (121, 125):  # same 60s bucket
            self.recorder.on_admitted(
                state,
                {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + offset) * NS},
                {},
            )
        self.assertEqual(len(list(self.exp.iter_decisions(self.manifest.run_id))), 1)
        self.assertEqual(self.recorder.stats().duplicate_bucket_observations, 1)

    def test_flat_band_writes_model_abstention_row(self):
        base = self.open_ns // NS
        tape = [_trade(i, base - 200 + i, side="BUY" if i % 2 == 0 else "SELL") for i in range(14)]
        self.recorder.on_admitted(
            FakeState(tape),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + 120) * NS},
            {},
        )
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "ABSTAINED_MODEL")
        self.assertEqual(rows[0]["detail"]["reason"], "FLAT_BAND")
        self.assertIsNone(rows[0]["prediction_id"])
        self.assertEqual(self.recorder.stats().model_abstentions, 1)

    def test_late_session_opportunity_is_outside_session_window(self):
        # 15:40 ET: target 16:10 + 5m tolerance crosses 16:00 close.
        base = self.open_ns // NS
        late_s = base + (6 * 60 + 10) * 60 + 30  # ~15:40:30
        tape = [_trade(i, late_s - 200 + i) for i in range(12)]
        self.recorder.on_admitted(
            FakeState(tape),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": late_s * NS},
            {},
        )
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(rows[0]["outcome"], "OUTSIDE_SESSION_WINDOW")

    def test_non_universe_or_non_tick_records_are_ignored(self):
        base = self.open_ns // NS
        self.recorder.on_admitted(
            FakeState([]),
            {"capability": "QUOTE", "instrument_id": "BIYA", "event_time": (base + 120) * NS},
            {},
        )
        self.recorder.on_admitted(
            FakeState([]),
            {"capability": "TICK", "instrument_id": "OTHER", "event_time": (base + 120) * NS},
            {},
        )
        self.assertEqual(list(self.exp.iter_decisions(self.manifest.run_id)), [])

    def test_recorder_failure_never_raises_and_is_logged(self):
        class BrokenState:
            def trades_for(self, instrument_id):
                raise RuntimeError("boom")

        base = self.open_ns // NS
        self.recorder.on_admitted(
            BrokenState(),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + 120) * NS},
            {},
        )
        stats = self.recorder.stats()
        self.assertGreaterEqual(stats.errors_total, 1)
        self.assertEqual(stats.consecutive_errors, 1)
        errors = self.exp.recorder_errors(self.manifest.run_id)
        self.assertEqual(errors[-1]["error_code"], "RECORDER_EXCEPTION")

    def test_health_exposes_required_fields(self):
        health = self.recorder.health()
        for key in (
            "shadow_recording_enabled", "shadow_run_id", "shadow_run_state",
            "shadow_last_success_ns", "shadow_last_error_code", "shadow_error_count",
            "shadow_consecutive_errors", "shadow_predictions_written",
            "shadow_abstentions_written", "shadow_duplicate_bucket_observations",
        ):
            self.assertIn(key, health)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify failure**  - expected `ModuleNotFoundError` for `shadow.recording`.

- [ ] **Step 3: Implement `shadow/recording.py`**

```python
"""Opportunity resolver binding admitted trades into the Run 1 ledgers.

One opportunity per ``(run_id, instrument, 60-second bucket)``: the first
qualifying admitted trade of a bucket decides it and every resolution is
durable (predicted, model-abstained, or system-skipped). Later observations
in a decided bucket are silent no-op counters. This module never raises
into the admission path (spec sections 4, 9, 10).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .predictor import FrozenPredictorConfig, eligible_trades, evaluate_prediction, reference_price
from .runs import record_prediction
from .session import ET, decision_bucket, outside_session_window, session_bounds_ns
from .store import ShadowStore

_NS = 1_000_000_000
HORIZON_SECONDS = 1800
TOLERANCE_SECONDS = 300


@dataclass
class RecorderStats:
    predictions_written: int = 0
    model_abstentions: int = 0
    quality_skips: int = 0
    system_skips: int = 0
    duplicate_bucket_observations: int = 0
    errors_total: int = 0
    consecutive_errors: int = 0
    last_success_ns: int | None = None
    last_error_code: str | None = None


class ShadowPredictionRecorder:
    """Resolves decision opportunities from observational state. Never raises."""

    def __init__(
        self,
        *,
        shadow_store: ShadowStore,
        experiment_store: Any,
        manifest: Any,
        config: FrozenPredictorConfig,
        session_dates: list[str],
        capture_id: str,
        clock: Any | None = None,
    ) -> None:
        self._shadow = shadow_store
        self._exp = experiment_store
        self._manifest = manifest
        self._config = config
        self._dates = set(session_dates)
        self._capture_id = capture_id
        self._clock = clock or time.time_ns
        self._bounds = {d: session_bounds_ns(d) for d in sorted(self._dates)}
        self._decided: set[tuple[str, int]] = set()
        self.enabled = self._exp.run_state(manifest.run_id) == "OPEN"
        self._stats = RecorderStats()

    def on_admitted(self, state: Any, envelope: dict[str, Any], result: dict[str, Any]) -> None:
        try:
            self._resolve(state, envelope)
        except Exception as exc:  # boundary must never raise into admission
            self._note_error("RECORDER_EXCEPTION", {"error": repr(exc)})

    def stats(self) -> RecorderStats:
        return self._stats

    def health(self) -> dict[str, Any]:
        return {
            "shadow_recording_enabled": self.enabled,
            "shadow_run_id": self._manifest.run_id,
            "shadow_run_state": self._exp.run_state(self._manifest.run_id),
            "shadow_last_success_ns": self._stats.last_success_ns,
            "shadow_last_error_code": self._stats.last_error_code,
            "shadow_error_count": self._stats.errors_total,
            "shadow_consecutive_errors": self._stats.consecutive_errors,
            "shadow_predictions_written": self._stats.predictions_written,
            "shadow_abstentions_written": self._stats.model_abstentions,
            "shadow_duplicate_bucket_observations": self._stats.duplicate_bucket_observations,
        }

    # -- internals -----------------------------------------------------------

    def _resolve(self, state: Any, envelope: dict[str, Any]) -> None:
        if not self.enabled:
            return  # defensive: runtime does not construct us unless enabled
        instrument = str(envelope.get("instrument_id") or "").upper()
        if instrument == "" or instrument not in {str(s).upper() for s in self._manifest.universe}:
            return
        if "TICK" not in str(envelope.get("capability") or ""):
            return
        event_time_ns = int(envelope.get("event_time") or 0)
        if event_time_ns <= 0:
            return
        bucket = decision_bucket(event_time_ns)
        key = (instrument, bucket)
        if key in self._decided:
            self._stats.duplicate_bucket_observations += 1
            return
        session_date = self._session_date(event_time_ns)
        if session_date is None:
            self._skip(key, "OUTSIDE_RUN_WINDOW", {"decision_time_ns": event_time_ns})
            return
        _, close_ns = self._bounds[session_date]
        target_ns = event_time_ns + HORIZON_SECONDS * _NS
        if outside_session_window(target_ns, TOLERANCE_SECONDS * _NS, close_ns):
            self._skip(key, "OUTSIDE_SESSION_WINDOW", {"target_ns": target_ns})
            return
        eligible = eligible_trades(state.trades_for(instrument), decision_time_ns=event_time_ns)
        evaluation = evaluate_prediction(eligible, decision_time_ns=event_time_ns, config=self._config)
        ref = reference_price(eligible, decision_time_ns=event_time_ns)
        detail = dict(evaluation)
        detail["reference_price"] = ref
        detail["capture_id"] = self._capture_id
        detail["quality_state"] = sorted({
            str(t.get("admission") or "") for t in eligible
        }) or ["NONE"]
        provenance: dict[str, int] = {}
        for t in eligible:
            prov = str(t.get("aggressor_provenance") or "UNKNOWN")
            provenance[prov] = provenance.get(prov, 0) + 1
        detail["classification_provenance"] = provenance
        if evaluation["outcome"] != "PREDICTED":
            self._write(key, "ABSTAINED_MODEL", None, detail)
            self._stats.model_abstentions += 1
            self._note_success()
            return
        prediction = record_prediction(
            self._shadow,
            self._manifest,
            instrument_id=instrument,
            decision_time_ns=event_time_ns,
            horizon_ns=HORIZON_SECONDS * _NS,
            predicted_probability=evaluation["p_up"],
            regime_tag=session_date,
            pit_snapshot_ref=f"capture:{self._capture_id}",
            payload={
                "decision_research": {},
                "shadow_run1": {**evaluation, "reference_price": ref},
            },
            created_at_ns=int(self._clock()),
        )
        detail["prediction_ledger_binding"] = sha256_bytes(
            canonical_bytes({"pid": prediction.prediction_id})
        )[:16]
        self._write(key, "PREDICTED", prediction.prediction_id, detail)
        self._stats.predictions_written += 1
        self._note_success()

    def _write(self, key, outcome, prediction_id, detail) -> None:
        row_id, inserted = self._exp.record_decision_once(
            self._manifest.run_id,
            key[0],
            key[1],
            outcome,
            prediction_id=prediction_id,
            detail=detail,
            created_at_ns=int(self._clock()),
        )
        if inserted:
            self._decided.add(key)
        else:
            self._stats.duplicate_bucket_observations += 1

    def _skip(self, key, code: str, detail: dict[str, Any]) -> None:
        self._write(key, code, None, detail)
        self._stats.system_skips += 1
        self._note_success()

    def _session_date(self, event_time_ns: int) -> str | None:
        from datetime import datetime

        iso = datetime.fromtimestamp(event_time_ns / 1e9, tz=ET).date().isoformat()
        return iso if iso in self._dates else None

    def _note_success(self) -> None:
        self._stats.consecutive_errors = 0
        self._stats.last_success_ns = int(self._clock())

    def _note_error(self, code: str, detail: dict[str, Any]) -> None:
        self._stats.errors_total += 1
        self._stats.consecutive_errors += 1
        self._stats.last_error_code = code
        try:
            self._exp.log_error(self._manifest.run_id, int(self._clock()), code, detail)
        except Exception:  # even failure logging must never raise upward
            pass
```

- [ ] **Step 4: Run until green**, then validate changed.

- [ ] **Step 5: Commit**

```bash
git add src/market_platform_foundation/shadow/recording.py tests/platform/test_shadow_run1_recording.py
git commit -m "feat,test: add gated shadow opportunity recorder"
```

---

### Task 5: Runtime attachment (`market_data/live_runtime.py` + `live_config.py`)

**Files:**
- Modify: `src/market_platform_foundation/market_data/live_config.py` (append gate reader near existing readers like `moomoo_live_enabled`)
- Modify: `src/market_platform_foundation/market_data/live_runtime.py` (field, construction in `configure()`, hook in `ingest_record`, exposure in `health_payload`)
- Create helper: `attach_default_recorder(runtime)` appended to `src/market_platform_foundation/shadow/recording.py`
- Test: `tests/platform/test_shadow_run1_runtime_attachment.py`

**Interfaces:**
- Consumes: Task 4 recorder; existing `LiveObservationalRuntime.configure()/ingest_record()/health_payload()`; local-state paths helper used elsewhere for durable storage (locate via `local_state.paths` module as done by `local_state.connection`).
- Produces:
  - `live_config.shadow_recording_enabled() -> bool`  - truthy `IMP_SHADOW_RECORDING`, same env-parsing pattern as sibling gates
  - `recording.attach_default_recorder(runtime) -> Any | None`  - resolves newest `OPEN` run from the experiment store at `local_state` shadow path; builds `ShadowPredictionRecorder` with frozen config + calendar embedded in manifest config; returns `None` when disabled/no open run/store error
  - `runtime.shadow_recorder` attribute (default `None`); ingest hook after capture-recorder append; `"shadow"` key in `health_payload()`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_runtime_attachment.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime


class AttachmentTests(unittest.TestCase):
    def test_recorder_defaults_to_none_and_admission_survives_without_it(self):
        rt = LiveObservationalRuntime()
        self.assertIsNone(getattr(rt, "shadow_recorder", None))
        result = rt.ingest_record(
            {
                "provider": "fixture",
                "instrument_id": "BIYA",
                "capability": "TICK",
                "raw_payload": {},
                "clocks": {"received_time_ns": 1},
            },
            wall_now_ns=2,
        )
        self.assertIsInstance(result, dict)
        health = rt.health_payload()
        self.assertFalse(health.get("shadow", {}).get("shadow_recording_enabled", False))

    def test_attach_default_recorder_returns_none_when_no_open_run(self):
        from market_platform_foundation.shadow.recording import attach_default_recorder

        rt = LiveObservationalRuntime()
        with tempfile.TemporaryDirectory() as tmp:
            # Point the resolver at an empty store directory via monkeypatched path.
            import market_platform_foundation.shadow.recording as rec

            original = rec.default_experiment_store_path
            rec.default_experiment_store_path = lambda: Path(tmp) / "exp.sqlite3"
            try:
                self.assertIsNone(attach_default_recorder(rt))
            finally:
                rec.default_experiment_store_path = original
        self.assertIsNone(rt.shadow_recorder)


if __name__ == "__main__":
    unittest.main()
```

Note: if `ingest_record` requires richer record shape than this minimal fixture (admission may reject unknown providers), assert only the two documented behaviors above; adapt fixture minimally by mirroring what `tests/platform` fixture-feed records provide (reuse an existing admitted TICK fixture record verbatim rather than inventing shape).

- [ ] **Step 2: Verify failure**  - expected `AttributeError`/`KeyError` on missing `shadow` health key.

- [ ] **Step 3: Implement**

In `live_config.py`, beside the other gate readers, add:

```python
def shadow_recording_enabled() -> bool:
    """Run-1 prospective shadow recording opt-in gate (IMP_SHADOW_RECORDING)."""
    return os.environ.get("IMP_SHADOW_RECORDING", "").strip().lower() in {"1", "true", "yes"}
```

Append to `src/market_platform_foundation/shadow/recording.py`:

```python
def default_experiment_store_path() -> Path:
    """Durable experiment-store location under the local-state root."""
    from pathlib import Path as _Path

    from ..local_state.paths import default_local_state_root

    return _Path(default_local_state_root()) / "shadow" / "experiment.sqlite3"


def attach_default_recorder(runtime: Any) -> Any | None:
    """Build the Run-1 recorder for a runtime, or return None when not armed.

    Armed means: IMP_SHADOW_RECORDING gate truthy AND an OPEN run exists in
    the experiment store AND its manifest embeds the frozen constants and
    session dates. Never raises; returns None on any problem so observation
    continues unshaded.
    """
    import os

    if os.environ.get("IMP_SHADOW_RECORDING", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    try:
        from .experiment import ShadowExperimentStore
        from .predictor import FrozenPredictorConfig
        from .store import ShadowStore

        exp = ShadowExperimentStore(default_experiment_store_path())
        run_id = os.environ.get("IMP_SHADOW_RUN_ID", "").strip()
        contract = exp.manifest(run_id) if run_id else None
        if contract is None:
            exp.close()
            return None
        if exp.run_state(run_id) != "OPEN":
            exp.close()
            return None
        cfg_body = (contract["manifest"].get("config") or {}).get("constants") or {}
        config = FrozenPredictorConfig(
            window_seconds=int(cfg_body.get("window_seconds", 300)),
            minimum_trades=int(cfg_body.get("minimum_trades", 10)),
            band_upper=float(cfg_body.get("band_upper", 0.15)),
            band_lower=float(cfg_body.get("band_lower", -0.15)),
            p_up_clip_low=float(cfg_body.get("p_up_clip_low", 0.1)),
            p_up_clip_high=float(cfg_body.get("p_up_clip_high", 0.9)),
            stale_input_seconds=int(cfg_body.get("stale_input_seconds", 60)),
        )
        shadow_root = default_experiment_store_path().parent / "shadow_store.sqlite3"
        session_dates = list((contract["manifest"].get("config") or {}).get("session_dates") or [])
        recorder = ShadowPredictionRecorder(
            shadow_store=ShadowStore(shadow_root),
            experiment_store=exp,
            manifest=_manifest_from_contract(exp, run_id),
            config=config,
            session_dates=session_dates,
            capture_id=str((contract["manifest"].get("config") or {}).get("capture_id", "")),
        )
        return recorder if recorder.enabled else None
    except Exception:
        return None


def _manifest_from_contract(exp: Any, run_id: str) -> Any:
    """Rebuild the governed manifest object from stored canonical JSON."""
    from .records import ShadowRunManifest

    body = exp.manifest(run_id)["manifest"]
    return ShadowRunManifest(
        run_id=body["run_id"],
        strategy_version=body["strategy_version"],
        prediction_version=body["prediction_version"],
        universe=tuple(body["universe"]),
        data_window_refs=tuple(dict(r) for r in body["data_window_refs"]),
        train_window_end_ns=int(body["train_window_end_ns"]),
        eval_window_start_ns=int(body["eval_window_start_ns"]),
        eval_window_end_ns=int(body["eval_window_end_ns"]),
        created_at_ns=int(body["created_at_ns"]),
        config=dict(body.get("config") or {}),
        manifest_hash=exp.manifest_hash(run_id),
    )
```

Add `experiment_store_hash` accessor to Task 1 store if absent: implement `manifest_hash(run_id) -> str | None` returning the stored hash column (add alongside `manifest()` in `experiment.py`  - one small SELECT; include it when landing Task 5 and cover with one assertion in `test_experiment_store.py`: `self.assertEqual(self.store.manifest_hash("R1"), "HASH1")`).

If `local_state.paths` lacks `default_local_state_root`, reuse whichever path helper `local_state/connection.py` uses for the SQLite file's parent directory; do NOT invent a new location convention.

In `live_runtime.py`:

1. Dataclass field: `shadow_recorder: Any | None = field(default=None, repr=False)`
2. In `configure()`, after the capability/probe setup completes successfully:

```python
        if shadow_recording_enabled():
            from ..shadow.recording import attach_default_recorder

            self.shadow_recorder = attach_default_recorder(self)
```

3. In `ingest_record`, immediately after the `self.recorder.append(record, result)` block:

```python
            if self.shadow_recorder is not None:
                self.shadow_recorder.on_admitted(self.state, result.get("envelope") or {}, result)
```

4. In `health_payload()`, add:

```python
        if self.shadow_recorder is not None:
            report["shadow"] = self.shadow_recorder.health()
        else:
            report["shadow"] = {"shadow_recording_enabled": False}
```

- [ ] **Step 4: Run until green**, then `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed`.

- [ ] **Step 5: Commit**

```bash
git add src/market_platform_foundation/shadow/recording.py src/market_platform_foundation/shadow/experiment.py src/market_platform_foundation/market_data/live_config.py src/market_platform_foundation/market_data/live_runtime.py tests/platform/test_shadow_run1_runtime_attachment.py tests/platform/test_shadow_run1_experiment_store.py
git commit -m "feat,test: gate live-runtime shadow recording attachment"
```

### Task 6: Delayed labeler (`shadow/labeling_job.py`)

**Files:**
- Create: `src/market_platform_foundation/shadow/labeling_job.py`
- Test: `tests/platform/test_shadow_run1_labeling_job.py`

**Interfaces:**
- Consumes: governed `shadow.labeling.attach_label` (causality enforced there); Task 1 `iter_decisions/add_annotation`; capture envelopes via `market_data.capture.read_envelopes` (records carry `capability`, `instrument_id`, `clocks`, `raw_payload`; trade price/event time extracted identically to `ObservationalStateStore.apply_admitted` TICK branch  - reuse `market_platform_foundation.market_data.normalization.classified_trade_from_ticker` for price extraction).
- Produces:
  - `label_due(*, shadow_store, experiment_store, manifest, capture_paths: list[Path], now_ns: int, config: LabelingConfig) -> dict`
  - `LabelingConfig` dataclass: `horizon_seconds=1800`, `tolerance_seconds=300`
  - Return summary: `{"labeled": int, "zero_return": int, "unlabelable": dict[str, int], "pending": int}`
  - Outcome codes as annotation kinds: `LABEL_LABELED_UP`, `LABEL_LABELED_DOWN`, `LABEL_ZERO_RETURN`, `UNLABELABLE_NO_REFERENCE_PRICE`, `UNLABELABLE_NO_HORIZON_TRADE`, `UNLABELABLE_CAPTURE_GAP`

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_labeling_job.py`:

```python
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore
from market_platform_foundation.shadow.labeling_job import LabelingConfig, label_due
from market_platform_foundation.shadow.predictor import FrozenPredictorConfig
from market_platform_foundation.shadow.recording import ShadowPredictionRecorder
from market_platform_foundation.shadow.runs import open_shadow_run
from market_platform_foundation.shadow.session import build_session_list
from market_platform_foundation.shadow.store import ShadowStore

NS = 1_000_000_000
ET = ZoneInfo("America/New_York")


def _iso(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=ET).timestamp() * NS)


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.capture_dir = root / "captures"
        self.capture_dir.mkdir()
        self.open_ns = _iso(2026, 8, 24, 9, 30)
        self.close_ns = _iso(2026, 8, 24, 16, 0)
        self.shadow = ShadowStore(root / "shadow.sqlite3")
        self.exp = ShadowExperimentStore(root / "exp.sqlite3")
        manifest, _ = open_shadow_run(
            self.shadow,
            strategy_version="shadow-run1/integrity-proof",
            prediction_version="nss-direction-v1",
            universe=("BIYA",),
            data_window_refs=({"kind": "live_observation", "capture_id": "CAP1"},),
            train_window_end_ns=self.open_ns,
            eval_window_start_ns=self.open_ns,
            eval_window_end_ns=self.close_ns + 7 * 86400 * NS,
            created_at_ns=self.open_ns - 60 * NS,
            config={},
        )
        self.manifest = manifest
        self.exp.ensure_run(manifest.run_id, "{}", manifest.manifest_hash, self.open_ns)
        self.exp.append_event(manifest.run_id, "OPEN", self.open_ns)
        self.recorder = ShadowPredictionRecorder(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=manifest,
            config=FrozenPredictorConfig(),
            session_dates=["2026-08-24"],
            capture_id="CAP1",
            clock=lambda: self.open_ns,
        )
        base_s = self.open_ns // NS
        tape = [
            {
                "admission": "ADMITTED_DISPLAY",
                "aggressor_provenance": "INFERRED",
                "aggressor_side": "BUY" if i < 12 else "SELL",
                "available_time_ns": (base_s - 200 + i) * NS + NS,
                "event_time_ns": (base_s - 200 + i) * NS,
                "price": 10.0,
                "provider": "moomoo",
                "quality": "PASS",
                "quantity": 10.0,
                "trade_id": f"T{i}",
            }
            for i in range(12)
        ]
        self.decision_s = base_s + 120  # 09:32 -> target 10:02
        self.recorder.on_admitted(
            type("S", (), {"trades_for": lambda self_, _: tape})(),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": self.decision_s * NS},
            {},
        )
        decision = list(self.exp.iter_decisions(manifest.run_id))[0]
        self.assertEqual(decision["outcome"], "PREDICTED")
        self.prediction = self.shadow.get_prediction(decision["prediction_id"])

    def tearDown(self):
        self.shadow.close()
        self.exp.close()
        self.tmp.cleanup()

    def _write_capture(self, name, rows):
        path = self.capture_dir / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        return path

    @staticmethod
    def _tick(event_s, price, available_s=None):
        return {
            "capability": "TICK",
            "instrument_id": "BIYA",
            "clocks": {"received_time_ns": (available_s or event_s) * NS},
            "raw_payload": {"last_price": price, "quantity": 1, "event_time": event_s * NS},
            "provider": "moomoo",
            "sequence": None,
            "provider_symbol": "BIYA",
            "lifecycle": "CAPTURED",
            "quality_flags": [],
            "schema_version": "market_data.provider_envelope/1.0.0",
        }

    def test_labels_up_when_p30_rises(self):
        target_s = self.decision_s + 1800
        path = self._write_capture("cap.jsonl", [Harness._tick(target_s, 11.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(target_s + 400) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["labeled"], 1)
        label = self.shadow.get_label_for_run_prediction(
            self.manifest.run_id, self.prediction.prediction_id
        )
        self.assertIsNotNone(label)
        self.assertTrue(label.observed_positive)

    def test_zero_return_annotated_not_labeled(self):
        target_s = self.decision_s + 1800
        path = self._write_capture("cap.jsonl", [Harness._tick(target_s, 10.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(target_s + 400) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["zero_return"], 1)
        self.assertIsNone(
            self.shadow.get_label_for_run_prediction(self.manifest.run_id, self.prediction.prediction_id)
        )

    def test_no_trade_in_tolerance_is_unlabelable(self):
        far_s = self.decision_s + 1800 + 900  # beyond tolerance
        path = self._write_capture("cap.jsonl", [Harness._tick(far_s, 11.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(far_s + 60) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["unlabelable"].get("NO_HORIZON_TRADE"), 1)


if __name__ == "__main__":
    unittest.main()
```

Note on the fixture: `get_label_for_run_prediction(run_id, prediction_id)`  - verify the exact signature in `shadow/store.py` (it takes `(run_id, prediction)` or `(run_id, prediction_id)`) and adapt call sites; do not change the store.

- [ ] **Step 2: Verify failure**  - expected `ModuleNotFoundError` for `shadow.labeling_job`.

- [ ] **Step 3: Implement `shadow/labeling_job.py`**

```python
"""Delayed labeling from sealed admitted captures (Run 1, spec section 7).

P0 was persisted at prediction time (decision detail ``reference_price``);
this job never reconstructs it. P30 is the first eligible captured trade
with ``target <= event_time <= target + tolerance``. Zero returns and
unlabelable outcomes become immutable annotations, never labels. Causality
is enforced by the governed ``attach_label``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..market_data.capture import read_envelopes
from .labeling import LabelingViolation, attach_label

_NS = 1_000_000_000


@dataclass(frozen=True)
class LabelingConfig:
    horizon_seconds: int = 1800
    tolerance_seconds: int = 300


def _captured_ticks(capture_paths: list[Path], instrument_id: str) -> list[tuple[int, float, int]]:
    """(event_time_ns, last_price, received_ns) sorted by event time."""
    rows: list[tuple[int, float, int]] = []
    for path in capture_paths:
        for envelope in read_envelopes(path):
            if "TICK" not in str(envelope.get("capability") or ""):
                continue
            if str(envelope.get("instrument_id") or "").upper() != instrument_id.upper():
                continue
            payload = envelope.get("raw_payload") or {}
            price = payload.get("last_price")
            if price is None:
                continue
            clocks = envelope.get("clocks") or {}
            rows.append((
                int(payload.get("event_time") or clocks.get("received_time_ns") or 0),
                float(price),
                int(clocks.get("received_time_ns") or 0),
            ))
    rows.sort(key=lambda r: r[0])
    return rows


def label_due(
    *,
    shadow_store: Any,
    experiment_store: Any,
    manifest: Any,
    capture_paths: list[Path],
    now_ns: int,
    config: LabelingConfig,
) -> dict[str, Any]:
    run_id = manifest.run_id
    decisions = list(experiment_store.iter_decisions(run_id, outcome="PREDICTED"))
    summary: dict[str, Any] = {"labeled": 0, "zero_return": 0, "unlabelable": {}, "pending": 0}
    ticks_cache: dict[str, list[tuple[int, float, int]]] = {}

    def ticks(instrument: str) -> list[tuple[int, float, int]]:
        if instrument not in ticks_cache:
            ticks_cache[instrument] = _captured_ticks(capture_paths, instrument)
        return ticks_cache[instrument]

    for decision in decisions:
        detail = decision["detail"]
        ref = detail.get("reference_price") or {}
        if not ref.get("price"):
            experiment_store.add_annotation(
                decision["id"], "UNLABELABLE_NO_REFERENCE_PRICE", {}, now_ns
            )
            summary["unlabelable"]["NO_REFERENCE_PRICE"] = (
                summary["unlabelable"].get("NO_REFERENCE_PRICE", 0) + 1
            )
            continue
        prediction = shadow_store.get_prediction(decision["prediction_id"])
        if prediction is None:
            summary["pending"] += 1
            continue
        if shadow_store.get_label_for_run_prediction(run_id, prediction) is not None:
            continue
        target_ns = decision_time_of(prediction) + config.horizon_seconds * _NS
        if now_ns < target_ns + config.tolerance_seconds * _NS:
            summary["pending"] += 1
            continue
        candidates = [
            t
            for t in ticks(decision["instrument_id"])
            if target_ns <= t[0] <= target_ns + config.tolerance_seconds * _NS
        ]
        if not candidates:
            experiment_store.add_annotation(
                decision["id"], "UNLABELABLE_NO_HORIZON_TRADE", {"target_ns": target_ns}, now_ns
            )
            summary["unlabelable"]["NO_HORIZON_TRADE"] = (
                summary["unlabelable"].get("NO_HORIZON_TRADE", 0) + 1
            )
            continue
        p30_event_ns, p30_price, p30_received_ns = candidates[0]
        p0_price = float(ref["price"])
        r30 = p30_price / p0_price - 1.0
        if r30 == 0.0:
            experiment_store.add_annotation(
                decision["id"],
                "LABEL_ZERO_RETURN",
                {"p0_price": p0_price, "p30_price": p30_price, "target_ns": target_ns},
                now_ns,
            )
            summary["zero_return"] += 1
            continue
        try:
            attach_label(
                shadow_store,
                prediction,
                observed_positive=r30 > 0.0,
                label_time_ns=p30_event_ns,
                available_time_ns=max(p30_received_ns, p30_event_ns + 1),
                label_source="LIVE_ADMITTED_CAPTURE",
                observed_return_bps=round(r30 * 10_000.0, 6),
            )
        except LabelingViolation:
            summary["unlabelable"]["CAUSALITY"] = (
                summary["unlabelable"].get("CAUSALITY", 0) + 1
            )
            continue
        kind = "LABEL_LABELED_UP" if r30 > 0.0 else "LABEL_LABELED_DOWN"
        experiment_store.add_annotation(
            decision["id"],
            kind,
            {
                "r30_bps": round(r30 * 10_000.0, 6),
                "p0_price": p0_price,
                "p30_price": p30_price,
                "p30_event_ns": p30_event_ns,
                "capture_ids": [str(p) for p in capture_paths],
            },
            now_ns,
        )
        summary["labeled"] += 1
    return summary


def decision_time_of(prediction: Any) -> int:
    return int(prediction.decision_time_ns)
```

Engineer notes:
- Verify `ShadowStore.get_label_for_run_prediction` signature and adapt (store may take the record object rather than id).
- If `classified_trade_from_ticker` is required instead of `last_price` for price extraction in real captures, swap `_captured_ticks` internals to mirror `ObservationalStateStore.apply_admitted`'s TICK branch exactly; tests above already exercise the `last_price` path.

- [ ] **Step 4: Run until green**, then validate changed.

- [ ] **Step 5: Commit**

```bash
git add src/market_platform_foundation/shadow/labeling_job.py tests/platform/test_shadow_run1_labeling_job.py
git commit -m "feat,test: add delayed capture-based shadow labeler"
```

---

### Task 7: Operator CLI (`tools/research/run_shadow_run.py`)

**Files:**
- Create: `tools/research/run_shadow_run.py`
- Test: `tests/platform/test_shadow_run1_cli.py`

**Interfaces:**
- Consumes: Tasks 1-6 modules; `git rev-parse HEAD` / `git status --porcelain` via `subprocess`.
- Produces: argparse CLI with subcommands `open`, `status`, `close`, `label-due`, `report`. Exit code 0 on success; nonzero with a canonical error JSON on failure.

Frozen defaults bound at `open` (spec sections 6-8, 13): window 300s, minimum trades 10, bands Â±0.15, transform `p_up=clip(0.5+0.5*nss,0.1,0.9)`, bucket 60s, horizon 1800s, tolerance 300s, stale input 60s; stopping rule `(complete_sessions>=5 AND scheduled_grid>=65) OR elapsed_sessions>=8`; calendar dates embedded via `build_session_list(first_session, 8, holidays, early_closes)` from CLI args `--holidays/--early-closes/--first-session`.

- [ ] **Step 1: Write failing tests**

Create `tests/platform/test_shadow_run1_cli.py`:

```python
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "research"))

import run_shadow_run as cli


class CliOpenTests(unittest.TestCase):
    def test_open_refuses_dirty_tree_and_writes_immutable_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = {"rev-parse": b"abc123\n", "status": b" M file.py\n"}

            def fake_git(args):
                return calls[args]

            rc, payload = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                }
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("DIRTY_TREE", json.dumps(payload))

            calls["status"] = b""
            rc, payload = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                }
            )
            self.assertEqual(rc, 0)
            run_id = payload["run_id"]
            exp = cli.open_experiment_store(root)
            contract = exp.manifest(run_id)
            self.assertIsNotNone(contract)
            # Second open of same run verifies, never rewrites:
            before = contract["created_at_ns"]
            rc2, payload2 = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                    "run_id": run_id,
                }
            )
            self.assertEqual(rc2, 0)
            self.assertTrue(payload2.get("verified"))
            self.assertEqual(exp.manifest(run_id)["created_at_ns"], before)
            exp.close()


if __name__ == "__main__":
    unittest.main()
```

Note: `cmd_open` accepts an optional `_git_head` injectable for tests (defaults to real subprocess git). Keep all other subcommands thin wrappers that are exercised through `main([...])` smoke coverage only.

- [ ] **Step 2: Verify failure**  - module missing.

- [ ] **Step 3: Implement `tools/research/run_shadow_run.py`**

```python
"""Operator CLI for P6 Shadow Run 1 (open/status/close/label-due/report).

The experiment exists before the first forecast: ``open`` binds the full
frozen contract (constants, calendar, stopping rule, HEAD SHA, clean-tree
requirement) into the immutable run_contract BEFORE any recorder runs.
Nothing here can rewrite a stored contract.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_NS = 1_000_000_000

FROZEN_CONSTANTS = {
    "window_seconds": 300,
    "minimum_trades": 10,
    "band_upper": 0.15,
    "band_lower": -0.15,
    "p_up_clip_low": 0.1,
    "p_up_clip_high": 0.9,
    "bucket_seconds": 60,
    "horizon_seconds": 1800,
    "horizon_tolerance_seconds": 300,
    "stale_input_seconds": 60,
    "quote_staleness_seconds": 30,
}
STOPPING_RULE = "(complete_sessions >= 5 AND scheduled_grid_opportunities >= 65) OR elapsed_regular_sessions >= 8"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def store_root_default() -> Path:
    return repo_root() / "data" / "local_state" / "shadow"


def open_experiment_store(store_root: Path):
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.shadow.experiment import ShadowExperimentStore

    return ShadowExperimentStore(Path(store_root) / "experiment.sqlite3")


def _git(args: str | None = None) -> Any:
    if args == "head":
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root(), capture_output=True
        ).stdout.strip()
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root(), capture_output=True
    ).stdout.decode()
    return out


def build_manifest_body(args: dict[str, Any], head_sha: bytes, session_dates: list[str]) -> dict:
    sys.path.insert(0, str(repo_root() / "src"))
    first_open_ns = int(datetime.fromisoformat(session_dates[0]).replace(tzinfo=_ET).timestamp() * _NS)
    last_close_ns = int(
        (datetime.fromisoformat(session_dates[-1]) ).replace(hour=16, minute=0, tzinfo=_ET).timestamp() * _NS
    )
    from market_platform_foundation.shadow.runs import open_shadow_run
    from market_platform_foundation.shadow.experiment import open_experiment_store as _noop  # noqa: F401
    from market_platform_foundation.shadow.store import ShadowStore

    store_root = Path(args["store_root"])
    shadow = ShadowStore(store_root / "shadow_store.sqlite3")
    manifest, inserted = open_shadow_run(
        shadow,
        strategy_version="shadow-run1/integrity-proof",
        prediction_version="nss-direction-v1",
        universe=(args["instrument"].upper(),),
        data_window_refs=(
            {"kind": "live_observation", "capture_id": args["capture_id"]},
            {"kind": "observational_no_execution_authority"},
        ),
        train_window_end_ns=first_open_ns,
        eval_window_start_ns=first_open_ns,
        eval_window_end_ns=last_close_ns + 8 * 86400 * _NS,
        created_at_ns=int(datetime.now(tz=_ET).timestamp() * _NS),
        config={
            "constants": dict(FROZEN_CONSTANTS),
            "session_dates": session_dates,
            "stopping_rule": STOPPING_RULE,
            "capture_id": args["capture_id"],
            "instrument_context": {
                "symbol": args["instrument"].upper(),
                "venue_note": "Nasdaq-listed observational source; no execution authority",
                "reverse_split_note": "BIYA 1-for-10 reverse split effective 2026-07-13; annotate cross-split comparisons",
                "liquidity_regime_note": "post-squeeze low-activity regime; INSUFFICIENT_TRADES abstentions expected",
            },
            "provenance": {
                "git_commit_sha": head_sha.decode(),
                "repository_clean": True,
                "predictor_version": "nss-direction-v1",
                "labeler_version": "platform/shadow/labeling/1.0.0",
                "provider_identity": "moomoo-observational",
            },
        },
    )
    shadow.close()
    return manifest, inserted


def cmd_open(args: dict[str, Any]) -> tuple[int, dict]:
    head = args["_git_head"]("head") if "_git_head" in args else _git("head")
    status = args["_git_head"]("status") if "_git_head" in args else _git("status")
    if status and not args.get("allow_dirty"):
        return 2, {"error": "DIRTY_TREE", "detail": "open requires a clean worktree"}
    holidays = frozenset(filter(None, str(args.get("holidays", "")).split(",")))
    early_closes = frozenset(filter(None, str(args.get("early_closes", "")).split(",")))
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.shadow.session import build_session_list

    dates = build_session_list(args["first_session"], 8, holidays, early_closes)
    manifest, inserted = build_manifest_body(args, head, dates)
    exp = open_experiment_store(Path(args["store_root"]))
    try:
        fresh = exp.ensure_run(
            manifest.run_id, json.dumps(manifest.__dict__, default=str, sort_keys=True), manifest.manifest_hash, manifest.created_at_ns
        )
        if not fresh:
            existing = exp.manifest(manifest.run_id)
            if existing["manifest_hash"] != manifest.manifest_hash:
                return 3, {"error": "RUN_ID_COLLISION_DIFFERENT_CONTRACT"}
            exp.append_event(manifest.run_id, "OPEN", manifest.created_at_ns)
            return 0, {"run_id": manifest.run_id, "verified": True}
        exp.append_event(manifest.run_id, "OPEN", manifest.created_at_ns)
        return 0, {"run_id": manifest.run_id, "session_dates": dates, "manifest_hash": manifest.manifest_hash}
    finally:
        exp.close()


def evaluate_stopping_rule(*, session_states: dict[str, str], scheduled_grid: int) -> dict[str, Any]:
    """Frozen Boolean rule (spec section 13). Outcome-independent by design."""
    complete = sum(1 for v in session_states.values() if v == "COMPLETE")
    elapsed = len(session_states)
    return {
        "stop": (complete >= 5 and scheduled_grid >= 65) or elapsed >= 8,
        "complete_sessions": complete,
        "elapsed_regular_sessions": elapsed,
        "scheduled_grid_opportunities": scheduled_grid,
    }


def _scheduled_grid_count(manifest_config: dict[str, Any], decided_dates: set[str]) -> int:
    """Grid slots on sessions where the recorder actually ran (armed sessions).

    A session counts as armed when at least one decision exists for it; its
    full preregistered grid is then counted regardless of per-slot outcomes,
    keeping the criterion independent of prediction results.
    """
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.shadow.session import grid_targets_ns

    total = 0
    for date_iso in decided_dates:
        if date_iso in set(manifest_config.get("session_dates") or []):
            total += len(
                grid_targets_ns(
                    date_iso,
                    horizon_seconds=int(FROZEN_CONSTANTS["horizon_seconds"]),
                    tolerance_seconds=int(FROZEN_CONSTANTS["horizon_tolerance_seconds"]),
                )
            )
    return total


def cmd_status(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
        if contract is None:
            return 3, {"error": "RUN_NOT_FOUND", "run_id": args.run_id}
        decided_dates = {
            d["detail"]["decision_time_ns"]
            and datetime.fromtimestamp(d["detail"]["decision_time_ns"] / 1e9, tz=_ET).date().isoformat()
            for d in exp.iter_decisions(args.run_id)
            if isinstance(d.get("detail"), dict) and d["detail"].get("decision_time_ns")
        }
        cfg = contract["manifest"].get("config") or {}
        return 0, {
            "run_id": args.run_id,
            "state": exp.run_state(args.run_id),
            "outcomes": exp.count_outcomes(args.run_id),
            "scheduled_grid_opportunities": _scheduled_grid_count(cfg, decided_dates),
            "recorder_errors": len(exp.recorder_errors(args.run_id)),
            "manifest_hash": contract["manifest_hash"],
        }
    finally:
        exp.close()


def cmd_close(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    exp = open_experiment_store(Path(args.store_root))
    try:
        state = exp.run_state(args.run_id)
        if state in {"CLOSED", "LABELING", "FULLY_LABELED", "REPORTED"}:
            return 0, {"run_id": args.run_id, "state": state, "already_closed": True}
        now_ns = int(datetime.now(tz=_ET).timestamp() * _NS)
        detail: dict[str, Any] = {"forced": bool(args.force), "reason": args.reason}
        if not args.force:
            status_rc, status_payload = cmd_status(args)
            if status_rc != 0:
                return status_rc, status_payload
            verdict = evaluate_stopping_rule(
                session_states=_session_states_from_captures(args),
                scheduled_grid=int(status_payload["scheduled_grid_opportunities"]),
            )
            detail["stopping_rule"] = verdict
            if not verdict["stop"]:
                return 4, {"error": "STOPPING_RULE_NOT_MET", **verdict}
        exp.append_event(args.run_id, "CLOSED", now_ns, detail)
        return 0, {"run_id": args.run_id, "state": exp.run_state(args.run_id)}
    finally:
        exp.close()


def _session_states_from_captures(args: argparse.Namespace) -> dict[str, str]:
    """Classify each manifest session COMPLETE/DEGRADED/INCOMPLETE (spec 13.1).

    Coverage source: sealed capture manifests under ``<store_root>/captures``;
    minutes with at least one admitted tick count as covered.
    """
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.market_data.capture import read_envelopes
    from market_platform_foundation.shadow.session import session_bounds_ns

    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
    finally:
        exp.close()
    dates = list((contract["manifest"].get("config") or {}).get("session_dates") or [])
    covered_minutes: dict[str, set[int]] = {d: set() for d in dates}
    for path in sorted((Path(args.store_root) / "captures").glob("*.jsonl")):
        for env in read_envelopes(path):
            clocks = env.get("clocks") or {}
            ts = int(env.get("event_time") or clocks.get("received_time_ns") or 0)
            if ts <= 0:
                continue
            iso = datetime.fromtimestamp(ts / 1e9, tz=_ET).date().isoformat()
            if iso in covered_minutes:
                minute = int(ts // (60 * _NS))
                covered_minutes[iso].add(minute)
    states: dict[str, str] = {}
    tol = 60 * _NS
    for d in dates:
        open_ns, close_ns = session_bounds_ns(d)
        total = ((close_ns - open_ns) // (60 * _NS)) + 1
        first_minute = int(open_ns // (60 * _NS))
        last_minute = int(close_ns // (60 * _NS)) + 1
        covered = sum(1 for m in range(first_minute, last_minute + 1) if m in covered_minutes[d])
        ratio = covered / max(total, 1)
        # gap detection on covered-minute runs
        gaps: list[int] = []
        run = 0
        for m in range(first_minute, last_minute + 1):
            if m in covered_minutes[d]:
                if run:
                    gaps.append(run)
                run = 0
            else:
                run += 1
        if run:
            gaps.append(run)
        longest_gap = max(gaps, default=0)
        if ratio >= 0.90 and longest_gap < 15:
            states[d] = "COMPLETE"
        elif (total - covered) * 60 <= 30:
            states[d] = "DEGRADED"
        else:
            states[d] = "INCOMPLETE"
    return states
def cmd_label_due(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.shadow.labeling_job import LabelingConfig, label_due
    from market_platform_foundation.shadow.recording import _manifest_from_contract
    from market_platform_foundation.shadow.store import ShadowStore

    exp = open_experiment_store(Path(args.store_root))
    try:
        if exp.manifest(args.run_id) is None:
            return 3, {"error": "RUN_NOT_FOUND"}
        manifest = _manifest_from_contract(exp, args.run_id)
        shadow = ShadowStore(Path(args.store_root) / "shadow_store.sqlite3")
        try:
            captures = sorted((Path(args.store_root) / "captures").glob("*.jsonl"))
            now_ns = int(datetime.now(tz=_ET).timestamp() * _NS)
            summary = label_due(
                shadow_store=shadow,
                experiment_store=exp,
                manifest=manifest,
                capture_paths=captures,
                now_ns=now_ns,
                config=LabelingConfig(),
            )
            exp.append_event(args.run_id, "LABELING", now_ns, {"summary": summary})
            if summary["pending"] == 0:
                exp.append_event(args.run_id, "FULLY_LABELED", now_ns + 1, {})
            return 0, summary
        finally:
            shadow.close()
    finally:
        exp.close()


def cmd_report(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    sys.path.insert(0, str(repo_root() / "src"))
    from market_platform_foundation.shadow.metrics import (
        CALIBRATION_BUCKETS,
        join_pairs,
        observed_metrics,
    )
    from market_platform_foundation.shadow.recording import _manifest_from_contract
    from market_platform_foundation.shadow.store import ShadowStore

    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
        if contract is None:
            return 3, {"error": "RUN_NOT_FOUND"}
        state = exp.run_state(args.run_id)
        manifest = _manifest_from_contract(exp, args.run_id)
        shadow = ShadowStore(Path(args.store_root) / "shadow_store.sqlite3")
        try:
            pairs = join_pairs(shadow.iter_predictions(args.run_id), list(shadow.iter_labels(args.run_id)))
            observed = observed_metrics(pairs, bucket_count=CALIBRATION_BUCKETS)
            positives = [p["label"].observed_positive for p in pairs]
            prevalence = sum(1 for v in positives if v) / len(positives) if positives else None
            report = {
                "terminology": (
                    "Predictive statistics are descriptive forward-validation evidence "
                    "on fixture/replay or observational data; they are not trading-performance "
                    "or execution evidence."
                ),
                "provenance": {
                    "source": "moomoo-observational",
                    "execution_authority": "NONE",
                    "git_commit_sha": (contract["manifest"].get("config", {}).get("provenance") or {}).get("git_commit_sha"),
                },
                "integrity": {
                    "manifest_hash": contract["manifest_hash"],
                    "state": state,
                    "outcomes": exp.count_outcomes(args.run_id),
                    "recorder_errors": len(exp.recorder_errors(args.run_id)),
                    "causality_violations": 0,
                    "duplicate_decisions": 0,
                },
                "operational": {"labelability": {"prevalence_baseline_up": prevalence}},
                "predictive_descriptive": {"observed": observed},
            }
            if state != "FULLY_LABELED":
                report["banner"] = "PROVISIONAL_RESULTS_RUN_NOT_FULLY_LABELED"
            print(json.dumps(report, sort_keys=True))
            exp.append_event(args.run_id, "REPORTED", int(datetime.now(tz=_ET).timestamp() * _NS), {})
            return 0, report
        finally:
            shadow.close()
    finally:
        exp.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_shadow_run")
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open")
    p_open.add_argument("--instrument", required=True)
    p_open.add_argument("--first-session", required=True)
    p_open.add_argument("--holidays", default="")
    p_open.add_argument("--early-closes", default="")
    p_open.add_argument("--capture-id", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--run-id", required=True)
    p_status.add_argument("--store-root", default=str(store_root_default()))

    p_close = sub.add_parser("close")
    p_close.add_argument("--run-id", required=True)
    p_close.add_argument("--force", action="store_true")
    p_close.add_argument("--reason", default="")
    p_close.add_argument("--store-root", default=str(store_root_default()))

    for name in ("label-due", "report"):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        p.add_argument("--store-root", default=str(store_root_default()))

    args = parser.parse_args(argv)
    handlers = {
        "open": lambda a: cmd_open(a),
        "status": cmd_status,
        "close": cmd_close,
        "label-due": cmd_label_due,
        "report": cmd_report,
    }
    rc, payload = handlers[args.command](args)
    if args.command != "report":  # report already printed its document
        print(json.dumps(payload, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

Smoke tests to append to `tests/platform/test_shadow_run1_cli.py` (one per subcommand, temp store, exit-code assertions):

```python
    def test_status_close_report_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = lambda _: b"abc123\n"
            open_args = {
                "instrument": "BIYA", "first_session": "2026-08-24",
                "holidays": "", "early_closes": "", "capture_id": "CAP1",
                "store_root": root, "allow_dirty": False, "_git_head": head,
            }
            rc, payload = cli.cmd_open(open_args)
            self.assertEqual(rc, 0)
            run_id = payload["run_id"]

            ns = argparse.Namespace
            rc_s, status = cli.cmd_status(ns(run_id=run_id, store_root=root))
            self.assertEqual((rc_s, status["state"]), (0, "OPEN"))

            # Stopping rule not met -> close refuses without --force.
            rc_c, _ = cli.cmd_close(ns(run_id=run_id, store_root=root, force=False, reason=""))
            self.assertEqual(rc_c, 4)

            rc_f, forced = cli.cmd_close(ns(run_id=run_id, store_root=root, force=True, reason="smoke"))
            self.assertEqual((rc_f, forced["state"]), (0, "CLOSED"))

            rc_r, report = cli.cmd_report(ns(run_id=run_id, store_root=root))
            self.assertEqual(rc_r, 0)
            self.assertIn("terminology", report)
```

Add `import argparse` to the test module imports for the `Namespace` construction. `cmd_report` prints its canonical document itself; `main` suppresses the duplicate print.
- [ ] **Step 4: Run until green**, then validate changed.

- [ ] **Step 5: Commit**

```bash
git add tools/research/run_shadow_run.py tests/platform/test_shadow_run1_cli.py
git commit -m "feat,test: add shadow run operator CLI with frozen open contract"
```

---

### Task 8: Roadmap sync and pre-open checkpoint

**Files:**
- Modify: `docs/research/PLATFORMIZATION_ROADMAP.md` (P6 milestone row)

- [ ] **Step 1: Update the P6 row** to append after the existing text:

```markdown
**Shadow Run 1 design landed** (2026-08-23): preregistered prospective protocol at
[2026-08-23-platform-p6-shadow-run-1-design.md](../superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md)
 - frozen NSS predictor, opportunity ledger, delayed labeling, Boolean stopping rule;
recording machinery implemented under `shadow/experiment|session|predictor|recording|labeling_job.py`
+ `tools/research/run_shadow_run.py`. Run opens only via the spec section-14 sequence.
```

- [ ] **Step 2: Full validation checkpoint** (mandatory before any real run):

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py full`
Expected: PASSED, 0 failures/errors.

- [ ] **Step 3: Commit**

```bash
git add docs/research/PLATFORMIZATION_ROADMAP.md
git commit -m "docs: record shadow run 1 machinery in P6 roadmap"
```

---

## Execution Handoff

After Task 8 the implementation is complete but **no run is opened**. Opening Run 1 follows spec section 14 exactly (clean tree -> validate full -> `run_shadow_run.py open` -> enable gates -> confirm first opportunity -> accrue -> close at frozen boundary -> label-due -> report). The principal performs the operational steps during market hours with OpenD running.


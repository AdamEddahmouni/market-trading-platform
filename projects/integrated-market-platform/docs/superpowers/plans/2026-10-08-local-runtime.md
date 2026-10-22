# Local runtime implementation plan

Owner: one primary implementation agent; independent read-only reviewer at closure.

1. Add contract regressions in `tests/platform/test_local_runtime_validation.py`:
   below-floor/unknown telemetry, commit exhaustion, corrupt identity, profile
   limits, Stop, context completeness, timeout cleanup and interrupted benchmark.
   Run exact regression selectors, for example
   `python tools/imp.py test focused tests/platform/test_local_runtime_validation.py::RuntimeAdmissionTests::test_below_floor_has_precise_reason_and_no_quality_claim`.
2. Add `intelligence/inference/local_runtime.py` for pinned artifact verification,
   profiles and `readiness(manifest, sample=...)`; extend `local_resources.py`
   with existing native query fields (no new native APIs).
3. Integrate server admission, launch flags, Stop/deadline telemetry and cleanup
   in `local_provider.py`; bind profile identity to `inference_identity.py`.
4. Extend `tools/ai_screener_local_first_benchmark.py` through a bounded runner;
   preserve the original frozen manifest and append attempts. Test summaries
   independently of mocked model quality.
5. Expose the same contract through staged preview; add focused UI diagnostics
   test. Run focused backend/UI tests and inspect failures before broader checks.
6. Collect actual host/artifact/admission evidence without launching below floor.
   Save a versioned receipt and report null empirical quality if blocked.
7. Obtain independent read-only security/quality review and fix confirmed defects.
   Run one stabilized FAST/CHANGED/FULL ladder, UI suite/type/build, docs and
   monorepo guards. Record exact counts/exit codes/source identities.
8. Commit, open one focused PR, complete protected CI, merge normally, verify
   merge parents, implementation ancestry and canonical source. Stop scope.

# PR #487 closure and local runtime validation report

Evidence cutoff: 2026-10-09T00:30:18.184463+00:00. [Versioned acceptance receipt](../../artifacts/ai-screener-local-runtime-validation.json), [validation totals and source bindings](../../artifacts/ai-screener-local-runtime/validation-summary.json), [runtime architecture](../architecture/SCREENER_AI_LOCAL_RUNTIME_VALIDATION.md).

## A. Overall Verdict

Objective A: `LOCAL_FIRST_EXPERIMENTAL_ENGINE_INTEGRATED`.
Objective B: `LOCAL_RUNTIME_VALIDATION_READY_FOR_PROTECTED_INTEGRATION` at this receipt cutoff. Protected CI and actual merge verification follow this versioned evidence commit; they cannot be claimed in advance.
Empirical verdict: `LOCAL_MODEL_QUALITY_NOT_PROVEN_RESOURCE_BLOCKED`.

## B. PR #487 Closure

[PR #487](https://github.com/AdamEddahmouni/market-trading-platform/pull/487) merged normally with nine successful checks at 2026-10-08T23:11:43Z. Actual merge `930c0e0bfc51d3283bbd66baf49fe0f09d86acec`; parents `6bd88f7a30fad2c30ab9320bcd0c893dd15b6007` and `74775e934a49383263a5017a4944910a6eec8805`. Implementation `231be2ddf66b7236fec02947b7eb2c2424cca77d` is an ancestor. Expected qualification source and acceptance receipt match the PR head exactly. This actual merge is Objective B's canonical base.

## C. Objective B Implementation

Implementation SHA: `b9ae89263d5816ba5a043c359143ef30fe16b030`. `local_runtime.py` defines pinned artifact verification, versioned CPU profiles and one admission contract. `local_resources.py` extends the existing audited bridge with physical/commit/high-water telemetry. `local_provider.py` enforces admission, bounded flags, one launch lease, Stop/deadline and confirmed owned-process cleanup. `inference_identity.py` binds runtime configuration; `local_qualification.py` retains resource receipts. Staged preview and the existing Screener panel display the same refusal. `local_runtime_benchmark.py` adds append-only attempts, cumulative reservations, once-only holdout and offline economic planning; the old real entry point delegates to the pilot. The narrowly diagnosed Windows validator fix isolates worker console groups and reaps interrupted owned workers; test selection and assertions are preserved.

## D. Hardware and Resource Findings

Intel Core Ultra 7 256V, eight physical/logical cores. Usable physical RAM: 16,687,722,496 bytes (15.54 GiB). Arc 140V integrated GPU, driver 32.0.101.8626. Vulkan's 9071 MiB budget / 8361 MiB free is shared system capacity, not extra physical RAM or proven dedicated VRAM. CIM's legacy AdapterRAM field is not authoritative for dedicated memory. Hardware receipts use Windows CIM/PowerShell and the original audited native memory queries. Storage free was approximately 69.86 GB.

## E. Runtime Bottleneck Analysis

Latest controlled pilot: profile `cpu-4096/1`, available physical RAM 3640451072 bytes (3.39 GiB), memory load 78%, commit headroom 16400461824 bytes. Refusal: `LOCAL_RESOURCE_INSUFFICIENT_MEMORY`. Required startup availability: 9006840064 bytes (8.39 GiB), including the unchanged 4 GiB reserve. This is an admission refusal. No measured model memory exhaustion occurred. Current application allocations cannot be attributed to weights, KV, batch buffers or model threads.

## F. Optimizations Implemented

Candidate contexts 8192 / 4096; CPU-only, four threads, mmap, one slot, batch 128 / microbatch 64, f16 KV; automatic fitting and GPU/KV/operation offload disabled. Installed defaults were context 8192, GPU layers 99 and runtime batch 2048 / microbatch 512. Full template tokenization plus output allowance must fit; evidence is never silently truncated. Predicted peaks are 5,315,852,544 / 4,711,872,768 bytes; required availability 9,610,819,840 / 9,006,840,064 bytes. The full weight artifact, exact f16 KV dimensions and an uncalibrated 1.5 GiB runtime reserve underlie these predictions. Accepted profiles: none. No measured memory or quality improvement is claimed.

## G. Model Runtime Verification

Qwen/Qwen3-4B-GGUF:Q4_K_M; revision `bc640142c66e1fdd12af0bd68f40445458f3869b`; 2,497,280,256 bytes; SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`. Trusted b11269 archive SHA-256 `34a27c239727047adc5aed80b656b13373ff136b27d28bd898a14b7b7283695a`, executable/DLL set verified against its bytes. Runtime reports build 11269 / commit cee37ffea. The primary agent invoked 2 controlled pilots, including the final smaller-profile attempt after validation. Total runtime starts: 0; actual inference requests: 0. Launch and model execution are not claimed from command invocation alone.

## H. Frozen Benchmark

52 original cases: 26 development / 26 holdout. Dataset hash `9accf87fbb23fc6c9414e38808a44e0c08c5f3c5988701891a4697b151c59a84`; manifest hash `d17e9921713c75058f96c4a9ff77d9abee148f38c913d35f425a44515afd9644`; prompt hash `62754efd07ca9a2db3ed9527646d7d98616aaf869e5c8c2ab8bdb1e2edd05dd9`. Evidence, labels, splits, rubric and thresholds unchanged. Three planned cases per pilot, zero completed; all 52 remain empirically unmeasured. Holdout unconsumed. Latest attempt ran 3.016s; cumulative ledger 34.084s of the 7200-second ceiling. No repeat holdout or negative result discarded.

## I. Qualification Quality

Recall, false exclusions, accuracy, evidence-grounding failures, missing-capability errors, inconsistency and real uncertainty behavior remain null / NOT PROVEN. No fixture quality value fills a missing real result. Invalid and uncertain judgments advance under the unchanged experimental contract. Controlled relevance labels are not independent best-trade ground truth. Resource refusal is not evidence of below-target Qwen quality.

## J. Local Performance

Model startup/idle memory, high-water resident/committed allocation, per-candidate latency, input/output tokens and throughput are unmeasured because no model started. 50 / 100 / 500 / 4630 latency projections remain null. OS admission samples are actual measurements; allocation predictions are not. No fixture scale run is represented as real throughput.

## K. Premium Economic Feasibility

`STAGED_BUDGET_NOT_MEASURED`: no actual local advancement pool, premium count, requests, provider input, reserved output/reasoning or global comparison cost. Offline planning reuses provider and budget accounting with an empty key and denied network poster. It is reproducible engineering behavior, not measured savings. The prior exhaustive 4630-row reference is 104 requests / 9,450,435 estimated tokens versus reference limits 30 / 200,000; no staged whole-universe affordability claim follows.

## L. Experimental Method Isolation

Exhaustive remains operational default. Staged methodology approval/activation OFF; separate identity and persistence preserved. Full-universe accounting, uncertainty advancement, refresh, premium preflight and global comparison reused. Action Decision rejects experimental results. No Paper/Live orders, paid generations, model substitution, provider changes or new campaign.

## M. Failure and Resource Safety

Unchanged 4 GiB physical floor; 6 GiB process resident and committed ceiling; startup requires predicted allocation plus reserve in physical and commit headroom. Unknown telemetry refuses. Stop/deadline/final monitor failures reject results and clean up owned processes. Lease conflicts and unknown cleanup refuse redispatch; queue slots release even when cleanup raises. Abrupt API termination may leave an owned child and an interrupted lease; automatic orphan cancellation is not proven. No experiment-owned model process was launched or abandoned. The mistakenly identified ChatGPT processes were confirmed to belong to the active Codex application and left running; unrelated agent services were preserved.

## N. Independent Review

6 read-only rounds, remaining P1/P2: zero. Findings covered warm profile identity, completeness before holdout, high-water telemetry, final failure propagation, queue release, retained ownership, profile diagnostics, stale exclusions, corrupt ledgers, verification-cache identity and Windows worker cancellation. The final committed 22-path scope matched reviewed source. [Review dispositions](../../artifacts/ai-screener-local-runtime/independent-review.json). Reviewer edits/tests/runtime launches: zero.

## O. FAST / CHANGED / FULL

| Mode | Tests run | Passes | Skips | Failures | Errors | Exit | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| FAST | 23 | 23 | 0 | 0 | 0 | 0 | 2.531 |
| CHANGED | 5423 | 5388 | 35 | 0 | 0 | 0 | 234.138 |
| FULL | 8462 | 8409 | 53 | 0 | 0 | 0 | 709.241 |

Tests ran on stabilized code based on `930c0e0b`, subsequently committed at the implementation SHA. Validation summary binds every changed code file by normalized SHA-256; compressed raw receipts retain individual test and skip details. Earlier CHANGED had four failures because workspace TEMP introduced an enclosing Git checkout; normal OS TEMP resolved them with no assertions changed. Four incomplete FULL attempts were preserved; the owned-process Windows console interruption was diagnosed and fixed, including cancellation cleanup. A subsequent complete two-worker FULL ran 8462 tests with 53 skips, zero assertion failures and one WinError 10053 loopback connection abort. The exact failed test passed in isolation; the final complete inventory ran with one worker. FAST performance is OBSERVE_ONLY `REGRESSION` versus provisional 1.821s baseline; it is not concealed or treated as a gating pass. FULL performance classification `INCOMPATIBLE_BASELINE` is also informational; serial execution and this host differ from the provisional baseline.

## P. UI and Static Validation

29 focused runtime tests, two validator regression tests, and the corrected 79-test acceptance worker passed. Complete UI: 1415 tests / 180 files; final panel: 32 tests. Typecheck, production build and bundle budget exit 0; initial gzip bundle 100.76 KiB under 200 KiB limit. Lint, format, Python compile, 296-file documentation links, repository closure 256/256, and monorepo CI guard passed. The final report and evidence links receive a follow-up documentation check. Normal monorepo guard requires sibling checkouts; CI mode is the established isolated-worktree path. No gate weakened.

## Q. Objective B PR and Protected CI

One focused branch `codex/ai-screener-local-runtime-validation`. At this versioned receipt cutoff, protected CI and actual merge are pending. The user authorized normal protected integration; required strict validate and administrator enforcement must remain enabled. No protection bypass. Implementation and evidence commits are separate.

## R. Final Canonical Main

At this receipt cutoff, canonical Objective B base is actual PR #487 merge `930c0e0bfc51d3283bbd66baf49fe0f09d86acec`. After the Objective B protected merge, final local integration evidence verifies actual merge SHA/parents, implementation ancestry, PR-head source/acceptance equality and final origin/main. A prospective merge SHA is never treated as actual integration. The user's unrelated dirty checkout is preserved.

## S. Acceptance Receipt

The versioned receipt records model/runtime pins, measured host profile, admission predictions/refusals, append-only pilots, null empirical metrics, validation source bindings, review and authorization. Its G27/G28 status reflects the pre-merge cutoff; final protected integration evidence resolves those gates separately.

| Gate | Status at versioned cutoff | Evidence / limitation |
|---|---|---|
| G1 | PASS | Engineering requirement verified; empirical quality is separate. |
| G2 | PASS | Engineering requirement verified; empirical quality is separate. |
| G3 | PASS | Engineering requirement verified; empirical quality is separate. |
| G4 | PASS | Engineering requirement verified; empirical quality is separate. |
| G5 | PASS | Engineering requirement verified; empirical quality is separate. |
| G6 | PASS | Engineering requirement verified; empirical quality is separate. |
| G7 | PASS | Engineering requirement verified; empirical quality is separate. |
| G8 | PASS | Engineering requirement verified; empirical quality is separate. |
| G9 | BLOCKED | Two versioned candidate profiles evaluated and resource-blocked; no accepted optimization. |
| G10 | PASS | Engineering requirement verified; empirical quality is separate. |
| G11 | PASS | Engineering requirement verified; empirical quality is separate. |
| G12 | PASS | Engineering requirement verified; empirical quality is separate. |
| G13 | BLOCKED | Bounded real pilot invoked by primary agent; refused before runtime launch, not a successful inference. |
| G14 | PASS | Engineering requirement verified; empirical quality is separate. |
| G15 | BLOCKED | Real runtime admission refused; no observed runtime or quality measurement. |
| G16 | NOT PROVEN | No real local qualification output; unknown metrics preserved as null. |
| G17 | BLOCKED | Real runtime admission refused; no observed runtime or quality measurement. |
| G18 | NOT PROVEN | No real local qualification output; unknown metrics preserved as null. |
| G19 | NOT PROVEN | No real local qualification output; unknown metrics preserved as null. |
| G20 | PASS | Engineering requirement verified; empirical quality is separate. |
| G21 | PASS | Engineering requirement verified; empirical quality is separate. |
| G22 | PASS | Engineering requirement verified; empirical quality is separate. |
| G23 | PASS | Engineering requirement verified; empirical quality is separate. |
| G24 | PASS | Engineering requirement verified; empirical quality is separate. |
| G25 | PASS | Engineering requirement verified; empirical quality is separate. |
| G26 | PASS | Engineering requirement verified; empirical quality is separate. |
| G27 | NOT PROVEN | Pending protected CI and actual merge at this versioned receipt cutoff; final Git/GitHub integration verification is separate. |
| G28 | NOT PROVEN | Pending protected CI and actual merge at this versioned receipt cutoff; final Git/GitHub integration verification is separate. |

## T. Remaining Genuine Blockers

Safe physical-memory admission prevents actual Qwen execution. Empirical quality, false exclusions, memory improvement, latency, cold-scan feasibility and premium savings remain unproven. Uncalibrated allocation reserve and abrupt-crash owner recovery remain explicit limitations. No smaller model, lower floor, unsafe paging policy or methodological change selected.

## U. Scope Stop

PR #487 closure and the Local AI Runtime Optimization/Real-Model Validation feature were completed to their evidenced integration states. The exhaustive AI Screener remains operationally authoritative, staged methodology activation remains OFF, no unauthorized provider spending or trading occurred, and no subsequent development lane was started.

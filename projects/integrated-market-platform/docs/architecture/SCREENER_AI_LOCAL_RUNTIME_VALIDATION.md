# Resource-safe local Screener runtime

**Authority:** runtime engineering contract. Experimental methodology approval
and operational activation remain **OFF**. The exhaustive Screener is default.

The existing `LocalLlamaServer` serves pinned Qwen3-4B Q4_K_M, revision
`bc640142c66e1fdd12af0bd68f40445458f3869b`, SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
The trusted b11269 archive anchors executable and adjacent DLL verification;
manifest hash claims cannot override these pins. No runtime downloads occur.

## Readiness and admission

`local-runtime-readiness/1.0.0` is the single calculation used by server admission,
staged preview and real benchmark. It reports artifact verification, model/hash,
runtime/profile, context/batch/KV, physical RAM, OS commit headroom, predicted
and observed peaks, timestamp and precise refusal. Unknown telemetry refuses
experimental execution. Windows uses only its two existing audited read-only
native APIs. The pinned Windows artifact is unavailable on other platforms.

The **4 GiB available physical-memory floor** and **6 GiB process ceiling** are
unchanged. Process committed memory also has a 6 GiB ceiling. Startup reserves
estimated allocation plus the 4 GiB floor in physical and commit headroom.
The estimate counts all 2,497,280,256 weight bytes, f16 K+V for 36 layers / 8 KV
heads / 128 head dimension, and 1.5 GiB uncalibrated runtime/graph/buffer reserve.
This is a conservative prediction, not measured peak allocation.

Candidate profiles `cpu-8192/1` and `cpu-4096/1` use one slot, four generation
and prompt threads, 128 batch / 64 microbatch, f16 KV and mmap. Device and
operation/KV offload and automatic fitting are OFF. Full chat-template tokens
plus 384 output tokens must fit; otherwise the evidence is refused intact.
The pinned managed runtime uses bounded flags for ordinary synthesis too,
so warm reuse cannot represent a different qualification profile.

Flags were verified against the installed runtime and
[pinned llama.cpp argument source](https://github.com/ggml-org/llama.cpp/blob/b11269/common/arg.cpp).
KV dimensions agree with the
[Qwen configuration](https://huggingface.co/Qwen/Qwen3-4B/blob/main/config.json).
Integrated GPU budgets draw on shared system RAM and add no admission capacity.
Profiles are not accepted optimizations until real memory and quality are measured.

## Lifecycle

Preserve the existing one-running / one-waiting queue. A runtime lease serializes
launches across processes; a foreign or interrupted lease refuses startup.
Only its owner removes a lease after confirmed child exit. No foreign alias is
adopted or killed. Monitor physical and committed memory, OS high-water working
set, Stop and bounded deadline through startup/inference. Cleanup terminates,
waits, then kills and waits if needed. Cleanup exceptions retain ownership and
unconditionally release inference queue slots. Final resource failure rejects
the response before qualification can validate or cache it.

An abrupt API-process crash cannot promise child cancellation. Interrupted
leases and benchmark reservations block redispatch. Preserve PID/log/receipts
for explicit owner recovery; never kill based only on a stale PID. This remains
a crash-recovery limitation, not evidence that abrupt cancellation succeeded.

## Frozen real benchmark

From the IMP tree using its resolved Python environment:

```powershell
python tools/local_runtime_benchmark.py --phase pilot --profile cpu-8192/1
python tools/local_runtime_benchmark.py --phase development --profile cpu-8192/1
python tools/local_runtime_benchmark.py --phase holdout --profile cpu-8192/1
```

Use the original frozen 52 cases in `artifacts/ai-screener-local-first/manifest.json`.
Dataset, evidence, splits, labels, prompt, rubric and targets stay unchanged.
The old `real` entry point delegates to the bounded pilot. No repeated scale
loop or paid inference runs. Each attempt preserves admission, outputs and times.

The shared cache holds the exclusive benchmark lock, cumulative budget and
configuration history. Carry legacy budget use forward. Reserve 720 seconds
before each call against the **7200-second cumulative ceiling**; charge actual
wall time including startup/cleanup. Unknown outcomes and corrupt state refuse
resumption. Successful development must complete every admissible case with
valid outputs before holdout can run. Holdout is consumed once per configuration,
bound to model/dataset/prompt/profile and implementation content. Original stale
cases are separate from failures. Every eligible case must dispatch for complete
recall; invalid/uncertain assessments advance and failures remain visible.
Controlled relevance labels are not trade ground truth or premium references.

The offline planner applies existing provider accounting and global-reduction
reserves to actual advancement, with 30 requests / 200,000 tokens as reference
quotas. It has no credentials and a denied network poster. Partial pool planning
does not prove whole-universe affordability. 50/100/500/4630 workload estimates
are projections from observed latency; absent execution they stay null.

## Observed result

October 8, 2026 pilot: artifacts verified; admission refused at 2,670,833,664
available bytes (2.49 GiB). Zero runtime starts and generation requests. Both
profiles remain resource-blocked; accepted profiles: none. Actual model peaks,
load/idle memory, quality, recall, false exclusions, throughput, premium pool
and savings are **NOT PROVEN**. This is admission failure, not measured runtime
exhaustion or evidence of poor model quality. No holdout was consumed.

See the [acceptance receipt](../../artifacts/ai-screener-local-runtime-validation.json)
and [final report](../reports/AI_SCREENER_LOCAL_RUNTIME_VALIDATION_REPORT.md).

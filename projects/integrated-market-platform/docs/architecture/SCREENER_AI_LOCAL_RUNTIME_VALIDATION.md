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

## Laptop model registry and explicit selection

The existing 4B artifact, legacy manifest, default selection and profiles remain
preserved. `local_models.py` adds official Qwen3-0.6B and Qwen3-1.7B **Q8_0** pins.
The official repositories at the recorded revisions expose only Q8_0; the
preferred Q4_K_M is unavailable. No third-party quantization is substituted.
Sources: [0.6B official files](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a)
and [1.7B official files](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/tree/90862c4b9d2787eaed51d12237eafdfe7c5f6077).

Explicit installation from the IMP tree:

```powershell
python tools/news/setup_laptop_models.py --model Qwen/Qwen3-0.6B-GGUF:Q8_0
python tools/news/setup_laptop_models.py --model Qwen/Qwen3-1.7B-GGUF:Q8_0
python tools/news/setup_laptop_models.py --model Qwen/Qwen3-0.6B-GGUF:Q8_0 --check
```

Weights and separate manifests live under `IMP_CACHE_DIR` (Windows default
`%LOCALAPPDATA%\IMP`), with weights in `models/weights/<revision>/` and manifests
`models/Qwen3-0.6B-Q8_0.json` / `models/Qwen3-1.7B-Q8_0.json`.
New manifests use cache-relative paths. Installation stages an exclusive partial
file, verifies exact bytes and SHA-256, verifies the pinned runtime archive and
all executables/DLLs, then atomically publishes the manifest. Offline checking
also verifies the resolved saved manifest and profile. Runtime never downloads.
`models/local-llm.json` and the 4B weights are untouched.

Both smaller models use `cpu-4096/1`: 4096 context, f16 KV, 128 logical batch,
64 microbatch, four CPU threads, one slot, mmap, no device/operation/KV offload,
no automatic fitting. Startup/inference deadlines remain 180/120 seconds.
KV estimates use 28 layers, eight KV heads, head dimension 128, as recorded in
the official [0.6B configuration](https://huggingface.co/Qwen/Qwen3-0.6B/blob/main/config.json)
and [1.7B configuration](https://huggingface.co/Qwen/Qwen3-1.7B/blob/main/config.json).
The unchanged 1.5 GiB graph/buffer reserve and 4 GiB free-memory floor produce
startup requirements of **6.53 GiB (0.6B)** and **7.65 GiB (1.7B)**.
These are conservative estimates, not measured peaks or accepted optimizations.
Evidence exceeding context is refused intact. The unchanged 4B requirements are
8.39 GiB at 4096 context and 8.95 GiB at 8192 context. The earlier 8.39 GiB pilot
used `cpu-4096/1`; the legacy manifest retains its 8192 context. The process and
process-commit ceilings remain 6 GiB.

The existing AI Screener panel exposes an **Experimental local model** selector
when the operator chooses Local-first experimental. It submits `local_model_id`
with the run scope; the backend validates membership and exact identity. The
selection is part of result/query identity and does not change the paid engine,
machine-wide synthesis setting or default exhaustive method. Missing or invalid
selected artifacts never fall back. Switching stops only previously owned
managed server objects sharing the port, under the inference slot. Foreign
processes are never adopted or terminated.

Preview reports all three configurations, pins, installation, quantization,
resource admission, current available memory, last benchmark error and observed
performance. Observations are external benchmark summaries with model hash and
revision checks. Admission readiness grants no quality or trading approval.

```powershell
python tools/local_runtime_benchmark.py --model Qwen/Qwen3-0.6B-GGUF:Q8_0 --phase pilot
python tools/local_runtime_benchmark.py --model Qwen/Qwen3-0.6B-GGUF:Q8_0 --phase development
# Only after a complete valid development run with frozen configuration:
python tools/local_runtime_benchmark.py --model Qwen/Qwen3-0.6B-GGUF:Q8_0 --phase holdout
```

The same commands support 1.7B explicitly. The frozen 52 cases, 26/26 splits,
evidence hashes, labels, prompt and quality targets remain unchanged. All models
share the existing cumulative two-hour ledger. Attempts are append-only;
holdout remains once per frozen successful-development configuration.

October 9 laptop pilots and development admission attempts verified both
artifacts but refused launch below the safety floor. **Zero starts and zero
generations**: runtime/contract compatibility, qualification quality, recall,
grounding, peak model memory, throughput and premium savings are **NOT PROVEN**.
The holdout was not consumed. 20/50/100/500/4630 projections stay null without
real latency measurements; the premium planner reports not measured rather than
claiming affordability against reference quotas. See the
[laptop acceptance receipt](../../artifacts/ai-screener-laptop-local-models-acceptance.json).
Experimental activation, paid generations and Paper/Live submissions remain OFF.

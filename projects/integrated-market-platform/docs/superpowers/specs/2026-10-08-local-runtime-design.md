# Resource-safe local runtime design

The owner authorized implementation and protected integration in the detailed
coordinator request. Canonical predecessor: `930c0e0bfc51d3283bbd66baf49fe0f09d86acec`.

Extend the existing LocalLlamaServer and LocalChatInferenceProvider. A single
readiness contract verifies the pinned Qwen model and trusted runtime archive,
versioned profile, physical RAM, system commit headroom, and conservative peak
estimate. Unknown telemetry refuses experimental qualification. Keep the 4 GiB
available floor and 6 GiB process ceiling; also monitor committed memory. Native
calls stay within the existing audited read-only Windows bridge.

Explicit CPU profiles preserve f16 KV, one slot, four threads, mmap and complete
evidence. Baseline context is 8192; the diagnostic smaller-context profile is
4096 and refuses oversized tokenized inputs. Batch/microbatch reduce to 128/64.
Profiles are candidates, never accepted quality optimizations without measured
memory and benchmark quality. No GPU profile is promoted on shared-memory claims.

Startup checks admission server-side before spawn; monitor startup and inference,
Stop and deadlines; reap only owned processes. Never reuse a foreign runtime.
Serialize profile changes against the existing shared inference slot.

Extend the frozen benchmark tooling with append-only attempt directories,
exclusive execution lock, cumulative worst-case budget reservations, interrupted
attempt preservation, development pilot and once-only holdout configuration.
Keep original manifest, evidence, labels, prompt and evaluation rules unchanged.
Report real outputs separately from fixture coverage. Unavailable quality,
throughput and premium pool projections stay null, never inferred from mocks.

Expose readiness on the existing staged preview and preserve exhaustive default,
experimental persistence, uncertainty advancement and Action Decision rejection.

Alternatives considered: a second server duplicates lifecycle and authority;
lowering admission changes safety policy and lacks measurements. Neither is used.

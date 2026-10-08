# AI Screener budget efficiency

This extends [full-universe coverage](SCREENER_AI_FULL_UNIVERSE_COVERAGE.md).
It preserves the existing eligibility gates, identity order, 50-row maximum,
320,000-byte canonical packet maximum, tournament selection method, output wire
3.0.0, and global zero-to-five selection. It grants no Paper or Live authority.

## Default behavior

Before holding the whole run, the planner validates successful cached first-pass
answers. It reserves only missing batches. If all first-pass answers are reusable,
it follows their finalist identities and validates every global comparison's
exact context. Only a fully reusable comparison chain has zero reserved generation
requests. Mixed runs retain the conservative worst-case comparison allowance.
No candidate is removed to lower cost.

Each request reacquires and gates current evidence. A planned reuse that becomes
invalid stops with REUSE_INVALIDATED_AFTER_PLANNING; it cannot silently generate
a replacement call. A miss that the plan reserved may generate once. No automatic
retry or recurring paid loop is introduced.

## Canonical manifest and reuse identity

The coverage ledger retains a per-request canonical model-evidence manifest and
its semantic hash before inference. Manifests contain facts, source clocks,
freshness deadlines, source identities, evidence ownership, missing/blocked/weak
states, and current/reference distinctions. Historical receipt identities remain
unchanged. Manifests are diagnostic evidence, never execution authority.

Reuse fingerprints include the whole comparison context, scope, instrument order,
every admitted observation and deadline, missing states, prompt content, output
schema, wire version, inference configuration, optimizer version, encoding, model,
provider, reasoning settings, and local model/runtime manifest identity. Dictionary
key ordering and integral float notation normalize; list order and facts do not.
Only the named news snapshot and alignment evaluation clocks are excluded. A fact
whose name is cutoff remains material.

Every competitor bounds reuse expiry, including unselected competitors. A cache
hit preserves its original run and cutoff; reuse records a separate validation
time. The stored envelope, evidence digest, provider and prompt contract, state,
clocks, schema, and candidate-local evidence references are revalidated against
the current request. Cache receipts cannot refresh evidence or bypass the existing
Action Decision and Paper checks.

Successful paid/local answers may persist in the external IMP cache at
inference/screener-reuse.sqlite, bounded to 512 entries and 128 MiB, with a
512,000-byte entry bound. Checksums detect accidental corruption; semantic
revalidation remains necessary even when a checksum matches. Corruption is a miss.
Unversioned local engines cannot reuse. Memory failures retain only the existing
cooldown behavior. No interrupted parent run resumes after restart.

## Optional model input compaction and batching

IMP_AI_SCREENER_COMPACT_INPUT=1 selects prompt v4 and the versioned
ai-screener-evidence-columns/1.0.0 encoding. Candidate and evidence column names
appear once; values retain order and ownership. Each row carries absent indices
so missing and null remain distinct. The deterministic decoder reconstructs the
manifest, and semantic hashes must match before inference. The canonical byte
bound still applies. Output schemas and references are unchanged.

IMP_AI_SCREENER_ADAPTIVE_BATCHES=1 permits the longest fitting prefix within an
existing 50-row group instead of repeated bisection when context forces a split.
It preserves membership and order but can change comparison composition.
Both options are off by default. A real provider's compact-input comprehension,
strict-schema generation, and composition-sensitive candidate quality have not
been demonstrated by these fixtures. These switches require matched provider
quality evaluation before production enablement. Existing unequal competition in
tail/split batches remains an unresolved P2 limitation.

## Tokens, holds, and cost

Accounting includes the serialized request's system and tool schema, output cap,
and configured reasoning headroom. Estimates use the existing model-calibrated
UTF-8 ratio and retain the previous reservation floor. That ratio was conservative
for the preserved October 7 controls; it is not a universal tokenizer bound.
The plan records the first available provider count. Each newly acquired Screener
generation request also obtains an exact count where the engine supports one,
raises its reservation when needed, and refuses an invalid body or context.
Unavailable count endpoints retain the disclosed estimate fallback.

Independent processes coordinate quota loads, holds, reservations, settlements,
and releases through a SQLite transaction lock beside the shared quota file.
Malformed existing state fails closed. Partial or unknown usage keeps the
reservation charged. Unclassified provider errors do not become free requests.
Reported usage above reservation blocks further generation and prevents a
completed selection. Without an exact count, an unexpectedly billed first
overrun cannot be retroactively prevented; it is exposed and stops further spend.

IMP_SYNTHESIS_PRICE_SCHEDULE optionally supplies a JSON object with model_id,
currency USD, input_per_million, output_per_million, source, verified_at, and
valid_until. A missing, mismatched, or expired schedule yields no dollar estimate.
Estimated dollars are not billed dollars. No model or budget configuration is
changed by this feature.

## Measurements and limits

The [acceptance receipt](../../artifacts/ai-screener-budget-efficiency-acceptance.json)
contains frozen baseline/optimized cold, warm, and partially changed controls at
0, 20, 50, 100, 500, 4,630, and 20,000 rows, source provenance, validation,
independent-review disposition, and the separate October 7 controlled replay.
The benchmark uses the production coverage path with fixture inference, frozen
clocks, and isolated stores. No generation is billed and no active campaign runs.

In the 4,630-row control, 4,605 eligible rows still require 93 first-pass batches
and one actual global comparison when cold. Full reuse eliminates all 94
generation calls; changing one candidate requires two. Optional compaction reduces
model-evidence bytes from 8,842,311 to 5,831,579 (34.05%) and estimated rendered-input
tokens from 6,167,394 to 4,197,714 (31.94%). These are fixture estimates.

Cold planning still needs at least 104 worst-case generation slots and millions
of estimated tokens, far above the default 30 requests / 200,000 tokens.
Reuse is useful only while all evidence and context remain valid; real changing
quotes may provide far fewer hits. Local replay latency does not improve with
reuse because acquisition, semantic revalidation, and immutable manifests still
run. Traced benchmark latency is diagnostic, not a live-provider SLA. No stronger
candidate quality or trading-return claim follows from reduced requests.

The API/UI expose new requests, reused answers, reported tokens, plan requirements,
and unavailable or configured dollar estimates. Progress counts reflect completed
reuse/generation work; planned demand remains in the plan. Partial results remain
diagnostic and cannot enter Action Decision.

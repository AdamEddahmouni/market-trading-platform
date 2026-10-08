# Screener AI full-universe coverage

Classification: CURRENT_CANONICAL_TRUTH, SOFTWARE_CONTROLLED software contract.
Method: `ai-screener-coverage/1.0.0` (`FULL_UNIVERSE_TOURNAMENT_REDUCTION`).
This document does not establish empirical provider proof, forecasts,
profitability or trading authority. No paid model generation has been made
under this method; every test and the acceptance receipt use controlled engines.

It extends [Screener AI candidate reduction](SCREENER_AI_CANDIDATE_REDUCTION.md),
which remains the contract for one model request (packet, wire, prompt,
validation). This document is the contract for a **run**: how the whole Screener
query is covered with many such requests.

## What changed and why

Until this method, a run read the first 50 rows (20 before PR 481) of the sorted
Screener result and sent them in one request. A US-equities query matches about
4,630 rows, so the model saw about 1% of the universe, and "no candidates"
described only that 1%. That method is now named
`ai-screener-intake-head/1.0.0`. It is still what the automatic reevaluation
passes, the risk control and the next-session snapshot use; it never claims
coverage. Runs stored under it are unchanged.

An operator Run now does this:

```text
active Screener query
  -> complete enumeration of one pinned result set
  -> classification of every row by the existing evidence gates
  -> plan: bounded batches in an identity-fixed order, and the whole run's budget
  -> one bounded model request per batch, each on evidence acquired for it
  -> batch finalists (provisional)
  -> global comparison of finalists until one request holds them all
  -> 0 to 5 final candidates, stored as one candidate run
  -> existing Action Decision path
```

## Three kinds of coverage

They are reported separately and are never substituted for one another.

| Term | Meaning | Reported as |
|---|---|---|
| Universe coverage | Every row of the query was enumerated and is in exactly one accounting bucket | `enumeration.complete`, `reconciled` |
| Evidence eligibility | Every enumerated row was assessed by the existing deterministic gates | `assessed_count`, `eligible_count`, `counts.by_class` |
| AI evaluation coverage | Every eligible row was sent to the model in a request that answered | `ai_evaluated_count`, `ai_coverage_pct`, `coverage_complete` |

`coverage_complete` is true only when enumeration is complete, the four
buckets add up to the universe, no eligible row is unprocessed and every
planned batch answered. A row that was eligible when classified and could not
be sent when its request was due (its quote aged out, or the quote source
failed) is unprocessed, so such a run is never complete and its
`ai_coverage_pct` counts that row in the denominator. `selection_complete`
additionally requires the global comparison to have finished on evidence that
was still current when the answer arrived. Nothing else is called complete.

## Enumeration

`ui_api/screener_ai_universe.py` pages the existing Screener reader at
`MAX_PAGE_LIMIT` (500) with the first page's `result_set_id` pinned for every
later page. Sort decides the order rows are read in and nothing else. The run
ends with `UNIVERSE_ENUMERATION_FAILED` and evaluates nothing when it cannot
prove completeness:

| Reason | Condition |
|---|---|
| `RESULT_SET_CHANGED` | The reader refused the pinned set, or a page came from another set |
| `RESULT_COUNT_CHANGED` | A later page reported a different total |
| `DUPLICATE_INSTRUMENT` | An `instrument_id` appeared twice |
| `SHORT_PAGE` | An empty page arrived before the total was reached |
| `RESULT_COUNT_MISMATCH` | Rows read differ from the reported total |
| `ROW_IDENTITY_MISSING`, `PAGE_OVERSIZED`, `PAGE_BOUND_EXCEEDED` | Malformed page or more than 400 pages |

Rows are held in memory for the run only (measured peak for 4,600 rows and
20,000 rows is in the acceptance receipt).

## Classification

No threshold is introduced. Each row goes through the same
`observations_for_row` and `build_candidate` as before; its class is read from
their output (`intelligence/inference/coverage_plan.py::classify`).

| Class | Derived from | Bucket |
|---|---|---|
| `ELIGIBLE` | `sufficient` is true: a strong current `QUOTE` with a price plus one other non-weak item | sent to the model |
| `INELIGIBLE` | A current price is present but the second item required by the existing rule is not (`NO_SECOND_STRONG_EVIDENCE`), or the quote is only weak | `ineligible` |
| `UNSUPPORTED` | `NOT_ENTITLED`, `NOT_CONFIGURED`, or the vendor refused the code by name | `ineligible` |
| `EVIDENCE_STALE` | Quote blocked with `STALE`, `AGE_EXCEEDS_POLICY`, `SESSION_CLOSED`, `NON_CURRENT_DELIVERY` | `evidence_blocked` |
| `EVIDENCE_UNAVAILABLE` | No quote observation, `NO_OBSERVATION_TIME`, `FUTURE_OBSERVATION_TIME`, no usable facts | `evidence_blocked` |
| `PROVIDER_UNAVAILABLE` | The bulk snapshot failed (`MARKET_SNAPSHOT_*`) or the source state says so | `evidence_blocked` |
| `AWAITING_EVIDENCE` | `AWAITING_DATA`, `PENDING`, `CONNECTING` | `evidence_blocked` |
| `AI_EVALUATED` | The row was in a request that answered | `evaluated` |
| `UNPROCESSED` | Eligible but not evaluated; always carries the reason | `unprocessed` |

Missing or stale evidence is never an economic rejection and is never counted
as evaluated. A row with a current price and nothing else may still be lifted
to `ELIGIBLE` by admitted news, exactly as the existing sufficiency rule
allows; only those rows are news-projected during classification. Already-owned
order-flow state is read at classification as it is for every request, so a
row is classified on the evidence it would be sent with. If the bulk quote
source returns nothing at all and no row is eligible, the run ends
`EVIDENCE_PROVIDER_UNAVAILABLE`, not `NO_ELIGIBLE_ROWS`: that outcome says
nothing about the rows.

Market evidence stays bounded. For equities and ETFs the run takes one bulk
OpenD snapshot of the enumerated rows through the existing
`EtfSnapshotSource` (400 codes per call, at most 50 calls; 4,630 rows is 12
calls). Other universes use the evidence their rows already carry. No
subscription is requested. A row the vendor returns nothing for stays
explicitly unavailable; its clock is never filled in. Shared news (Finviz,
RSS) is refreshed under its own TTL; per-instrument news providers stay
cache-only.

## Batch planning

Eligible rows are ordered by `sha256(result_set | instrument_id)`. Batch
membership therefore does not depend on sort, page, position, symbol length or
how much metadata a provider returns for a row. A partial run covers an
unbiased slice, never "the top of the list".

A batch is the largest group that satisfies all three limits:

- at most `MAX_INTAKE` (50) rows: the only strict-schema grammar size the
  provider has been shown to accept (PR 484);
- at most `MAX_PACKET_BYTES` (320,000) after the existing deterministic
  `fit_news` thinning, which is recorded (`reference_evidence_thinned`);
- estimated input plus output and thinking headroom within the selected
  model's context window.

A group over a limit is split in half and re-planned; a single row that cannot
fit is `UNPROCESSED` (`IRREDUCIBLE_PACKET_OVERSIZE` or
`PACKET_EXCEEDS_CONTEXT_WINDOW`) and the run cannot be complete.

Comparison rounds are planned for the worst case that every batch returns five
finalists: groups of 50 until one remains (`reduction_rounds`). One batch needs
no comparison round, because one request already compared every eligible row.

## Budget

The budget is the existing shared daily allowance
(`quota/anthropic-synthesis.json`; 200,000 tokens and 30 requests per UTC day
by default), shared by News synthesis, the AI Screener, Action Decisions and
reevaluation. This method adds no private budget and never raises a limit.

- **Estimate.** `estimate_tokens` now bounds input tokens from UTF-8 bytes with
  a per-model ratio set below the provider's own count of the controlled
  50-candidate packet (2.2 bytes per token for Haiku 4.5, 1.5 for Sonnet 5.5
  and Opus 5.5 and for any unmeasured model). The former three-characters rule
  under-counted every Claude model. The estimate applies to every reservation,
  not only this feature.
- **Provider count.** Where the engine offers a free token count, the first
  planned batch is counted before anything is held. A higher count raises
  every batch by the same ratio plus a margin; a lower count never shrinks a
  reservation. A request the provider rejects ends the run before any spend.
- **Hold.** The whole plan (every batch, every comparison round, output and
  thinking headroom, plus a 5% drift margin) is placed as one hold. Every
  other AI operation sees held requests and tokens as used. The run's calls
  draw from its hold and cannot exceed it. What the run did not use is released
  when it ends.
- **Does not fit.** No model is called. The run ends
  `AI_COVERAGE_BUDGET_INSUFFICIENT` with eligible rows, planned batches,
  required and available tokens and requests; every eligible row is
  `UNPROCESSED: BUDGET_INSUFFICIENT`.
- **Outgrown mid-run.** Evidence is re-acquired per request, so a request can
  exceed its planned size. If the hold cannot cover it the request is refused,
  later batches do not start, and the run ends `PROVISIONAL_PARTIAL_COVERAGE`.
- **Unknown outcome.** A timeout keeps the worst case charged (unchanged rule).
- **Local model.** A local engine has no budget: no token or request cap and no
  hold. Only the row, byte and context-window limits bound a batch.

Measured consequence, recorded in the receipt: a controlled 50-row packet with
quote and technicals only is about 96,000 bytes, so under the default allowance
a run completes only for a query with about 50 eligible rows on Sonnet or Opus
and about 100 on Haiku. An unfiltered equities universe needs millions of
tokens and about 104 requests. That is a resource limit the run reports; it is
not worked around.

## Model requests

Every request is the existing `CandidateReducer.reduce`: prompt
`screener.ai_candidate_reduction.v3`, `ai-screener-wire/3.0.0`, strict schema,
exact decode, canonical validation, the model the operator selected. There is
no free-form fallback, no model substitution and no retry.

Immediately before each request the batch's rows are read again from the
Screener as it serves them now, equities and ETFs get a new bounded snapshot,
a new cutoff is taken, and the candidates are rebuilt. Membership stays the
enumeration's: a row that has since left the result is read from the
enumeration and its own clocks decide. Nothing is acquired beyond what the
Screener already serves and the bounded snapshot. A row no longer sufficient
at that cutoff is not sent; it becomes `UNPROCESSED` with
`<CLASS>_AT_REQUEST_CUTOFF` and its reason codes. Each request records its
evidence cutoff, completion time, expiry, input hash and tokens. No
observation later than a request's cutoff can enter it.

## Global comparison

Batch answers are **finalists**, not results. They are recorded as batch
receipts and are never stored as a candidate run.

Finalists are deduplicated, ordered by identity with a per-round salt, given
fresh evidence, and compared with the same request contract in groups of up to
50. Winners advance until one group remains; that group's answer is the final
0 to 5. A finalist whose evidence is no longer sufficient at the comparison
cutoff is not sent and is named in `reduction.finalists_excluded`; a selection
made without it carries the reason `FINALISTS_EXCLUDED_AT_FINAL_CUTOFF` and a
limitation saying so. If no finalist is admissible the run is
`PROVISIONAL_PARTIAL_COVERAGE` (`NO_FINALIST_ADMISSIBLE_AT_FINAL_CUTOFF`):
nothing was compared. If the final answer arrives after the evidence it cites
has expired, it is not a selection: the run is `PROVISIONAL_PARTIAL_COVERAGE`
(`FINAL_SELECTION_EXPIRED_DURING_INFERENCE`), its picks are listed as
provisional and nothing is stored. Quotes live 60 seconds, so a slow engine
will meet this often; that is reported, not hidden.

"Selected" means selected by this documented tournament of bounded comparisons
made by the configured model. It is not a ranking score and not a claim of
best return. A model may choose differently in a different comparison context;
the receipts record every group, cutoff and answer.

## Result and the Action Decision boundary

| Terminal status | Meaning | Stored candidate run |
|---|---|---|
| `GLOBAL_SELECTION_COMPLETE` | Complete coverage and a finished comparison with at least one selection whose evidence is current | Yes, as `CU-<run id>` |
| `COMPLETE_NO_SELECTION` | Complete coverage; nothing selected | No |
| `NO_ELIGIBLE_ROWS` | Every row assessed; none eligible; no model called | No |
| `EMPTY_UNIVERSE` | The query matched no rows | No |
| `EVIDENCE_PROVIDER_UNAVAILABLE` | The quote source returned nothing; no row could be assessed as eligible | No |
| `PROVISIONAL_PARTIAL_COVERAGE` | A batch or comparison failed, an eligible row could not be sent, no finalist was admissible, or the final answer outlived its evidence | No |
| `AI_COVERAGE_BUDGET_INSUFFICIENT` | The plan did not fit the budget; no model called | No |
| `UNIVERSE_ENUMERATION_FAILED` | The result could not be read completely | No |
| `STOPPED` | Operator Stop | No |
| `INTERRUPTED` | A server restart ended the run | No |
| `FAILED` | Engine refused, or an unexpected error | No |

Only the first status stores anything the Action Decision layer can load. The
stored record is an ordinary candidate run whose picks and evidence both come
from the final comparison, with an additive `universe_coverage` block (method,
software SHA, counts, plan, budget, cutoffs). Its `valid_until` is bounded by
the evidence it cites, so the existing `CANDIDATE_EXPIRED`, quote-freshness and
risk gates apply unchanged. A partial result carries `state: INCOMPLETE`, an
empty `candidates` list and a `provisional` list for inspection; the panel
offers no Action Decision for it. The Action Decision, Paper, risk, SMA stop,
lifecycle and evaluation code is not modified. There is no automatic Paper
submit and no Live authority.

Accounting invariant, checked at every terminal write:

```text
evaluated + ineligible + evidence_blocked + unprocessed == universe_count
```

## Run lifecycle, Stop and recovery

Stages (`screener-ai-screener-run/2.0.0`): `ENUMERATION`, `ELIGIBILITY`,
`PLANNING`, `BUDGET_HELD`, `BATCH_INFERENCE`, `GLOBAL_REDUCTION`, `STORED`.
`progress` holds counts the run has actually produced (`universe_count`,
`assessed_count`, `eligible_count`, `batches_planned`, `batches_completed`,
`rows_evaluated`). No percentage is derived from assumed model latency.

- **Duplicate Run.** One run per account; a second POST joins it and starts
  and spends nothing.
- **Stop.** `POST /screener/ai-screener/runs/{run_id}/stop` (`state.write`).
  No further request starts. A request already sent is not claimed cancelled:
  the provider offers no confirmed cancellation, so it finishes, is recorded
  and stays charged. Finished receipts are kept; the unused hold is released.
- **Client disconnect.** The run lives on the server; a reloaded page
  re-attaches.
- **Restart.** Receipts are appended to the coverage ledger
  (`local_state/ai_screener_coverage.py`, table
  `ai_screener_coverage_records`, insert-only) as the run goes. A status read
  reports a run with no terminal record that is not alive in this process as
  interrupted and writes nothing. The next operator write (Run or Stop) closes
  it `INTERRUPTED`; a request with no recorded outcome is listed as an unknown
  provider outcome and stays charged; only the never-reserved part of the hold
  is released.
- **Orphaned hold.** A hold nobody has drawn from for 900 seconds lapses. A
  live run draws at least once per request, and a request times out in at most
  300 seconds, so only a hold whose run is gone (a crash with no ledger, or an
  engine switched under it) lapses. What it had already reserved stays charged.
- **No resume.** Quote evidence expires after 60 seconds, so an old run cannot
  continue on its snapshot. A new Run is a new run with a new identity.
- **No retries.** Permanent failures (invalid schema, unsupported model,
  oversize packet, budget, validation) and transient ones alike end the run's
  further spending; the operator decides whether to run again. An identical
  request repeated within the reducer's cache lifetime is not bought twice.

`GET /screener/ai-screener/runs/{run_id}/coverage` (`state.read`) returns one
run's plan, per-request receipts and a page of per-row accounting
(`?class=` one class or `NOT_EVALUATED`, `?offset=`, `?limit=` up to 500) for
the owning account. The ledger's terminal record keeps finalist identities
only (at most 500); rationales stay in the per-request receipts.

## UI

The existing AI status strip and AI Screener panel show: rows read, assessed,
eligible and AI-evaluated; the batch in progress; what the plan needed against
the shared budget; final or partial in words; reason counts for every row not
evaluated; and, on request, per-request receipts and the rows not evaluated.
`Stop run` is offered while a run is active. Provisional finalists are listed
without an Action Decision. No new workspace exists.

## Evidence

- Receipt: `artifacts/ai-screener-full-universe-acceptance.json`, written by
  `python tools/ai_screener_full_universe_acceptance.py`
  (`--probe` adds one free token-count request per Claude model; no option
  generates).
- Tests: `tests/intelligence/test_coverage_plan.py`,
  `tests/platform/test_screener_ai_universe.py`,
  `tests/platform/test_screener_ai_coverage.py`,
  `tests/platform/test_screener_ai_runs.py`,
  `tests/trading_correctness/test_full_universe_end_to_end.py`.

## Known limitations

- Under the default allowance only small queries complete; see Budget.
- A batch holds at most 50 rows until a larger strict-schema grammar is
  preflighted.
- The packet shape is PR 484's. About a third of a quote-and-technicals
  candidate is its fixed missing-capability list; a more compact wire would be
  a new wire version and is not part of this method.
- Per-instrument news is cache-only during a run.
- Automatic reevaluation passes keep the single-request method.
- No run is resumed after a restart.
- The candidate run is written before the ledger's terminal record. If the
  terminal write then failed, a stored selection would exist beside a run
  later closed as interrupted. The terminal record is bounded to make that
  failure unlikely; it is not transactional.
- A tail batch or a split batch has fewer rows competing for the same five
  finalist slots. Order is unbiased; competition per batch is not perfectly
  equal.
- Rows are re-read per request from what the Screener already serves. For a
  universe with no bulk snapshot source (futures, bonds, crypto) a request is
  only as fresh as the Screener's own quotes for those rows.
- The preview still describes only the first batch-sized slice of the sorted
  result; it is labelled as such. The run's own plan is the authoritative cost.

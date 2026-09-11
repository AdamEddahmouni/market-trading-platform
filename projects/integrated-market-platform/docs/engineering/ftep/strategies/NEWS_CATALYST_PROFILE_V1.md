# FTEP News / Catalyst Strategy Profile V1

**Classification:** `PREIMPLEMENTATION_PROFILE`  
**Inherits:** `FTEP_CORE_V1` plus the campaign's asset-class profile  
**Scope:** deterministic and governed-AI news/catalyst forward-test campaigns

## Strategy boundary

The news/catalyst lane is an event-driven strategy family. News is a candidate/catalyst input, not automatic trading authority. Deterministic preprocessing owns collection, timestamps, source policy, dedupe, entity linkage and catalyst classification before any AI challenger is evaluated.

## Required event provenance

Each qualifying candidate must preserve:

- story/event identity;
- publisher/source identity and source-quality class;
- publication/event time;
- retrieval/receive time;
- revision/update relationship where known;
- linked canonical instruments/entities;
- catalyst taxonomy/version;
- recency/novelty/dedupe state;
- information available at the decision cutoff;
- market-data snapshot references at/around the decision.

Later revisions, post-event explanations and future price reactions are excluded from candidate generation.

## Baseline-first rule

The preferred baseline is a frozen deterministic policy using the same eligible event cohort and information cutoff as the challenger. An AI/model arm is evaluated as incremental information or ranking value, not as a different data-acquisition process.

If a live AI arm is used, bind prompt version, model/provider/version, inference configuration, structured-output schema and input artifact references. If reproducible live-model behavior cannot be guaranteed, preserve the exact inference output and provenance used for each locked decision.

## Candidate generation

The activation manifest must freeze:

- eligible sources and source tiers;
- recency window;
- catalyst classes/keywords;
- entity/instrument linkage rules;
- dedupe/novelty rules;
- materiality/eligibility thresholds;
- candidate cadence and overlap policy;
- abstention/rejection conditions;
- treatment arms and baseline versions.

## Outcome horizons

Event horizons must be chosen before qualifying evidence. Multiple horizons may be used only when preregistered as primary/secondary or separate segments. Selecting the best horizon after seeing results is prohibited.

## Required analysis

Where applicable, report:

- eligible event count and abstention rate;
- baseline and treatment hit/return/calibration metrics;
- AI incremental value on matched cohorts;
- catalyst/source/time-of-day segmentation that was preregistered;
- latency/decay sensitivity;
- transaction-cost/execution sensitivity if execution claims are made;
- contradictory/null outcomes;
- multiple-testing/search-family accounting.

## First ES/news campaign open bindings

The current candidate first campaign still requires activation binding for:

- exact ES contract month and futures profile;
- prospective ES market-data capability contract;
- eligible news sources and their capability/rights records;
- deterministic baseline version;
- whether the AI arm is active and its provider/model/prompt binding;
- candidate cadence/overlap;
- session window;
- evaluation horizon(s);
- signal-only vs execution mode;
- sizing/order/cost rules if execution mode;
- calibration/comparator rules and thresholds;
- minimum campaign duration/cohort sufficiency.

This profile does not make ES/news the definition of FTEP or IMP.

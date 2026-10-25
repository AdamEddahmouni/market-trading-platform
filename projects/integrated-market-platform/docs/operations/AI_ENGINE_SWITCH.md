# Which AI decides: free local or capped paid

Owner decision 4 (2026-10-23, [OWNER_DECISIONS_20261023.md](../platform/OWNER_DECISIONS_20261023.md)): two AI
options and one switch in Setup. The free option is the best local model for this PC (RTX 2070 Super, 8 GB;
32 GB RAM). The paid option is the most cost-effective paid model, under a hard spending cap, and off by default.

Status: built in rebuild step 5 (2026-10-24) on its branch. **Not deployed.** The benchmark result is in
[AI_ENGINE_BENCHMARK_20261024.md](../reports/AI_ENGINE_BENCHMARK_20261024.md).

## The rule in one line

Automatic always means the free local model. Paid AI runs only when the owner chooses a paid model in Setup **and**
has set both dollar caps above $0. A saved API key alone turns nothing on.

## The Setup card

Setup → **Which AI decides** shows, for the whole machine:

- **Now:** which AI runs (free local, or paid and its model).
- **Free — runs on this PC:** the installed local model, and how it did on past decisions.
- **Paid — billed per decision:** a model list (the benchmark's pick is preselected), its list price, the measured
  cost per decision, and what paid AI has cost today and this month against the caps.
- **Spending caps:** a daily and a monthly cap in US dollars. Both start at $0, and $0 keeps paid AI off.

Switching asks for confirmation and applies to every AI feature at once (News synthesis, AI Screener, Action
Decisions, automatic passes and the Assistant), starting with the next request. It is refused while Paper's
automatic passes hold the engine (`SYNTHESIS_ENGINE_LOCKED`): pause them first.

| What | Where it is saved | Route |
|---|---|---|
| Engine and model | `<IMP cache>/settings/synthesis-engine.json` | `POST /screener/news/synthesis/engine` (`state.write`) |
| Daily and monthly caps | `IMP_PAID_AI_DAILY_USD`, `IMP_PAID_AI_MONTHLY_USD` in the private provider file | `POST /operator/config/provider`, provider `paid_ai` (`security.config.write`, this computer only) |
| The card's status | read only | `GET /screener/setup/ai` (no model call, no key) |

A paid engine cannot be saved while either cap is $0 (`PAID_AI_CAP_NOT_SET`), and a paid engine saved earlier calls
nothing once a cap is set back to $0.

## The dollar caps

Code: `intelligence/inference/paid_prices.py` and `paid_spend.py`.

- **Pinned prices.** Each paid catalog model has its list price per million tokens in the code, with the vendor's
  pricing page and the date it was checked (Claude 2026-10-06; OpenAI and Gemini 2026-10-24). A long-prompt tier and
  a dated price change are applied by prompt size and by day. A model without a pinned price cannot be chosen
  (`PAID_MODEL_PRICE_UNKNOWN`).
- **Before each call** its worst case is set aside: the input estimate (or the provider's exact count) plus the
  whole output allowance, thinking included, at that price. A call that could cross today's or this month's cap is
  refused before it is sent (`PAID_AI_DAILY_DOLLAR_CAP`, `PAID_AI_MONTHLY_DOLLAR_CAP`).
- **After the call** the set-aside amount is replaced by the cost of the usage the vendor reported. A timeout or an
  unknown outcome keeps the worst case charged. Usage above the reservation (`PAID_AI_USAGE_EXCEEDED_RESERVATION`)
  stops paid calls for the rest of the UTC day.
- **One ledger** for every paid engine and the Assistant: `<IMP cache>/quota/paid-ai-dollars.json`, under a lock,
  failing closed when unreadable (`PAID_AI_LEDGER_UNREADABLE`). The day is the UTC day; the month is the UTC
  calendar month. The older request and token limits (`IMP_SYNTHESIS_DAILY_REQUESTS`, `IMP_SYNTHESIS_DAILY_TOKENS`)
  still apply as well.
- The cap is on **list price**. The vendor's invoice can differ slightly (rounding, taxes, any account discount).

## Paper and paid AI

The Paper controller is armed with a risk policy, and that policy decides whether it may use paid AI at all
(`ai.allow_paid_inference` and its own caps, see the
[Paper runbook](AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md)). The Setup switch does not change it. To let Paper use paid
AI: pause Paper, choose the paid model in Setup, then re-arm Paper with paid AI allowed. A policy armed without it
never sends a paid request, whatever the engine.

## The Assistant

The Assistant follows the same choice: paid Claude only when Claude is the chosen engine with both caps set, and
its calls are charged to the same ledger. Otherwise it answers from the evidence without calling a model.
`IMP_ASSISTANT_PROVIDER=grounded` or `IMP_ASSISTANT_STUB` only turn it further off.

## Local models

Pinned in `intelligence/inference/local_models.py` (size, SHA-256 and architecture from each file):

| Model | File | Profile |
|---|---|---|
| Qwen3-4B (today's model) | `Qwen3-4B-Q4_K_M.gguf`, 2.5 GB | `vulkan-8192/1` |
| Qwen3-4B-Instruct-2507 | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2.5 GB | `vulkan-8192/1` |
| Qwen3-8B | `Qwen3-8B-Q4_K_M.gguf`, 5.0 GB | `vulkan-8192/1` |
| Qwen3-30B-A3B-Instruct-2507 (mixture of experts) | `Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf`, 18.6 GB | `vulkan-8192/1-moe` |

The step-5 downloads are in `D:\IMP\IMP-tools\models\`. The 2507 files are LM Studio community conversions of the
Apache-2.0 Qwen releases, because Qwen publishes no official 2507 GGUF.

- **Memory check that counts the graphics card.** On a GPU profile the card must hold the offloaded weights, the
  KV cache and 1 GiB of buffers within 7 GiB (about 1 GiB stays with the desktop). Only the weights kept on the CPU,
  plus 2 GiB, count against RAM, and at least 4 GiB must stay free. CPU profiles keep the old rule: everything in
  RAM, at most 6 GiB per process. So the 8B runs on the card and is refused on the CPU.
- **The 30B model** keeps the expert weights of 38 of its 48 layers in RAM (`--n-cpu-moe 38`, 13.9 GB) and the rest
  on the card. It needs about 18.9 GiB of free RAM to start. On 2026-10-24 this PC had 17.5 GiB free with IMP off, so
  it was refused and is not usable here. It has no CPU fallback.
- A GPU process's working set also holds the memory-mapped model file (measured 3.1 GB for the 4B, 5.5 GB for the
  8B). Those pages are file-backed and reclaimable, so they are allowed for in the process limit and not counted
  against free RAM.
- **Faster start.** The model file is read once, front to back, before `llama-server` starts. On the hard disk that
  is much faster than the scattered reads of a cold memory map, and it reads nothing a load would not read anyway.
  The start limit is 180 s plus 30 s per GB of model file, at most 900 s (the 10-23 failure was a slow load hitting
  the old fixed 180 s). The integrity check before the first start also reads the whole file once per process.

## The benchmark

`tools/ai_decision_benchmark.py` replays real past Action Decisions:

```bash
python tools/ai_decision_benchmark.py export --db <state-normal>/imp-state.sqlite3 --out cases.json --count 60
python tools/ai_decision_benchmark.py run --cases cases.json --engine local --model <pin> --out results --base-manifest <cache>/models/local-llm.json --models-dir D:/IMP/IMP-tools/models
python tools/ai_decision_benchmark.py run --cases cases.json --engine anthropic --model claude-haiku-5-5 --out results --provider-env <provider file> --ledger-dir <folder> --total-usd 3
python tools/ai_decision_benchmark.py report --results results --publish <IMP cache>
```

`export` opens the state database read-only and checks each case's input hash against the stored decision. `run`
uses the production prompt, schema, output bound, timeout and validator. A paid run has its own dollar ledger with
a hard total. `report --publish` writes `<IMP cache>/benchmarks/ai-decision/summary.json`, which the Setup card
shows; it changes no setting.

The winner rule was fixed before the runs: a local model replaces Qwen3-4B only if it starts within the memory check,
its p95 latency is at most twice Qwen3-4B's, and its acceptance beats Qwen3-4B's by at least 5 points. The paid pick
is the cheapest model per accepted decision whose acceptance is at least the local winner's.

## Not proven until the release

- Live decisions on the chosen model while Paper runs (everything is off until step 10).
- The Setup card against the live API on the release build (covered here by unit and component tests).

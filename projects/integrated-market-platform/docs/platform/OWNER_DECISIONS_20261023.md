# Owner decisions — 2026-10-23

| Field | Value |
|---|---|
| Document ID | `IMP-OWNER-DECISIONS-20261023` |
| Classification | `ACTIVE_SUPPORTING` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Owner choices that set the next build after the 2026-10-23 shutdown |
| Establishing Milestone | 2026-10-23 status reconciliation |
| Version | `1.0` |
| Last Verified | `2026-10-23` |
| Supersedes | None |
| Superseded By | None |

On Friday 2026-10-23 the owner shut the whole workstation down after the
market day and then answered the open questions one at a time. These are the
answers, in plain words, and what each one changes. The verified state they
were made against is in [Program Status](PROGRAM_STATUS.md#current-operating-state-2026-10-23).
Nothing here grants Live authority: Live trading stays off.

| # | Question | Owner's answer | What it changes |
|---|---|---|---|
| 1 | What counts as "the AI works"? | Both tests, measured from the same continuous Paper run. | **2-week test:** after 10 trading days the account is worth more than it started with. **1-month test:** after 20 trading days, with at least 30 trades, the account is worth more than it started with after costs **and** beat simply buying and holding SPY over the same days. Needs an evaluation report (equity curve, SPY comparison, costs, trade count). |
| 2 | Allow short selling (betting a price falls)? | Build it now. | The Paper simulator gains borrow, margin and cover accounting, short-side risk limits and a ledger `allow_short` setting; the AI gains short entry and cover actions. Paper only. 30 of the 96 automation intents recorded so far were shorts the account could not take. |
| 3 | Restart automatically after a reboot or a frozen price feed? | Yes. | Platform, collector and Moomoo OpenD restart unattended and the Paper controller resumes; every restart is logged for review. Fake money only. |
| 4 | Which AI makes the decisions? | Both options, switchable by the owner. | (a) The best free local model that fits the RTX 2070 Super (8 GB) and 32 GB RAM at a speed that is not a drawback, benchmarked against Qwen3-4B. (b) The most cost-effective paid model under a hard spending cap, off by default. A Setup switch picks which one runs. |
| 5 | How many stocks does the AI look at? | A fast opportunity engine first, the AI last. | A deterministic numeric screen (movement, volume, liquidity, catalysts, freshness) ranks the whole market and passes only a shortlist sized to the model to the AI, which makes the final pick — "like Finviz handing its best picks to a broker". Full-universe AI sweeps stop being the default. |
| 6 | Keep the risk limits? | Keep them, but allow selective overnight holds. | Still $5,000 per position, 15 positions, $75,000 total, $2,000 daily loss stop. Positions are still sold 10 minutes before the close **unless** the AI gives an evidence-backed reason to hold overnight or for several days, and only a few may be held (proposed default: at most 5 positions / $25,000 carried overnight). The close-out must also run when the feed is unhealthy and touch only automation positions. |
| 7 | What runs on Monday 2026-10-26? | Keep everything off. | No R13 deploy and no restart until the rebuild is ready. R13's fixes are folded into that rebuild. All six IMP scheduled tasks stay disabled. |
| 8 | Merge the nine open pull requests? | Hold all of them. | #456, #479, #501, #504, #505, #506, #507, #502 and #503 stay open; #500 stays a draft. They are folded into the rebuild later. #504 and #506 currently fail two UI tests each. |
| 9 | Upload the unpushed R9–R13 code? | Yes, as a backup. | The Paper branch is pushed to GitHub with one **draft** pull request. Nothing is merged. |
| 10 | Disk space on D:? | Compress the large log, trim logs automatically, clear old work copies. | The 6.08 GB error log became a 50 MB zip. Automatic log size limits are part of the rebuild. Old worktrees are removed only from a list the owner approves. |
| 11 | The `.git` folder in `C:\Users\Adam`? | Move it. | It was the owner's own July 26 `cursor` repository, not something new. Moved to `C:\Users\Adam\cursor\`; the two `test_git_ref.py` discovery tests it broke now pass. |

## Build order agreed for the rebuild

Each item gets its own go-ahead and its own validation; none of it is built
by recording it here.

1. A Moomoo data-flow watchdog outside the feed thread that notices
   "connected but no new rows" and reconnects, plus the reason 2026-10-21 and
   2026-10-23 had no Moomoo rows at all.
2. Root cause of the recurring `database is locked` errors.
3. The opportunity engine and AI shortlist (answer 5), carrying R13's fixes.
4. Automatic restart (answer 3).
5. Switchable AI (answer 4).
6. Short selling (answer 2).
7. Selective overnight holds and close-out fixes (answer 6).
8. The 2-week / 1-month evaluation report (answer 1).
9. The AI Journal budget-guard bug (it checks the paid budget even when the
   free local model is the engine, so it never runs).
10. Fold in the held pull requests, then one release with the owner's deploy
    approval and a restart.

## Follow-up answers

| Date | Question | Owner's answer | What it changes |
|---|---|---|---|
| 2026-10-25 | How much cash does a Paper short set aside while it is open? | 50%, like a real broker. | A short holds back its sale proceeds plus 50% of its value from buying power (a $5,000 short lowers buying power by $2,500). Buys stay cash-only. See [Paper short selling](../architecture/PAPER_DECISION_LIFECYCLE.md#paper-short-selling). |
| 2026-10-25 | How much may carry overnight? | At most 5 positions and $25,000 total. | Both caps apply together across automation scopes; disabled until configured at release. |
| 2026-10-25 | Maximum multi-day holding period? | 5 trading days. | Entry is day 1; mandatory close-out on day 5; a fresh evidence-backed reason is required each day. |
| 2026-10-25 | Feed down at the close? | Keep trying, then sell at the next open. | Use valid prices and canonical Paper gates; record unresolved carry and block new entries until closed. |
| 2026-10-25 | May shorts carry overnight? | Yes, under the same limits. | Long and short positions share the 5-position/$25,000 caps; simulated borrow fees continue. |

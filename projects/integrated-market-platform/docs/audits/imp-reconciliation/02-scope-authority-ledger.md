# 02 — Scope Authority Ledger

Status: **COMPLETE for WS02 (2026-09-06)**. Canonical scope-authority output.
Image evidence index: [02a-original-scope-image-index.md](02a-original-scope-image-index.md).
This ledger defines what IMP is authorized to become; it does not judge the
current implementation (WS04/WS05) and executes no remediation.

## Authority tiers (used throughout)

| Tier | Class | Evidence |
|---|---|---|
| A | ORIGINAL_AUTHORIZED_SCOPE | Project-scope image set (`project-scope-images/`, 7 PNG, OCR-extracted) — earliest streams + original screener |
| B | AUTHORIZED_LATER_SCOPE (professor) | Professor Kaamran Raahemifar emails (verbatim, images IMG-001..006) — EXPAND/REFINE/CORRECT/CLARIFY/SUPERSEDE allowed |
| C | AUTHORIZED_LATER_SCOPE (Adam) | Explicit current user mandate (this program, §1); any other user-authorized additions |
| D | AUTHORIZED_DONOR_SUPPORT | Donors intentionally supplied for an authorized capability (SRC-003/004/005/006) — legitimate reference, NOT automatic requirements |
| E | AUTHORIZED_SUPPORTING_ARCHITECTURE | Identity, accounts, portfolio state, provider adapters, market-data normalization, caching, persistence, risk, mode isolation, test infra, observability, auditability |
| F | IMPLEMENTATION_EVIDENCE | Code/tests/docs/commits/roadmaps — proves what was built, not what was authorized |

Separate for every capability: `SCOPE_AUTHORIZATION` · `IMPLEMENTATION_STATUS`
(WS04) · `PROVENANCE_STATUS` (WS01/WS03).

## Tier A — Original authorized scope (from images)

| ID | Capability | Image evidence | Wording/meaning | Type | Importance | Confidence | Ambiguity |
|---|---|---|---|---|---|---|---|
| ORG-001 | Short Squeeze screener with short-interest formula | IMG-001 ("Short Interest Formula" 7/24/2026; "Screener Project" 7/27/2026 threads) | The original project is a short-squeeze/short-interest screener; professor thanked for it and the CVD/Level2/Future/Options work came later | PRODUCT_GOAL + USER_CAPABILITY | CORE_REQUIRED | MODERATE (subjects/previews only) | Full original proposal body not in image set |
| ORG-002 | Screener project scope detail | IMG-001 (preview: "Thank you very much. Wel...") | Continuation of screener project welcome/scope email | PRODUCT_GOAL | IMPORTANT_SUPPORTING | LOW (truncated preview) | Body unreadable in image |
| ORG-003 | Research/deliverable posture | IMG-001/IMG-005 ("This project certainly suits your talents and skillsets"; media presentations supplied) | Academic capstone program (IST/DS 495 context) with presentation/media deliverables | DELIVERABLE_REQUIREMENT | IMPORTANT_SUPPORTING | MODERATE | Course specifics not in images |

Explicit statement: the 7-image set documents the email evolution and the
professor integration mandate, but does NOT contain the full original proposal
screenshots. ORG-001/002 are reconstructed from the earliest threads at
MODERATE confidence; any later-supplied original proposal screenshots supersede
this reconstruction (recorded in 14-open-decisions under M1-closed).

## Tier B — Authorized later professor additions (verbatim evidence)

| ID | Requirement | Verbatim evidence (OCR-normalized) | Image | Classification | Importance |
|---|---|---|---|---|---|
| LATER-001 | CVD / Level 2 project stream (Hyuntae Jeong donor) | "CVD & Level 2 Project Full Code from Hyuntae Jeong (John)" — full code + README/USAGE; repo link | IMG-002 | AUTHORIZED_DONOR_SUPPORT + stream | CORE_REQUIRED |
| LATER-002 | CVD/Level2 requires IB Level 1 AND Level 2 data; professor offered to pay one month | "CVD/Leve12 requires Interactive Brokers Level 1 and Level 2 data. Please purchase them and let me know how much you pay. I am happy to pay for one month." | IMG-005 | AUTHORIZED_LATER_SCOPE (data requirement) | CORE_REQUIRED |
| LATER-003 | Future + CVD stream; both use IB API | "Both use Interactive Brokers API." (Future + CVD thread, 7/27) | IMG-001 | AUTHORIZED_LATER_SCOPE (IB data) | CORE_REQUIRED |
| LATER-004 | Options project stream (Eric Strzalkowski donor) | "Option Project" — repo supplied; donor admitted trial-based providers and unreliability | IMG-003 | AUTHORIZED_DONOR_SUPPORT + stream | CORE_REQUIRED |
| LATER-005 | Earlier Future material (Eric_futuresX) circulated within CVD/Future stream | "CVD Project (Eric's Materials)" — Eric_futuresX-main.zip to Zheng/Jeong 6/6/2026, forwarded to Adam 8/1 | IMG-004 | AUTHORIZED_DONOR_SUPPORT (candidate) | IMPORTANT_SUPPORTING |
| LATER-006 | Integrated platform: short squeeze + CVD/Level2 + Options/Future together | "you can create an integrated platform where your short squeeze, your CVD/Leve12 and Options/Future come together nicely." | IMG-005 | AUTHORIZED_LATER_SCOPE (product direction) | CORE_REQUIRED |
| LATER-007 | Options may use IB | "For option, you maybe able to use IB as well." | IMG-005 | AUTHORIZED_OPTION (provider) | IMPORTANT_SUPPORTING |
| LATER-008 | Future uses IB data (Eric's implementation) | "For Future, Eric's using IB data." | IMG-005 | AUTHORIZED_PREFERRED_PROVIDER (donor-level) | IMPORTANT_SUPPORTING |
| LATER-009 | Enhanced codeset incoming for Future+CVD | "An enhanced codeset will be coming your way shortly." | IMG-001 | AUTHORIZED_LATER_SCOPE (intent) | IMPORTANT_SUPPORTING |
| LATER-010 | Professor-supplied presentations (Kaltura) for Future+CVD and CVD (Eric's materials) | Media links in IMG-001/IMG-004 | IMG-001/004 | DELIVERABLE_REFERENCE | OPTIONAL |
| LATER-011 | Newly confirmed Future source: Claude Code News | "Please let me know if you can download this. This is Future Project." — supplied by Bichara, Lucas via OneDrive | IMG-006 | AUTHORIZED_FUTURE_DONOR (SRC-006) | CORE_REQUIRED (reference) |
| LATER-012 | Mistaken-donor correction (Heller) | "Future Project — Hello Adam: This was not..." (email subject visible; full text per controller §3) | IMG-006 | CORRECTION (supersedes prior classification) | — |
| LATER-013 | Short Squeeze remains part of the integrated platform | Professor integration list includes "your short squeeze" | IMG-005 | AUTHORIZED_LATER_SCOPE (confirmation) | CORE_REQUIRED |

## Tier C — Authorized later Adam additions (explicit current mandate)

| ID | Domain | Classification | Notes |
|---|---|---|---|
| MND-001 | Bonds / Fixed Income | EXPLICIT_CURRENT_USER_MANDATE | First-class domain; Treasuries/yields/curve/rates/duration/credit/corporates/portfolio/analytics → many DETAILS_TO_BE_DEFINED |
| MND-002 | Crypto | EXPLICIT_CURRENT_USER_MANDATE | First-class domain; market data/assets/analytics/portfolio/intelligence; planning docs exist (Tier F): `docs/research/CRYPTO_FEASIBILITY_STUDY_PLAN.md`, `CRYPTO_INFLUENCE_EXPERIMENT_ROADMAP.md`, `docs/architecture/CRYPTO_*` (previously "planning only — not authorized"; now authorized domain) |
| MND-003 | Whale / Large-Participant Intelligence | EXPLICIT_CURRENT_USER_MANDATE | Cross-market intelligence layer; Tier F groundwork: `docs/architecture/SWIM_WITH_THE_WHALES.md` (8 evidence families), Phase 9–16 whale families (fixture-first) |
| MND-004 | Industry Intelligence | EXPLICIT_CURRENT_USER_MANDATE | Sectors/industries/peers/trends/supply chains; details to be defined |
| MND-005 | Government / Public-Sector Intelligence | EXPLICIT_CURRENT_USER_MANDATE | Macro/policy/central banks/Treasury/regulatory; Tier F groundwork: FRED/ALFRED, CFTC COT, EIA, NOAA/NWS/CPC, SEC EDGAR/FTD providers; Market Context MC11 macro |
| MND-006 | Gold | EXPLICIT_CURRENT_USER_MANDATE | Must remain visible (not hidden under generic commodities) |
| MND-007 | Silver | EXPLICIT_CURRENT_USER_MANDATE | Same |
| MND-008 | Broader Commodities | EXPLICIT_CURRENT_USER_MANDATE | Energy/agriculture/industrial metals/precious metals; Tier F groundwork: ENERGY/CL futures fixtures (F11) |

Rule: these domains may not be marked OUT_OF_SCOPE or removed for lack of
implementation. Unspecified details use `AUTHORIZED_DOMAIN, DETAILS_TO_BE_DEFINED`.

## Chronological requirements ledger (key rows; full graph in 05-capability-matrix)

| Capability | First evidence | Authority | Current authorized requirement | Superseded by | Importance | Confidence |
|---|---|---|---|---|---|---|
| Short Squeeze screener | ORG-001 (7/24–7/27 emails) | A + B (LATER-013) | Read-only evidence-driven short-squeeze research; part of integrated platform | — | CORE_REQUIRED | CONFIRMED |
| CVD / Level 2 | LATER-001 (7/27–7/28) | B + D | CVD + L1 + L2 measurement; IB L1+L2 data required | — | CORE_REQUIRED | CONFIRMED |
| Options | LATER-004 (7/31–8/1) | B + D | Options analysis/confirmation; IB allowed; paid donor providers NOT mandatory | — | CORE_REQUIRED | CONFIRMED |
| Futures / Future | LATER-003/005/011 | B + D | Future capability; IB data used by Eric; Claude Code News = primary authorized reference; architecture NOT decided (WS05/07) | — | CORE_REQUIRED | CONFIRMED |
| Integrated platform | LATER-006 (8/1) | B | One platform: squeeze + CVD/Level2 + Options/Future together | — | CORE_REQUIRED | CONFIRMED |
| Interactive Brokers | LATER-002/003/007/008 | B | CVD L1+L2 REQUIRED; Options allowed; Future preferred (Eric path); others UNKNOWN | — | CORE_REQUIRED (CVD) | CONFIRMED |
| Demo/Paper/Live | Tier F (MODE_AUTHORITY) | E (+ safety invariants) | Demo replay, Paper internal simulation (gated), Live observational only; LIVE-001 blocked | — | CORE_REQUIRED (safety) | CONFIRMED |
| Bonds/Fixed Income | MND-001 | C | Domain authorized; details to be defined | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Crypto | MND-002 | C | Domain authorized; planning docs exist; details to be defined | README's "planning only" note superseded by mandate | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Whale intelligence | MND-003 | C | Cross-market layer; doctrine exists; details to be defined | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Industry intelligence | MND-004 | C | Domain authorized; details to be defined | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Government/public-sector intelligence | MND-005 | C | Domain authorized; providers exist (FRED/COT/EIA/EDGAR…); details to be defined | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Gold | MND-006 | C | Explicitly visible domain | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Silver | MND-007 | C | Explicitly visible domain | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |
| Commodities | MND-008 | C | Broader commodity domain | — | CORE_REQUIRED (domain) | HIGH_CONFIDENCE |

## Canonical capability graph (WS02 scope level)

```text
PLATFORM FOUNDATION (identity, accounts, providers, instruments, portfolio,
orders, risk, market-data layer, persistence, mode isolation) — Tier E

MARKET/ASSET DOMAINS
  Equities (incl. Short Squeeze)
  Options
  Futures
  Bonds / Fixed Income
  Crypto
  Gold
  Silver
  Broader Commodities
  (CVD / Level 1 / Level 2 = order-flow measurement layer over Equities)

CROSS-MARKET INTELLIGENCE LAYERS
  Whale / Large-Participant Intelligence
  Industry Intelligence
  Government / Public-Sector Intelligence
  Market Context / Macro
  News / Research
  Analytics (performance, attribution, risk, cross-asset)

TRADING / PORTFOLIO PLATFORM SERVICES
  Market data · Orders · Trading · Portfolio · Accounts · Risk ·
  Alerts · Automation · Dashboard/UX

MODES  Demo · Paper · Live

ENGINEERING INFRASTRUCTURE (separate from product scope)
  AGENTS, SOPs, CI, validation, developer commands, docs governance
```

Rule (WS02 §11/§39): asset domains ≠ intelligence layers ≠ platform services
≠ engineering infrastructure. A cross-market intelligence capability may
apply to several asset classes; model explicitly at WS05/WS07.

## Interactive Brokers requirement matrix (capability × classification)

| Capability | Classification | Evidence |
|---|---|---|
| CVD Level 1 | EXPLICITLY_REQUIRED | LATER-002 (IMG-005 verbatim) |
| CVD Level 2 | EXPLICITLY_REQUIRED | LATER-002 (IMG-005 verbatim) |
| Options | AUTHORIZED_OPTION | LATER-007 ("you maybe able to use IB as well") — not mandated; donor trial providers not requirements |
| Futures | AUTHORIZED_PREFERRED_PROVIDER (donor path) | LATER-008 ("Eric's using IB data"); Claude Code News uses Tradovate — decision deferred (WS05/07) |
| Equities / Short Squeeze | NOT_REQUIRED | no evidence |
| Bonds | UNKNOWN | no evidence yet |
| Crypto | NOT_REQUIRED / UNKNOWN | no evidence; exchanges unspecified |
| Gold / Silver / Commodities | UNKNOWN | no evidence yet |
| Accounts / Portfolio / Orders / Execution | DONOR_SPECIFIC → UNKNOWN for scope | futuresX uses IBKR; no professor scope statement; resolve at WS05 |

## Demo / Paper / Live authority

- Authority source: IMP governance (Tier E + safety invariants), not the image
  set. `MODE_AUTHORITY.md`: Demo = read-only replay; Paper = gated internal
  simulation (`INTERNAL_SIMULATION` + `PAPER_ONLY` + env gates); Live =
  observational only; `LIVE-001` remains blocked pending separate authorization.
- Expected behavior (authorized): mode isolation end-to-end; fail-closed on
  authority loss/stale preview/schema mismatch/unknown identifiers/unconfigured
  providers; never fabricate data.
- No correctness audit here (WS05).

## Accounts / Portfolio scope

Authorized requirement candidates: accounts, multi-account, switching, cash,
buying power, positions, P&L, orders, fills, transactions, portfolio
snapshots, allocation, exposure, cross-asset portfolio. Multi-asset mandate
may require cross-domain portfolio semantics later — NOT designed during WS02.

## Research / Intelligence scope

Authorized: news, research, screeners, watchlists, fundamentals, technicals,
whale/industry/government/macro intelligence, AI-assisted research
(MRA-001/002 exist), source/evidence tracking. Explicit mandates remain in scope.

## Analytics scope

Authorized: performance, returns, attribution, risk analytics, trade/portfolio
analytics, asset-class analytics, cross-asset comparison, market/regime
analytics. Dashboard metrics ≠ complete analytics scope.

## Developer infrastructure (separate, never inflates product completion)

AGENTS, Cursor rules, SOPs, CI, validation manifest, developer commands, docs
governance, hooks → `AUTHORIZED_SUPPORTING_ARCHITECTURE` /
`DEVELOPER_INFRASTRUCTURE`.

## Known mistaken donor scope (SRC-001/002)

- GridIQ port commit `6adeeec` = IMPLEMENTATION_EVIDENCE_ONLY; never scope
  authority (WS03 traces it).
- Test for any capability: (1) independent Tier A/B/C authority? (2) later
  independent adoption? (3) exists only due to mistaken donor influence?
  → classify `KNOWN_MISTAKEN_DONOR_SCOPE` / `LEGITIMATE_REQUIREMENT_INDEPENDENT_OF_DONOR` / `AMBIGUOUS`.
- Admitted donor fixtures (`ADMITTED-CVD-NVDA-ORDERFLOW-001`,
  `ADMITTED-OPTIONS-BIYA-001`) = intentional bounded evaluation evidence, NOT
  whole-donor authorization.

## Supersession model

`UNCHANGED · EXPANDED · REFINED · CORRECTED · SUPERSEDED · REVOKED · AMBIGUOUS`.
Preserve chains: original → later modification → current requirement.
Concrete: LATER-011 (Claude Code News) expands LATER-005 (Eric_futuresX) —
does not revoke it; LATER-012 corrects SRC-001/002 classification; MND-002
(Crypto) supersedes README's "planning only — not authorized" note for the
crypto domain.

## Details-to-be-defined (domain authorized, specifics open)

Bonds (which instruments/data/analytics), Crypto (exchanges/providers),
Whale (which evidence families to elevate), Industry (classification source),
Government (which feeds/APIs), Gold/Silver (spot vs futures vs ETFs),
Commodities (product coverage), cross-asset portfolio semantics, Future
execution provider (IB vs Tradovate vs adapters). Each recorded in
14-open-decisions.

## WS02 closure statement

WS02 criteria met: all 7 images inventoried and analyzed (02a); ORG-* and
LATER-*/MND-* IDs assigned; professor + Adam additions incorporated; all
mandated domains explicitly represented; SS/CVD/Options/Futures authority
established; integrated-platform requirement established; IB matrix
capability-by-capability; Demo/Paper/Live, accounts/portfolio,
research/intelligence, analytics, developer-infrastructure classified;
mistaken-donor scope excluded from authority; supersession traceable; current
authorized scope explicit below.

## Current authorized scope (canonical statement)

> IMP is authorized to become one integrated market workstation covering the
> asset domains **Equities (incl. Short Squeeze), Options, Futures,
> Bonds/Fixed Income, Crypto, Gold, Silver, and broader Commodities**, with
> **CVD/Level 1/Level 2 order-flow measurement** (IB Level 1+2 data required),
> cross-market intelligence layers (**Whale/Large-Participant, Industry,
> Government/Public-Sector, Market Context, News/Research, Analytics**),
> shared trading/portfolio platform services (accounts, market data, orders,
> trading, portfolio, risk, alerts, automation, dashboard), operating under
> **Demo/Paper/Live mode isolation with Live execution blocked (LIVE-001)**
> and fail-closed safety invariants. Authorized donors (tradingCVDBubble,
> internship-project, Eric_futuresX, Claude Code News) are legitimate
> references only; mistaken Heller material (GridIQ, DS-340W) is excluded as
> scope authority. Requirements that were later added by the professor or Adam
> remain legitimate; the target is NOT a rollback to the earliest feature set.
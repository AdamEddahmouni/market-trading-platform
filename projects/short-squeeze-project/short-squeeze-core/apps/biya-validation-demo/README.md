# BIYA Validation Demonstration

A static, single-page research demonstration of the Phase 2V candidate-validation case
study. Plain HTML, CSS, and JavaScript — no framework, no build step, no backend, no
login, no analytics, and no third-party request of any kind.

## What it shows

Why the original screener surfaced the ticker BIYA, what evidence genuinely existed at
that moment, how each original rule holds up methodologically, and — explicitly — what
the surviving record cannot establish.

The original forensic result remains `INSUFFICIENT_EVIDENCE`. The additive outcome
amendment is `OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED`: retained historical bars show
a substantial later move from both detection-window boundaries, without recovering any
missing original input or validating the original selection method.

## Where the data comes from

`data/biya-outcome-case.json` is **generated, never hand-edited**. It is produced by a
deterministic whitelist projection that builds a public case field by field from named
sources, rather than copying the internal case and deleting keys. A field added to the
internal model is therefore absent from this page by default.

Regenerate the acquisition-derived normalization, amendment, public projection, and
separate anchors from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\generate_phase_2v_outcome_anchors.py
```

The generator records the public payload as `biya_updated_public_export` in the additive
outcome anchor manifest. The original Phase 2V demo file and anchors remain untouched.

## What is excluded, by construction

Sensitive artifacts never reach this directory. The exporter drops them rather than
redacting in place, and `assert_export_is_clean()` re-scans the rendered bytes for
absolute paths, credentials, API keys, tokens, and email addresses before they are
written. Specifically absent: personal names and correspondence, the archived
application log (which contains a live provider credential), local filesystem paths, and
account identifiers.

## Run it locally

The page fetches its data file, so open it over HTTP rather than from disk:

```powershell
python -m http.server 8731 --directory apps\biya-validation-demo
```

Then visit <http://localhost:8731>.

## Deploying

`vercel.json` sets a strict Content-Security-Policy (`default-src 'none'`, self-only
scripts and styles, no framing) and standard hardening headers. There is nothing to
build.

```powershell
cd apps\biya-validation-demo
vercel --prod
```

Deployment requires an authenticated Vercel CLI session. If the CLI is not logged in,
this directory is already deployment-ready — run `vercel login` first. No URL is
recorded here unless a deployment actually happened.

## Design constraints

The page is deliberately not a trading dashboard. No score gauge, no ranking, no
buy/sell styling, no "AI prediction" language, and no red/green verdict colouring that
could be read as a signal. Every claim is traceable to the generated payload, and every
unknown renders as an explicit "unknown" rather than a zero or a blank.

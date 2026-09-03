"""Deterministic operator-facing prose for the submission kit.

Every guide is rendered to bytes with LF endings, in plain language, while
preserving exact Batch 03 field names and constraints. Guidance is aligned to
actual Batch 03 behavior; no non-existent feature is described. No credential
material appears anywhere.
"""

from __future__ import annotations

from ..local_bar_intake.semantics import (
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntendedUse,
    PriceAdjustmentSemantics,
    SUPPORTED_ENCODINGS,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)
from .checklist import CHECKLIST_ITEMS
from .preflight import PreflightStatus
from .troubleshooting import build_invalid_scenario_index, build_troubleshooting_index


def _md(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _values(enum) -> str:
    return ", ".join(member.value for member in enum)


def readme() -> bytes:
    return _md(
        "# Historical Market-Bar Submission Kit",
        "",
        "This kit helps you prepare a lawful, local historical market-bar export so it",
        "conforms to the offline intake contracts, and validate it with an **offline",
        "preflight** before any later work. It performs preparation and validation only.",
        "",
        "It does **not** download data, call provider APIs, log into accounts, handle",
        "credentials, associate your data with any research case, compute any outcome, or",
        "begin any later phase. You obtain the export yourself, lawfully; the kit records",
        "your entitlement assertion and checks the local files.",
        "",
        "## What preflight can and cannot tell you",
        "",
        "A `READY_FOR_FUTURE_ASSOCIATION` result means only that your local bundle passed",
        "the current intake and normalization checks. It does **not** mean the data is",
        "accurate, that your license is legally sufficient, that a particular historical",
        "case is covered, that an outcome window is complete, or that any later analysis or",
        "publication may run.",
        "",
        "## Read these in order",
        "",
        "1. `QUICKSTART.md` — the end-to-end path in a few steps.",
        "2. `PROVIDER-AND-ENTITLEMENT-GUIDE.md` — obtaining a file lawfully and declaring it.",
        "3. `FOLDER-PLACEMENT-GUIDE.md` — where the raw file and declarations go.",
        "4. `SHA256-AND-BYTE-LENGTH-GUIDE.md` — recording exact bytes.",
        "5. `TIMEZONE-INTERVAL-SESSION-GUIDE.md` — declaring time semantics.",
        "6. `ADJUSTMENT-SEMANTICS-GUIDE.md` — declaring price/volume adjustment.",
        "7. `PREFLIGHT-GUIDE.md` — running preflight and reading the report.",
        "8. `TROUBLESHOOTING.md` — what each reason code means and how to respond.",
        "9. `EXPORT-CHECKLIST.md` and `FINAL-OPERATOR-CHECKLIST.md` — confirm before you finish.",
        "",
        "## Contents",
        "",
        "- `templates/` — blank, fill-in templates for the manifest, mapping profile, and",
        "  (future-only) case association.",
        "- `examples/synthetic-valid/` — a complete, clearly fictional example that passes",
        "  preflight, small enough to read by hand.",
        "- `examples/synthetic-invalid/` — a deterministic index of failing scenarios with",
        "  the reason codes they produce and how to respond.",
        "",
        "Everything in this kit is synthetic. No real market data is included.",
    )


def quickstart() -> bytes:
    return _md(
        "# Quickstart",
        "",
        "1. **Obtain** a historical bar export you are entitled to use (see the",
        "   provider-and-entitlement guide). The kit never fetches it for you.",
        "2. **Place** the exact raw file under your bundle root at `raw/<your-export>.csv`",
        "   (see the folder-placement guide). Never edit the raw file afterward.",
        "3. **Hash** the raw file and record its SHA-256 and byte length:",
        "",
        "   ```",
        "   squeeze-core historical-bar-hash --file raw/<your-export>.csv",
        "   ```",
        "",
        "4. **Fill in** `templates/intake-manifest.template.json` and",
        "   `templates/column-mapping-profile.template.json`. Replace every `<REPLACE: ...>`",
        "   value and delete the `_field_guidance` blocks.",
        "5. **Run preflight** offline:",
        "",
        "   ```",
        "   squeeze-core historical-bar-preflight --root <bundle-root> \\",
        "       --manifest <bundle-root>/manifest.json \\",
        "       --profile <bundle-root>/profile.json",
        "   ```",
        "",
        "6. **Read the status**:",
        "",
        f"   - `{PreflightStatus.READY_FOR_FUTURE_ASSOCIATION.value}` — the bundle passed the",
        "     current checks (with the disclaimers in the preflight guide).",
        f"   - `{PreflightStatus.NOT_READY_QUARANTINED.value}` — some rows were quarantined;",
        "     review diagnostics before relying on it.",
        f"   - `{PreflightStatus.NOT_READY_REJECTED.value}` — a barrier blocked the bundle; see",
        "     the reason codes and the troubleshooting guide.",
        "",
        "7. **Confirm** the export and final operator checklists.",
        "",
        "Preflight stops before any case association. It never touches the network.",
    )


def provider_and_entitlement_guide() -> bytes:
    return _md(
        "# Provider and Entitlement Guide",
        "",
        "Obtaining the file and using the software are separate steps.",
        "",
        "## Obtaining a file lawfully",
        "",
        "You obtain the export yourself, through means you are permitted to use: your own",
        "licensed download, a permitted export from a tool you have rights to, or another",
        "lawful source. The kit does not download data, call APIs, scrape sites, log into",
        "accounts, or bypass paywalls, rate limits, robots rules, or anti-bot measures.",
        "Supply only exports you are entitled to use under their terms.",
        "",
        "## Declaring what you obtained",
        "",
        "In the manifest you declare provenance and your entitlement assertion:",
        "",
        "- `provider_name` — the data source or provider.",
        "- `provider_product_or_export_name` — the specific product or export.",
        "- `user_entitlement_assertion` — your statement that you are entitled to use it.",
        "- `license_or_terms_reference` — a reference to the terms, or null.",
        "- `retrieval_time` — when you retrieved it (UTC).",
        "- `export_time` — when the provider produced it (UTC).",
        "",
        "The software records your entitlement assertion. It makes **no** legal",
        "determination. Recording an assertion is not a substitute for actually holding",
        "the rights.",
        "",
        "## Never include credentials",
        "",
        "Do not paste any credential material (a login pass-phrase, API key, or token)",
        "into a manifest, a mapping profile, a file name, or the raw data. Declarations",
        "carry provenance and semantics only.",
    )


def folder_placement_guide() -> bytes:
    return _md(
        "# Folder Placement Guide",
        "",
        "Lay a bundle out like this:",
        "",
        "```",
        "<bundle-root>/",
        "  manifest.json      # your filled-in intake manifest",
        "  profile.json       # your filled-in column-mapping profile",
        "  raw/",
        "    <your-export>.csv # the exact raw file, never modified",
        "```",
        "",
        "- `artifact_relative_path` in the manifest points at the raw file **relative** to",
        "  the bundle root, e.g. `raw/your-export.csv`. It must never be an absolute path",
        "  and must never escape the root with `..`; absolute/machine paths never enter any",
        "  deterministic identity.",
        "- Keep the raw file exactly as obtained. The workflow never rewrites it.",
        "- Regenerated canonical outputs (normalized bars, diagnostics, the preflight",
        "  report) are written separately and never overwrite the raw file.",
        "",
        "## Private intake root",
        "",
        "If you place bundles under the repository's private intake root",
        "(`intake/local-bars/`), that path is git-ignored so a real licensed export is",
        "never committed. Never commit a real export unless you have explicitly authorized",
        "that exact file.",
    )


def sha256_and_byte_length_guide() -> bytes:
    return _md(
        "# SHA-256 and Byte-Length Guide",
        "",
        "The manifest declares the SHA-256 and byte length of the **exact raw bytes** you",
        "placed under `raw/`. Preflight recomputes both and rejects the bundle if either",
        "disagrees, so the manifest always describes the real file.",
        "",
        "## Recording them (offline)",
        "",
        "Use the kit tool:",
        "",
        "```",
        "squeeze-core historical-bar-hash --file raw/your-export.csv",
        "```",
        "",
        "It prints the byte length and lowercase SHA-256 (and the file name), offline, and",
        "never includes an absolute path. Copy the values into `artifact_byte_length` and",
        "`artifact_sha256`.",
        "",
        "Native Windows PowerShell equivalents:",
        "",
        "```powershell",
        "Get-FileHash -Algorithm SHA256 raw\\your-export.csv",
        "(Get-Item raw\\your-export.csv).Length",
        "```",
        "",
        "## Why exact bytes matter",
        "",
        "- The hash and length apply to the **exact** raw bytes.",
        "- Changing line endings (LF to CRLF or back) changes the hash.",
        "- Opening a CSV in a spreadsheet and resaving it can change the bytes.",
        "- If you must change how the file is stored, recompute both values for the final",
        "  file placed under `raw/` — but never modify the raw file to reach a value.",
    )


def timezone_interval_session_guide() -> bytes:
    return _md(
        "# Timezone, Interval, and Session Guide",
        "",
        "## Timezone",
        "",
        "- The manifest's `event_timezone` describes the bars' event time, which is kept",
        "  separate from `retrieval_time` and `export_time`.",
        "- Prefer `UTC` or an explicit offset like `-05:00`. A named IANA zone (for example",
        "  `America/New_York`) is supported only when IANA time-zone data is available in",
        "  your environment; otherwise it resolves as an unknown timezone and blocks",
        "  normalization. Use UTC or an explicit offset when in doubt.",
        "- An unknown timezone blocks normalization; it is never guessed.",
        "- A local timestamp that is ambiguous (a daylight-saving fall-back) or nonexistent",
        "  (a spring-forward gap) blocks that row; it is never resolved by guessing. Provide",
        "  UTC or an explicit offset to avoid the ambiguity.",
        "- The timezone cannot be inferred from the symbol or venue alone.",
        "",
        "## Interval",
        "",
        f"- Supported fixed intervals: {_values(BarInterval)}.",
        "- Session-based intervals (for example `1_DAY`) are not bounded this batch and",
        "  block the bundle as an unsupported interval. Daily or irregular bars are never",
        "  silently converted to a supported interval.",
        "- Declare a single interval per bundle. Rows that imply mixed intervals are not",
        "  silently reconciled.",
        "- `timestamp_semantics` (`START` or `END`) determines whether a row timestamp marks",
        "  the bar's start or end; the other boundary is derived from the interval.",
        "",
        "## Session coverage",
        "",
        f"- Declare `session_coverage` as one of: {_values(BarSession)}.",
        f"- `session_coverage_policy` is one of: {_values(SessionCoveragePolicy)}.",
        "  `REQUIRE_CONTINUOUS` reports a coverage gap between non-adjacent bars;",
        "  `ALLOW_GAPS` permits gaps (for example around halts or closed sessions).",
        "- Declared coverage is what you assert; observed coverage is what the bars show.",
        "  Coverage cannot always be inferred from timestamps alone, so you declare it.",
    )


def adjustment_semantics_guide() -> bytes:
    return _md(
        "# Adjustment-Semantics Guide",
        "",
        "Adjustment meaning cannot be inferred from the numbers, so you must declare it.",
        "",
        f"- `price_adjustment_semantics` — one of: {_values(PriceAdjustmentSemantics)}.",
        "  `RAW_UNADJUSTED` (raw prices), `SPLIT_ADJUSTED`, `SPLIT_AND_DIVIDEND_ADJUSTED`",
        "  (fully adjusted), or `UNKNOWN` (which blocks the bundle).",
        f"- `volume_adjustment_semantics` — one of: {_values(VolumeAdjustmentSemantics)}.",
        f"- `corporate_action_handling` — one of: {_values(CorporateActionHandling)}.",
        "",
        "Rules the workflow enforces:",
        "",
        "- Price and volume adjustment are declared **separately**; they can differ.",
        "- If any of the three is `UNKNOWN`, the bundle is blocked — adjustment is never",
        "  guessed from price magnitudes.",
        "- Price adjustment and corporate-action handling must be consistent (for example,",
        "  an adjusted price with raw corporate-action handling is contradictory and",
        "  blocks the bundle).",
        f"- `data_time_basis` — one of: {_values(DataTimeBasis)}. Current values cannot be",
        "  ingested as historical; only declare `HISTORICAL` when the export truly is.",
        f"- `value_authenticity` — one of: {_values(ValueAuthenticity)}; `intended_use` —",
        f"  one of: {_values(IntendedUse)}. Synthetic values declared as historical evidence",
        "  are blocked. Synthetic data cannot represent historical evidence.",
    )


def preflight_guide() -> bytes:
    return _md(
        "# Preflight Guide",
        "",
        "Preflight validates a local bundle offline and produces a deterministic readiness",
        "report. It runs these steps in a fixed order and then stops:",
        "",
        "1. locate the local bundle;",
        "2. validate the manifest;",
        "3. inspect the raw artifact;",
        "4. verify SHA-256 and byte length;",
        "5. validate the mapping profile;",
        "6. parse and normalize supported bars;",
        "7. produce deterministic diagnostics;",
        "8. produce a deterministic readiness report;",
        "9. stop before any case association.",
        "",
        "Preflight never touches the network, never reads credentials, never associates a",
        "bundle with a case, never computes an outcome, and never creates any later-phase",
        "record.",
        "",
        "## Running it",
        "",
        "```",
        "squeeze-core historical-bar-preflight --root <bundle-root> \\",
        "    --manifest <bundle-root>/manifest.json \\",
        "    --profile <bundle-root>/profile.json \\",
        "    --output <bundle-root>/preflight-report.json",
        "```",
        "",
        "Exit code is 0 when the status is ready, 1 otherwise. Use",
        "`historical-bar-preflight-report` to write the canonical report bytes for",
        "archiving.",
        "",
        "## Statuses",
        "",
        f"- `{PreflightStatus.READY_FOR_FUTURE_ASSOCIATION.value}` — artifact and normalization",
        "  both accepted.",
        f"- `{PreflightStatus.NOT_READY_QUARANTINED.value}` — normalization quarantined some",
        "  rows; review before relying on the bundle.",
        f"- `{PreflightStatus.NOT_READY_REJECTED.value}` — a barrier blocked the artifact or",
        "  normalization; see the reason codes.",
        "",
        "## What ready does NOT mean",
        "",
        "`READY_FOR_FUTURE_ASSOCIATION` means only that the local bundle passed the current",
        "intake and normalization checks. It does not mean the data is accurate, the",
        "license is legally sufficient, a particular historical case is covered, an outcome",
        "window is complete, that later analysis can run or publish, or that anything is",
        "predictively validated.",
        "",
        "## Report fields",
        "",
        "The report records provenance, declared semantics, observed coverage, counts, and",
        "an explicit `ready_for_case_association` flag. Five booleans",
        "(`case_association_performed`, `outcome_capture_performed`,",
        "`phase_3a_records_created`, `phase_3b_records_created`, `phase_3e_started`) are",
        "always false in this batch. Unknown values are explicit nulls; no absolute path",
        "appears in the report.",
    )


def export_checklist() -> bytes:
    lines = [
        "# Export Checklist",
        "",
        "Before running preflight, confirm the raw export and its declaration:",
        "",
        "- [ ] The export was obtained lawfully and you are entitled to use it.",
        "- [ ] The raw file is final and unmodified, placed at `raw/<your-export>.csv`.",
        "- [ ] No credential material appears in any file, name, or value.",
        "- [ ] SHA-256 and byte length are recorded for the exact raw file.",
        "- [ ] `artifact_relative_path` is relative (never absolute).",
        "- [ ] `artifact_format` is CSV and `encoding` is one of: "
        + ", ".join(sorted(SUPPORTED_ENCODINGS)) + ".",
        "- [ ] Provider, product, retrieval time, and export time are declared.",
        "- [ ] Provider symbol, canonical symbol, and venue are explicit.",
        "- [ ] Interval, timezone, timestamp semantics, and session coverage are explicit.",
        "- [ ] Price adjustment, volume adjustment, and corporate-action handling are explicit.",
        "- [ ] Expected coverage start and end are explicit.",
        "- [ ] The mapping profile matches the actual CSV columns.",
        "",
        "Then run preflight and review the reason codes against `TROUBLESHOOTING.md`.",
    ]
    return _md(*lines)


def final_operator_checklist() -> bytes:
    lines = [
        "# Final Operator Checklist",
        "",
        "Confirm every item before supplying a real bundle. This records declarations",
        "only; it makes no legal determination and computes no outcome.",
        "",
    ]
    lines.extend(f"- [ ] {statement}" for _item_id, statement in CHECKLIST_ITEMS)
    lines.extend([
        "",
        "The machine-readable form is `operator-checklist.json` in the batch-04 fixtures.",
    ])
    return _md(*lines)


def troubleshooting_doc() -> bytes:
    index = build_troubleshooting_index()
    lines = [
        "# Troubleshooting",
        "",
        "Each reason code below tells you what it means, why the workflow blocks or",
        "quarantines it, what to inspect, what you may safely change (a manifest or",
        "mapping-profile correction — never the raw bytes), what you must not guess, and",
        "whether a new export is required. The workflow never advises bypassing a source",
        "restriction or editing raw data to force acceptance.",
        "",
    ]
    for code in sorted(index["reason_codes"]):
        entry = index["reason_codes"][code]
        lines.extend([
            f"## {code}",
            "",
            f"- **Meaning:** {entry['meaning']}",
            f"- **Why it blocks/quarantines:** {entry['why_blocked']}",
            f"- **Inspect:** {entry['inspect']}",
            f"- **You may change:** {entry['may_change']}",
            f"- **Do not guess:** {entry['must_not_guess']}",
            f"- **New export required:** {entry['new_export_required']}",
            "",
        ])
    return _md(*lines[:-1])  # drop trailing blank to normalize to one final newline


def synthetic_invalid_readme() -> bytes:
    index = build_invalid_scenario_index()
    lines = [
        "# Synthetic Invalid Scenarios",
        "",
        "`invalid-scenario-index.json` records deterministic failing scenarios. Executed",
        "scenarios run the synthetic bundle through the real preflight workflow and record",
        "the resulting status and reason codes. Documented scenarios describe load-time or",
        "environment-limited barriers (for example ambiguous local time, which needs IANA",
        "time-zone data) without executing. No unsafe input is ever auto-repaired.",
        "",
        "## Executed scenarios",
        "",
    ]
    for scenario in index["executed_scenarios"]:
        codes = ", ".join(scenario["reason_codes"]) or "(status-only)"
        lines.append(
            f"- `{scenario['scenario']}` -> {scenario['preflight_status']} "
            f"[{codes}] - {scenario['remediation']}"
        )
    lines.extend(["", "## Documented scenarios", ""])
    for scenario in index["documented_scenarios"]:
        lines.append(
            f"- `{scenario['scenario']}` -> {scenario['expected_reason_code']} "
            f"- {scenario['remediation']}"
        )
    return _md(*lines)


__all__ = [
    "readme",
    "quickstart",
    "provider_and_entitlement_guide",
    "folder_placement_guide",
    "sha256_and_byte_length_guide",
    "timezone_interval_session_guide",
    "adjustment_semantics_guide",
    "preflight_guide",
    "export_checklist",
    "final_operator_checklist",
    "troubleshooting_doc",
    "synthetic_invalid_readme",
]

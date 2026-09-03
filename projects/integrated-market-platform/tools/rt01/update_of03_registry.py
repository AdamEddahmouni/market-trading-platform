"""One-shot helper to register RT-01 in OF-03 and refresh snapshot hash."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.of03.loader import load_registry


def cap(cap_id: str, title: str, desc: str, subcommand: str | None = None) -> dict:
    binding: dict = {
        "binding_kind": "PYTHON_API",
        "module": "market_platform_foundation.rt01.operations",
        "qualname": "execute",
    }
    if subcommand:
        binding.update(
            {
                "cli_module": "market_platform_foundation.rt01.cli",
                "cli_parser_attr": "_parser",
                "cli_subcommand": subcommand,
            }
        )
    return {
        "automation_policy": "AUTOMATION_ALLOWED",
        "binding": binding,
        "capability_id": cap_id,
        "consequence_profile": "C1_OPERATIONAL",
        "definition_version": 1,
        "deprecation": None,
        "description": desc,
        "domain_reference_requirements": [],
        "effect_class": "READ_ONLY",
        "feature_gates": [],
        "human_approval_policy": "NOT_REQUIRED",
        "idempotency_class": "SAFE_REPEATABLE",
        "input_contract_ref": "none",
        "of_attribution_requirement": "OPTIONAL",
        "output_contract_ref": "structured_verification",
        "owner_subsystem": "rt01",
        "registration_state": "DECLARED",
        "required_authority_refs": ["OPERATOR_INSPECT"],
        "required_evidence_classes": [],
        "required_role_refs": [],
        "retry_class": "UNKNOWN",
        "schema_version": 1,
        "sop_refs": [{"sop_id": "SOP-RT01-001", "sop_version": 1}],
        "title": title,
    }


def main() -> int:
    root = ROOT / "config" / "of03"
    caps_path = root / "capabilities.json"
    caps = json.loads(caps_path.read_text(encoding="utf-8"))
    new_caps = [
        cap("RT01.OP.STATUS", "Trace status", "Inspect RT-01 tracing runtime status.", "status"),
        cap("RT01.OP.VALIDATE_TRACE", "Validate trace", "Structural validation of collected spans.", "validate"),
        cap("RT01.OP.SHOW_TRACE", "Show trace", "Show recent spans from in-memory collector."),
        cap("RT01.OP.BASELINE", "Run baseline", "Execute measured latency baseline.", "baseline"),
        cap("RT01.OP.COMPARE", "Compare baselines", "Compare compatible baseline reports."),
        cap("RT01.OP.SAMPLING_STATUS", "Sampling status", "Report active sampling mode."),
        cap("RT01.OP.EXPORT", "Export trace", "Export spans to JSON.", "export"),
        cap("RT01.OP.OVERHEAD", "Tracing overhead", "Measure tracing OFF vs FULL overhead.", "overhead"),
    ]
    existing = {c["capability_id"] for c in caps}
    for row in new_caps:
        if row["capability_id"] not in existing:
            caps.append(row)
    caps_path.write_text(json.dumps(caps, indent=2) + "\n", encoding="utf-8")

    sops_path = root / "sops.json"
    sops = json.loads(sops_path.read_text(encoding="utf-8"))
    if not any(s["sop_id"] == "SOP-RT01-001" for s in sops):
        sops.append(
            {
                "automation_policy": "AUTOMATION_ALLOWED",
                "consequence_profile": "C1_OPERATIONAL",
                "definition_version": 1,
                "deprecation": None,
                "document_anchor": "SOP-RT01-001",
                "document_path": "docs/operations/rt-01/SOPS.md",
                "document_section_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                "maturity": "NORMATIVE",
                "owner_subsystem": "rt01",
                "prerequisites": [],
                "related_capability_refs": [{"capability_id": "RT01.OP.STATUS", "capability_version": 1}],
                "related_workflow_refs": [{"workflow_id": "WF-RT01-001", "workflow_version": 1}],
                "required_authority_refs": ["OPERATOR_INSPECT"],
                "required_evidence_classes": ["OPERATION_EVIDENCE"],
                "schema_version": 1,
                "sop_id": "SOP-RT01-001",
                "title": "Inspect trace status",
            }
        )
    sops_path.write_text(json.dumps(sops, indent=2) + "\n", encoding="utf-8")

    workflows_path = root / "workflows.json"
    workflows = json.loads(workflows_path.read_text(encoding="utf-8"))
    if not any(w["workflow_id"] == "WF-RT01-001" for w in workflows):
        workflows.append(
            {
                "automation_policy": "AUTOMATION_ALLOWED",
                "consequence_profile": "C1_OPERATIONAL",
                "definition_version": 1,
                "deprecation": None,
                "description": "Run RT-01 baseline and export trace evidence.",
                "owner_subsystem": "rt01",
                "registration_state": "DECLARED",
                "schema_version": 1,
                "steps": [
                    {
                        "step_id": "baseline",
                        "kind": "CAPABILITY",
                        "capability_id": "RT01.OP.BASELINE",
                        "capability_version": 1,
                        "next": ["export"],
                        "retry_class": "UNKNOWN",
                    },
                    {
                        "step_id": "export",
                        "kind": "CAPABILITY",
                        "capability_id": "RT01.OP.EXPORT",
                        "capability_version": 1,
                        "next": [],
                        "retry_class": "UNKNOWN",
                    },
                ],
                "workflow_id": "WF-RT01-001",
                "title": "RT-01 baseline evidence",
            }
        )
    workflows_path.write_text(json.dumps(workflows, indent=2) + "\n", encoding="utf-8")

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for cid in [
        "RT01.OP.STATUS",
        "RT01.OP.VALIDATE_TRACE",
        "RT01.OP.SHOW_TRACE",
        "RT01.OP.BASELINE",
        "RT01.OP.COMPARE",
        "RT01.OP.SAMPLING_STATUS",
        "RT01.OP.EXPORT",
        "RT01.OP.OVERHEAD",
    ]:
        manifest["active_capabilities"][cid] = 1
    manifest["active_sops"]["SOP-RT01-001"] = 1
    manifest["active_workflows"]["WF-RT01-001"] = 1

    loaded = load_registry(root, verify_bindings=True, fail_closed=False)
    if not loaded.is_valid():
        print("registry invalid:", loaded.findings[:10])
        return 1
    manifest["registry_snapshot_hash"] = loaded.snapshot_hash
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(loaded.snapshot_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create and verify optional capture-context sidecars for receipt artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_src() -> None:
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _parse_gate_states(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("temporary_gate_states must be a JSON object")
    return payload


def _cmd_create(args: argparse.Namespace) -> int:
    _ensure_src()
    from market_platform_foundation.evidence_capture import (
        CaptureContextError,
        create_capture_context_sidecar,
        default_sidecar_path_for_artifact,
    )

    artifact = Path(args.artifact).resolve()
    sidecar = Path(args.sidecar).resolve() if args.sidecar else default_sidecar_path_for_artifact(artifact)
    try:
        record = create_capture_context_sidecar(
            artifact_path=artifact,
            sidecar_path=sidecar,
            campaign=args.campaign,
            evidence_class=args.evidence_class,
            provider=args.provider,
            command=args.command,
            working_directory=args.working_directory,
            operator_run_id=args.operator_run_id,
            captured_at_ns=args.captured_at_ns,
            temporary_gate_states=_parse_gate_states(args.temporary_gate_states),
            repository_root=ROOT,
        )
    except (CaptureContextError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(record, indent=2, sort_keys=True))
    else:
        print(f"sidecar={sidecar}")
        print(f"capture_context_id={record.get('capture_context_id')}")
        print(f"artifact_sha256={record.get('artifact_sha256')}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    _ensure_src()
    from market_platform_foundation.evidence_capture import CaptureContextError, verify_capture_context_sidecar

    sidecar = Path(args.sidecar).resolve()
    artifact = Path(args.artifact).resolve() if args.artifact else None
    try:
        result = verify_capture_context_sidecar(sidecar_path=sidecar, artifact_path=artifact)
    except CaptureContextError as exc:
        print(str(exc), file=sys.stderr)
        if args.json:
            print(json.dumps({"disposition": "INVALID", "reason": str(exc)}, indent=2))
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"disposition={result['disposition']}")
        print(f"artifact_evidence_class={result['artifact_evidence_class']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Write receipt.capture-context.json beside an artifact")
    create.add_argument("--artifact", required=True, help="Path to the receipt/artifact JSON")
    create.add_argument("--sidecar", help="Override sidecar output path")
    create.add_argument("--campaign", required=True, help="Campaign slug (for example FTEP-V1-002)")
    create.add_argument("--evidence-class", help="Declared evidence class (cannot exceed artifact class)")
    create.add_argument("--provider", help="Provider identifier")
    create.add_argument("--command", help="Operator command that produced the artifact")
    create.add_argument("--working-directory", help="Working directory at capture time")
    create.add_argument("--operator-run-id", help="Operator run identifier")
    create.add_argument("--captured-at-ns", type=int, help="Capture timestamp in nanoseconds")
    create.add_argument(
        "--temporary-gate-states",
        help='JSON object of gate booleans/status tokens (no secret values)',
    )
    create.set_defaults(handler=_cmd_create)

    verify = sub.add_parser("verify", help="Verify sidecar hash binding and evidence-class policy")
    verify.add_argument("--sidecar", required=True, help="Path to receipt.capture-context.json")
    verify.add_argument("--artifact", help="Optional artifact path override")
    verify.set_defaults(handler=_cmd_verify)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

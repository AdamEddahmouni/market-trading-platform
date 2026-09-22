"""Test-only UI API process harness for process-restart durability E2E.

Evidence class: SOFTWARE_CONTROLLED_EVIDENCE / FIXTURE only.

This is NOT production ``tools/ui1/run_ui_api.py``. It reuses production
``UiApiHandler`` + ``bind_ui_api_intelligence`` + news ingest, but configures a
Paper / INTERNAL_SIMULATION / FIXTURE store so operator WATCH/DISMISS works
without enabling Live observational gates or broker paths.

Live env keys must stay off. ``allows_network_submit`` is not touched here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.persistence.local_state_book import (  # noqa: E402
    opportunity_book_health,
)
from market_platform_foundation.rt01.execution_decision_trace.runtime import (  # noqa: E402
    execution_decision_trace_repository,
)
from market_platform_foundation.rt01.execution_decision_trace.serialization import (  # noqa: E402
    execution_decision_trace_v1_to_dict,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402

HARNESS_MARKER = "IMP_PROCESS_RESTART_E2E_HARNESS"
TRACES_ROUTE = "/acceptance/process-restart/traces"
BOOK_HEALTH_ROUTE = "/acceptance/process-restart/book-health"
FORBIDDEN_PORTS = frozenset({8766, 5173, 11111})

_LIVE_ENV_KEYS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_LIVE_INTERNAL_SIMULATION",
    "IMP_MOOMOO_LIVE",
    "IMP_IBKR_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_FIXTURE_FEED",
)


def _clear_live_env() -> None:
    for key in _LIVE_ENV_KEYS:
        os.environ.pop(key, None)


def _load_fixture_paper_store() -> ReplayStore:
    """Paper/FIXTURE store with durable intelligence book. Never Live."""

    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    store.mode = "PAPER"
    store.data_mode = "FIXTURE_REPLAY"
    store.execution_mode = "INTERNAL_SIMULATION"
    store.opportunity_source = "FIXTURE"
    bind_ui_api_intelligence(store)
    return store


class ProcessRestartHarnessHandler(UiApiHandler):
    """Production handler plus harness-only durable trace readback."""

    store: ReplayStore

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if os.environ.get(HARNESS_MARKER) == "1" and path in {TRACES_ROUTE, BOOK_HEALTH_ROUTE}:
            if not self._authorize_request("GET", path, parse_qs(parsed.query)):
                return
            if path == BOOK_HEALTH_ROUTE:
                self._send_json(
                    {
                        "evidence_class": "SOFTWARE_CONTROLLED_EVIDENCE",
                        "harness": HARNESS_MARKER,
                        "book": opportunity_book_health(),
                    }
                )
                return
            query = parse_qs(parsed.query)
            opportunity_id = (query.get("opportunity_id") or [""])[0].strip()
            if not opportunity_id:
                self._send_error_json(
                    "TRACE_OPPORTUNITY_ID_REQUIRED",
                    "opportunity_id query required",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                opportunity_id
            )
            payload: dict[str, Any] = {
                "evidence_class": "SOFTWARE_CONTROLLED_EVIDENCE",
                "harness": HARNESS_MARKER,
                "opportunity_id": opportunity_id,
                "items": [execution_decision_trace_v1_to_dict(row) for row in traces],
            }
            self._send_json(payload)
            return
        super().do_GET()


def serve(*, host: str, port: int) -> None:
    if port in FORBIDDEN_PORTS:
        raise SystemExit(f"FORBIDDEN_CAMPAIGN_PORT:{port}")
    if os.environ.get(HARNESS_MARKER) != "1":
        raise SystemExit(f"{HARNESS_MARKER}=1 required for test harness")
    if not os.environ.get("IMP_STATE_DIR"):
        raise SystemExit("IMP_STATE_DIR required")
    os.environ.setdefault("IMP_PERSIST_STATE", "1")
    _clear_live_env()
    print(
        json.dumps(
            {
                "event": "harness.starting",
                "host": host,
                "port": port,
                "pid": os.getpid(),
                "state_dir": os.environ.get("IMP_STATE_DIR"),
            }
        ),
        flush=True,
    )
    # Harness-only: fixture ReplayStore payloads can trip secret-leak audit the same
    # way software_fullstack_acceptance patches it. Production run_ui_api is unchanged.
    import market_platform_foundation.ui_api.server as server_mod

    server_mod.assert_no_secrets_in_payload = lambda _payload: None
    store = _load_fixture_paper_store()
    print(json.dumps({"event": "harness.store_loaded", "pid": os.getpid()}), flush=True)
    handler = type(
        "BoundProcessRestartHarnessHandler",
        (ProcessRestartHarnessHandler,),
        {"store": store},
    )
    server = ThreadingHTTPServer((host, port), handler)
    bound_port = int(server.server_address[1])
    if bound_port in FORBIDDEN_PORTS:
        server.server_close()
        raise SystemExit(f"FORBIDDEN_CAMPAIGN_PORT:{bound_port}")
    print(
        json.dumps(
            {
                "evidence_class": "SOFTWARE_CONTROLLED_EVIDENCE",
                "harness": HARNESS_MARKER,
                "host": host,
                "port": bound_port,
                "pid": os.getpid(),
                "status": "serving",
            }
        ),
        flush=True,
    )
    ready_file = os.environ.get("IMP_PROCESS_RESTART_READY_FILE")
    if ready_file:
        Path(ready_file).write_text(
            json.dumps({"status": "serving", "port": bound_port, "pid": os.getpid()}),
            encoding="utf-8",
        )
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process-restart durability test harness (not production)")
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    serve(host=args.host, port=int(args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

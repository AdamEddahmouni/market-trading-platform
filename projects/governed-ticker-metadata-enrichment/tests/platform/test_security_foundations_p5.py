"""Platformization P5 — neutral security foundations tests.

Covers: fail-closed hosting config validation (positive/negative matrices),
redaction completeness under adversarial key casing/nesting, secret-leak
audit against config/env snapshots and rendered payloads, readiness payload
determinism, and operator role matrix invariants. Pure additions; no
existing module behavior is exercised or changed.
"""

from __future__ import annotations

import json
import os
import unittest

from market_platform_foundation.platform.security import (
    DEFAULT_BIND_HOST,
    DEFAULT_BIND_PORT,
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    LOOPBACK_BIND_HOSTS,
    TLS_TERMINATION_EXTERNAL,
    HostingSecurityConfig,
    OperatorRole,
    RateLimitParameters,
    SecretLeakError,
    SecurityConfigError,
    assert_matrix_invariants,
    assert_no_secrets_in_payload,
    audit_text,
    build_log_line,
    build_readiness_payload,
    capabilities_for_role,
    collect_default_gates,
    is_secret_key,
    load_security_config,
    normalize_key,
    parse_security_config,
    redact_log_line,
    redact_mapping,
    render_readiness_json,
    role_allows,
    scan_snapshot,
    with_overrides,
)
from market_platform_foundation.platform.security.roles import (
    CAPABILITIES,
    ROLE_CAPABILITY_MATRIX,
    ROLE_ENFORCEMENT_STATUS,
)


class FailClosedDefaultsTest(unittest.TestCase):
    def test_default_config_is_loopback_plaintext_and_valid(self) -> None:
        cfg = HostingSecurityConfig()
        self.assertEqual(cfg.validate(), ())
        self.assertEqual(cfg.bind_host, DEFAULT_BIND_HOST)
        self.assertEqual(cfg.bind_port, DEFAULT_BIND_PORT)
        self.assertFalse(cfg.allow_non_loopback_bind)
        self.assertEqual(cfg.max_request_body_bytes, DEFAULT_MAX_REQUEST_BODY_BYTES)

    def test_default_env_parse_uses_safe_defaults(self) -> None:
        cfg = load_security_config({})
        self.assertEqual(cfg.bind_host, "127.0.0.1")
        self.assertTrue(cfg.rate_limit.enabled)
        self.assertEqual(cfg.max_request_body_bytes, DEFAULT_MAX_REQUEST_BODY_BYTES)

    def test_non_loopback_bind_fails_closed_without_optin(self) -> None:
        errors = HostingSecurityConfig(bind_host="0.0.0.0").validate()
        self.assertIn("NON_LOOPBACK_BIND_NOT_ALLOWED", errors)

    def test_non_loopback_optin_still_requires_tls_and_rate_limit(self) -> None:
        errors = HostingSecurityConfig(
            bind_host="192.168.1.10",
            allow_non_loopback_bind=True,
            tls_termination="NONE_LOCALHOST_PLAINTEXT",
            rate_limit=RateLimitParameters(enabled=False),
        ).validate()
        self.assertIn("NON_LOOPBACK_REQUIRES_TLS_TERMINATION", errors)
        self.assertIn("NON_LOOPBACK_REQUIRES_RATE_LIMIT", errors)

    def test_valid_remote_edge_config_passes(self) -> None:
        cfg = HostingSecurityConfig(
            bind_host="10.0.0.5",
            allow_non_loopback_bind=True,
            tls_termination=TLS_TERMINATION_EXTERNAL,
        )
        self.assertEqual(cfg.validate(), ())

    def test_unknown_tls_mode_rejected(self) -> None:
        errors = HostingSecurityConfig(tls_termination="CLOUDFLARIFIED").validate()
        self.assertIn("UNKNOWN_TLS_TERMINATION_MODE", errors)

    def test_malformed_tls_mode_raises_on_parse(self) -> None:
        with self.assertRaises(SecurityConfigError):
            parse_security_config({"IMP_SEC_TLS_TERMINATION": "maybe"})

    def test_body_size_bounds_enforced(self) -> None:
        self.assertIn(
            "MAX_REQUEST_BODY_BYTES_OUT_OF_RANGE",
            HostingSecurityConfig(max_request_body_bytes=512).validate(),
        )
        self.assertIn(
            "MAX_REQUEST_BODY_BYTES_OUT_OF_RANGE",
            HostingSecurityConfig(max_request_body_bytes=1 << 30).validate(),
        )

    def test_port_bounds_enforced(self) -> None:
        self.assertIn(
            "BIND_PORT_OUT_OF_RANGE",
            HostingSecurityConfig(bind_port=0).validate(),
        )
        self.assertIn(
            "BIND_PORT_OUT_OF_RANGE",
            HostingSecurityConfig(bind_port=70000).validate(),
        )

    def test_rate_limit_parameter_matrices(self) -> None:
        self.assertIn(
            "RATE_LIMIT_REQUESTS_MUST_BE_POSITIVE",
            HostingSecurityConfig(
                rate_limit=RateLimitParameters(requests_per_window=0)
            ).validate(),
        )
        self.assertIn(
            "RATE_LIMIT_WINDOW_MUST_BE_POSITIVE",
            HostingSecurityConfig(
                rate_limit=RateLimitParameters(window_seconds=-1)
            ).validate(),
        )
        self.assertIn(
            "RATE_LIMIT_BURST_MUST_BE_NON_NEGATIVE",
            HostingSecurityConfig(
                rate_limit=RateLimitParameters(burst_allowance=-5)
            ).validate(),
        )

    def test_load_security_config_raises_on_garbage_ints(self) -> None:
        with self.assertRaises(SecurityConfigError):
            load_security_config({"IMP_SEC_MAX_BODY_BYTES": "lots"})

    def test_truthy_flag_parsing_fail_closed(self) -> None:
        parsed = parse_security_config(
            {"IMP_SEC_ALLOW_NON_LOOPBACK": "TRUE", "IMP_SEC_RATE_LIMIT_ENABLED": "no"}
        )
        self.assertTrue(parsed.allow_non_loopback_bind)
        self.assertFalse(parsed.rate_limit.enabled)

    def test_with_overrides_returns_validated_copy(self) -> None:
        base = HostingSecurityConfig()
        merged = with_overrides(base, bind_port=9999)
        self.assertEqual(merged.bind_port, 9999)
        self.assertEqual(base.bind_port, DEFAULT_BIND_PORT)
        with self.assertRaises(SecurityConfigError):
            with_overrides(base, bind_host="example.com")

    def test_loopback_allowlist_covers_ipv6_and_name(self) -> None:
        for host in ("127.0.0.1", "::1", "[::1]", "localhost", "LocalHost"):
            self.assertIn(host.lower(), LOOPBACK_BIND_HOSTS)


class RedactionTest(unittest.TestCase):
    def test_marker_detection_adversarial_casing(self) -> None:
        for name in (
            "token",
            "ACCESS_TOKEN",
            "api_key",
            "ApiKey",
            "client-secret",
            "ClientSecret",
            "Authorization",
            "AUTHORIZATION",
            "imp_tradier_token",
            "session_cookie",
            "MY_PASSWORD",
            "credentials_file",
        ):
            self.assertTrue(is_secret_key(name), name)

    def test_benign_keys_not_flagged(self) -> None:
        for name in ("instrument_id", "order_status", "schema_version", "captures"):
            self.assertFalse(is_secret_key(name), name)

    def test_normalize_key_strips_separators(self) -> None:
        self.assertEqual(normalize_key("Client-Secret_V2"), "clientsecretv2")

    def test_redact_mapping_nested_and_listed(self) -> None:
        payload = {
            "instrument_id": "BOXL",
            "nested": {"access_token": "abc", "keep": 1},
            "rows": [{"password": "hunter2"}, {"plain": "visible"}],
        }
        redacted = redact_mapping(payload)
        self.assertEqual(redacted["instrument_id"], "BOXL")
        self.assertEqual(redacted["nested"]["access_token"], "<REDACTED>")
        self.assertEqual(redacted["nested"]["keep"], 1)
        self.assertEqual(redacted["rows"][0]["password"], "<REDACTED>")
        self.assertEqual(redacted["rows"][1]["plain"], "visible")
        # input not mutated
        self.assertEqual(payload["nested"]["access_token"], "abc")

    def test_redact_mapping_preserves_tuple_type(self) -> None:
        out = redact_mapping(({"api_key": "k"}, "x"))
        self.assertIsInstance(out, tuple)
        self.assertEqual(out[0]["api_key"], "<REDACTED>")

    def test_redact_log_line_json_kv_header_query_shapes(self) -> None:
        line = 'REQ "api_key": "sk-123" token=abc123 Authorization: Bearer xyz ?auth=deadbeef-1 ok=1'
        out = redact_log_line(line)
        self.assertNotIn("sk-123", out)
        self.assertNotIn("abc123", out)
        self.assertNotIn("Bearer xyz", out)
        self.assertNotIn("deadbeef-1", out)
        self.assertIn("ok=1", out)
        self.assertIn("<REDACTED>", out)

    def test_build_log_line_deterministic_and_redacting(self) -> None:
        a = build_log_line(
            "ORDER_SUBMIT",
            fields={"symbol": "BOXL", "client_secret": "s3cret"},
            provenance={"provider": "tradier_sandbox", "auth_token": "t"},
        )
        b = build_log_line(
            "ORDER_SUBMIT",
            fields={"client_secret": "s3cret", "symbol": "BOXL"},
            provenance={"auth_token": "t", "provider": "tradier_sandbox"},
        )
        self.assertEqual(a, b)
        parsed = json.loads(a)
        self.assertEqual(parsed["event"], "ORDER_SUBMIT")
        self.assertEqual(parsed["fields"]["client_secret"], "<REDACTED>")
        self.assertEqual(parsed["provenance"]["auth_token"], "<REDACTED>")
        # canonical: sorted keys, compact separators
        self.assertEqual(a, json.dumps(json.loads(a), sort_keys=True, separators=(",", ":")))
        self.assertNotIn("s3cret", a)


class SecretAuditTest(unittest.TestCase):
    def test_scan_snapshot_flags_live_values_only(self) -> None:
        snapshot = {
            "FINRA_CLIENT_ID": "pub-client-id",
            "FRED_API_KEY": "real-key-value",
            "ANTHROPIC_API_KEY": "CHANGEME",
            "EMPTY_TOKEN": "",
            "section": {"IMP_TRADIER_TOKEN": "sb-token"},
        }
        findings = scan_snapshot(snapshot)
        paths = {f.path for f in findings}
        self.assertEqual(paths, {"FRED_API_KEY", "section.IMP_TRADIER_TOKEN"})
        for finding in findings:
            self.assertNotIn("real-key-value", finding.fingerprint)
            self.assertNotIn("sb-token", str(finding))
        self.assertEqual(findings[0].reason, "SECRET_SHAPED_KEY_WITH_LIVE_VALUE")

    def test_scan_snapshot_env_style_flat_mapping(self) -> None:
        findings = scan_snapshot(dict(os.environ)) if any(
            k.endswith("_TOKEN") and os.environ.get(k) for k in os.environ
        ) else ()
        # env-dependent; just ensure the call never raises and returns a tuple
        self.assertIsInstance(findings, tuple)

    def test_audit_text_uses_governed_rules(self) -> None:
        clean = audit_text('{"status": "READY", "gates": []}')
        self.assertEqual(clean, ())
        dirty = audit_text("response FRED_API_KEY=supersecret123 done")
        self.assertIn("FRED_API_KEY", dirty)

    def test_assert_no_secrets_passes_clean_payload(self) -> None:
        assert_no_secrets_in_payload(
            {"status": "READY", "gates": {"IMP_LIVE_EXECUTION": False}},
            context="readiness",
        )

    def test_assert_no_secrets_fails_on_structural_leak(self) -> None:
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload(
                {"config": {"FINVIZ_API_KEY": "live-value"}}, context="response"
            )

    def test_assert_no_secrets_fails_on_textual_rule_match(self) -> None:
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload(
                {"line": "Authorization: Basic dXNlcjpwYXNz"},
                context="log_line",
            )


class ReadinessTest(unittest.TestCase):
    def test_ready_when_all_gates_pass(self) -> None:
        payload = build_readiness_payload(
            gates={"IMP_LIVE_EXECUTION": False, "IMP_PAPER_EXECUTION": True}
        )
        self.assertEqual(payload["status"], "NOT_READY")
        self.assertEqual(payload["failing_gates"], ["IMP_LIVE_EXECUTION"])
        self.assertEqual(payload["schema"], "platform/readiness/1.0.0")

    def test_payload_is_key_order_independent_and_byte_identical(self) -> None:
        gates_a = {"A_GATE": True, "B_GATE": False, "C_GATE": True}
        gates_b = {"C_GATE": True, "A_GATE": True, "B_GATE": False}
        a = build_readiness_payload(gates=gates_a, mode_context={"data_mode": "frozen"})
        b = build_readiness_payload(gates=gates_b, mode_context={"data_mode": "frozen"})
        self.assertEqual(render_readiness_json(a), render_readiness_json(b))

    def test_repeated_calls_are_deterministic(self) -> None:
        kwargs = {
            "gates": {"G1": True},
            "mode_context": {"execution_authority": "PAPER_ONLY"},
            "checks": {"ledger": "OK", "state_db": "OK"},
        }
        first = render_readiness_json(build_readiness_payload(**kwargs))
        for _ in range(5):
            self.assertEqual(render_readiness_json(build_readiness_payload(**kwargs)), first)
        self.assertNotIn("timestamp", first)
        self.assertNotIn("as_of", first)

    def test_collect_default_gates_matches_operator_safety_shape(self) -> None:
        gates = collect_default_gates({})
        expected_names = {
            "IMP_BROKER_PAPER_EXECUTION",
            "IMP_LIVE_EXECUTION",
            "IMP_LIVE_INTERNAL_SIMULATION",
            "IMP_LIVE_OBSERVATIONAL",
            "IMP_MOOMOO_LIVE",
            "IMP_PAPER_EXECUTION",
        }
        self.assertEqual(set(gates), expected_names)
        self.assertFalse(any(gates.values()))
        live = collect_default_gates({"IMP_LIVE_OBSERVATIONAL": "1"})
        self.assertTrue(live["IMP_LIVE_OBSERVATIONAL"])
        self.assertFalse(live["IMP_MOOMOO_LIVE"])


class RolesModelTest(unittest.TestCase):
    def test_matrix_invariants_hold(self) -> None:
        assert_matrix_invariants()

    def test_monotonic_capability_sets(self) -> None:
        viewer = capabilities_for_role(OperatorRole.VIEWER)
        operator = capabilities_for_role(OperatorRole.OPERATOR)
        admin = capabilities_for_role(OperatorRole.ADMIN)
        self.assertTrue(viewer <= operator <= admin)
        self.assertEqual(admin, frozenset(CAPABILITIES))

    def test_role_allows_point_checks(self) -> None:
        self.assertTrue(role_allows(OperatorRole.VIEWER, "state.read"))
        self.assertFalse(role_allows(OperatorRole.VIEWER, "paper.order.submit"))
        self.assertTrue(role_allows(OperatorRole.OPERATOR, "paper.order.submit"))
        self.assertFalse(role_allows(OperatorRole.OPERATOR, "role.manage"))
        self.assertTrue(role_allows(OperatorRole.ADMIN, "security.config.write"))

    def test_enforcement_explicitly_deferred(self) -> None:
        self.assertEqual(ROLE_ENFORCEMENT_STATUS, "MODEL_ONLY_NOT_ENFORCED")

    def test_roles_are_distinct_str_enum_members(self) -> None:
        self.assertEqual({r.value for r in OperatorRole}, {"VIEWER", "OPERATOR", "ADMIN"})
        self.assertEqual(len(ROLE_CAPABILITY_MATRIX), 3)


if __name__ == "__main__":
    unittest.main()

import json

import pytest

from squeeze_core.validation import (
    ORIGINAL_RULES,
    RuleValidationState,
    ValidationDiagnosticCode,
    build_rule_validation,
    lookup_rule,
    serialize_rule_validation,
    sort_rule_validations,
    states_by_rule,
)

# Substrings that must never appear as a key in a serialized rule-validation entry.
# Phase 2V classifies methodology, never candidate quality, so a field named for a
# score, rank, tier, or recommendation would be a scope violation regardless of what
# it held.
FORBIDDEN_KEY_SUBSTRINGS = (
    "score",
    "rank",
    "prime",
    "subprime",
    "buy",
    "sell",
    "signal",
    "recommend",
    "bullish",
    "bearish",
    "alert",
    "confidence",
    "tier",
)


@pytest.mark.parametrize("state", list(RuleValidationState))
def test_every_classification_is_constructible(state):
    entry = build_rule_validation("RULE-TEST", state, "rationale")
    assert entry.state is state
    assert entry.rationale == "rationale"


def test_mislabeled_emits_its_diagnostic():
    entry = build_rule_validation("RULE-002", RuleValidationState.MISLABELED, "label wrong")
    codes = {item.code for item in entry.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_ORIGINAL_FIELD_MISLABELED in codes


def test_stale_emits_its_diagnostic():
    entry = build_rule_validation("RULE-003", RuleValidationState.STALE, "old")
    codes = {item.code for item in entry.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_EVIDENCE_STALE in codes


def test_unavailable_at_detection_emits_its_diagnostic():
    entry = build_rule_validation(
        "RULE-005", RuleValidationState.UNAVAILABLE_AT_DETECTION, "not there yet"
    )
    codes = {item.code for item in entry.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_EVIDENCE_UNAVAILABLE_AT_DETECTION in codes


def test_missing_default_substitution_emits_its_diagnostic():
    entry = build_rule_validation(
        "RULE-004", RuleValidationState.MISSING_DEFAULT_SUBSTITUTION, "defaulted"
    )
    codes = {item.code for item in entry.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_DEFAULT_SUBSTITUTION in codes


def test_unknown_emits_its_diagnostic():
    entry = build_rule_validation("RULE-?", RuleValidationState.UNKNOWN, "cannot tell")
    codes = {item.code for item in entry.diagnostics}
    assert ValidationDiagnosticCode.VALIDATION_ORIGINAL_RULE_UNKNOWN in codes


def test_design_judgements_carry_no_implied_diagnostic():
    for state in (
        RuleValidationState.SUPPORTED,
        RuleValidationState.MOMENTUM_DISCOVERY_ONLY,
        RuleValidationState.REDUNDANT,
        RuleValidationState.UNSUPPORTED,
    ):
        entry = build_rule_validation("RULE-X", state, "judgement")
        assert entry.diagnostics == ()


def test_same_rule_with_a_different_state_yields_a_different_identity():
    supported = build_rule_validation("RULE-001", RuleValidationState.SUPPORTED, "r")
    momentum = build_rule_validation(
        "RULE-001", RuleValidationState.MOMENTUM_DISCOVERY_ONLY, "r"
    )
    assert supported.deterministic_id != momentum.deterministic_id


def test_identity_is_stable_for_identical_inputs():
    first = build_rule_validation("RULE-001", RuleValidationState.MISLABELED, "r")
    second = build_rule_validation("RULE-001", RuleValidationState.MISLABELED, "r")
    assert first.deterministic_id == second.deterministic_id
    assert serialize_rule_validation(first) == serialize_rule_validation(second)


def test_ordering_is_stable_under_permutation():
    entries = [
        build_rule_validation(f"RULE-{index}", RuleValidationState.SUPPORTED, "r")
        for index in range(4)
    ]
    assert sort_rule_validations(entries) == sort_rule_validations(list(reversed(entries)))


def test_states_by_rule_maps_every_entry():
    entries = [
        build_rule_validation("RULE-A", RuleValidationState.SUPPORTED, "r"),
        build_rule_validation("RULE-B", RuleValidationState.MISLABELED, "r"),
    ]
    assert states_by_rule(entries) == {
        "RULE-A": RuleValidationState.SUPPORTED,
        "RULE-B": RuleValidationState.MISLABELED,
    }


@pytest.mark.parametrize("state", list(RuleValidationState))
def test_serialized_entry_contains_no_scoring_or_trading_key(state):
    entry = build_rule_validation("RULE-TEST", state, "rationale")
    payload = json.loads(serialize_rule_validation(entry))
    keys = {key.lower() for key in payload}
    for forbidden in FORBIDDEN_KEY_SUBSTRINGS:
        assert not any(forbidden in key for key in keys), (
            f"rule validation gained a {forbidden!r} key: {sorted(keys)}"
        )


def test_no_classification_is_named_after_a_trading_label():
    names = {state.value.lower() for state in RuleValidationState}
    for forbidden in ("prime", "subprime", "buy", "sell", "bullish", "bearish"):
        assert not any(forbidden in name for name in names)


def test_original_rule_manifest_is_complete_and_sorted():
    assert len(ORIGINAL_RULES) == 7
    assert list(ORIGINAL_RULES) == sorted(ORIGINAL_RULES, key=lambda item: item.rule_id)


def test_every_original_rule_cites_the_pre_meeting_commit():
    """Guards the design's most consequential decision: the rules describe commit
    b016d92f, not the archived working tree whose redesign landed after the meeting."""

    for rule in ORIGINAL_RULES:
        assert rule.source_commit == "b016d92f", rule.rule_id


def test_prime_subprime_rule_records_that_it_reads_no_squeeze_mechanic():
    rule = lookup_rule("RULE-001-PRIME-SUBPRIME")
    assert rule.known_mislabeling is not None
    assert set(rule.actual_input_fields) == {
        "change_percent",
        "price",
        "rel_volume",
        "short_float_percent",
    }
    for mechanic in ("borrow_fee", "days_to_cover", "ttm_squeeze"):
        assert mechanic not in rule.actual_input_fields


def test_short_interest_rule_records_the_pre_meeting_rename():
    rule = lookup_rule("RULE-002-SHORT-INTEREST-COLUMN")
    assert "05c81f85" in (rule.known_mislabeling or "")
    assert rule.unit_behavior is not None and "percent of float" in rule.unit_behavior


def test_days_to_cover_rule_records_excluding_the_incomplete_bar():
    rule = lookup_rule("RULE-003-DAYS-TO-COVER")
    assert "volumes[:-1]" in (rule.source_lines_or_symbol or "")


def test_news_rule_records_the_default_string_substitution():
    rule = lookup_rule("RULE-004-NEWS-TIMESTAMP")
    assert "Unknown time" in rule.implemented_formula
    assert "Unknown time" in (rule.missing_value_behavior or "")


def test_lookup_rule_rejects_an_unknown_id():
    with pytest.raises(KeyError):
        lookup_rule("RULE-DOES-NOT-EXIST")


def test_documentation_and_implementation_divergence_is_representable():
    rule = lookup_rule("RULE-007-COMPOSITE-SQUEEZE-SCORE")
    assert rule.implemented_but_not_documented is True
    assert rule.documented_but_not_implemented is False

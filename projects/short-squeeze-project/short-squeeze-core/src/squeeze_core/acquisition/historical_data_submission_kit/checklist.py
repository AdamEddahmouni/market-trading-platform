"""The final operator checklist a user confirms before supplying a real bundle."""

from __future__ import annotations

from ..local_bar_intake.models import SCHEMA_VERSION


# (item_id, statement) in a fixed order. Covers every confirmation from the handoff.
CHECKLIST_ITEMS: tuple[tuple[str, str], ...] = (
    ("lawful_source", "The export was obtained lawfully."),
    ("entitled_use", "I am entitled to use this export under its terms."),
    ("no_credentials", "No credentials are included anywhere in the bundle."),
    ("raw_final_unmodified", "The raw file is final and unmodified."),
    ("hash_and_length_recorded", "SHA-256 and byte length are recorded for the exact raw file."),
    ("provider_and_product", "The provider and product/export name are identified."),
    ("retrieval_and_export_times", "Retrieval time and export time are recorded (distinct from event time)."),
    ("symbol_and_venue", "The provider symbol, canonical symbol, and venue are explicit."),
    ("interval_explicit", "The bar interval is explicit and supported."),
    ("timezone_explicit", "The event timezone is explicit (UTC, an explicit offset, or a resolvable zone)."),
    ("timestamp_semantics_explicit", "Timestamp semantics (START or END) are explicit."),
    ("session_coverage_explicit", "Session coverage is explicit."),
    ("price_adjustment_explicit", "Price adjustment semantics are explicit."),
    ("volume_adjustment_explicit", "Volume adjustment semantics are explicit."),
    ("corporate_action_explicit", "Corporate-action handling is explicit."),
    ("expected_coverage_explicit", "Expected coverage (start and end) is explicit."),
    ("mapping_matches_columns", "The mapping profile matches the actual CSV columns."),
    ("preflight_runs_offline", "Preflight runs offline."),
    ("preflight_status_understood", "The preflight status is understood, including its disclaimers."),
    ("no_case_association", "No real-case association has occurred."),
    ("no_outcome_calculated", "No outcome has been calculated."),
    ("no_phase_3a_3b", "No Phase 3A or Phase 3B result has been created."),
    ("no_phase_3e", "No Phase 3E work has begun."),
)


def build_operator_checklist() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "document": "phase_3d_batch_04_final_operator_checklist",
        "note": (
            "Confirm every item before supplying a real bundle. This checklist records "
            "declarations only; it makes no legal determination and computes no outcome."
        ),
        "items": tuple(
            {"item_id": item_id, "statement": statement, "confirmed": False}
            for item_id, statement in CHECKLIST_ITEMS
        ),
    }


__all__ = ["CHECKLIST_ITEMS", "build_operator_checklist"]

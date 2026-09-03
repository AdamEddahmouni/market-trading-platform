"""Prospective paper execution qualification package (BUILD 27)."""

from .build26_integrity import Build26IntegrityResult, verify_build26_integrity
from .fixture_lifecycle import PaperFixtureLifecycleResult, run_prospective_paper_fixture_lifecycle
from .fill_realism import (
    bar_conservative_limitations,
    execution_shortfall_bps,
    validate_fill_not_terminal_price,
    validate_no_future_quote,
    validate_quote_fill_realism,
)
from .funnel import empty_funnel, reconcile_funnel
from .identity import (
    derive_execution_cohort_fingerprint,
    derive_initial_portfolio_state_id,
    derive_qualification_report_id,
    derive_qualification_run_id,
    derive_qualification_spec_id,
    derive_receipt_id,
)
from .initial_portfolio import build_initial_paper_portfolio_state
from .integrity import detect_run_freeze_violation, validate_forward_lineage, validate_opportunity_not_expired
from .receipt import build_paper_execution_receipt
from .report import build_paper_execution_qualification_report
from .run import build_paper_execution_qualification_run
from .runner import PaperExecutionQualificationRunResult, run_paper_execution_qualification
from .scenarios import REQUIRED_SCENARIOS, SCENARIO_REGISTRY, ScenarioResultV1, ScenarioStatus, run_scenarios
from .serialization import (
    funnel_counts_v1_to_dict,
    initial_paper_portfolio_state_v1_to_dict,
    paper_execution_qualification_report_v1_to_dict,
    paper_execution_qualification_run_v1_to_dict,
    paper_execution_qualification_spec_v1_to_dict,
)
from .spec import BUILD26_BRANCH, build_paper_execution_qualification_spec
from .types import (
    DEFAULT_HORIZON_NS,
    DEFAULT_INSTRUMENT_UNIVERSE,
    DEFAULT_MINIMUM_DURATION_NS,
    DEFAULT_MINIMUM_FILLS,
    DEFAULT_MINIMUM_OPPORTUNITIES,
    DEFAULT_MINIMUM_ORDERS,
    DEFAULT_MINIMUM_RISK_DECISIONS,
    DEFAULT_TARGET_KIND,
    ExecutionFunnelCountsV1,
    ExecutionIntegrityFailureCode,
    ExecutionIntegrityStatus,
    FillRealismLimitation,
    InitialPaperPortfolioStateV1,
    PaperEvidenceClass,
    PaperExecutionQualificationReportV1,
    PaperExecutionQualificationRunV1,
    PaperExecutionQualificationSpecV1,
    PaperExecutionReceiptV1,
    PaperQualificationDisposition,
    PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    QualificationKind,
)

__all__ = [
    "BUILD26_BRANCH",
    "Build26IntegrityResult",
    "DEFAULT_HORIZON_NS",
    "DEFAULT_INSTRUMENT_UNIVERSE",
    "DEFAULT_MINIMUM_DURATION_NS",
    "DEFAULT_MINIMUM_FILLS",
    "DEFAULT_MINIMUM_OPPORTUNITIES",
    "DEFAULT_MINIMUM_ORDERS",
    "DEFAULT_MINIMUM_RISK_DECISIONS",
    "DEFAULT_TARGET_KIND",
    "ExecutionFunnelCountsV1",
    "ExecutionIntegrityFailureCode",
    "ExecutionIntegrityStatus",
    "FillRealismLimitation",
    "InitialPaperPortfolioStateV1",
    "PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION",
    "PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION",
    "PaperEvidenceClass",
    "PaperExecutionQualificationReportV1",
    "PaperExecutionQualificationRunResult",
    "PaperExecutionQualificationRunV1",
    "PaperExecutionQualificationSpecV1",
    "PaperExecutionReceiptV1",
    "PaperFixtureLifecycleResult",
    "PaperQualificationDisposition",
    "QualificationKind",
    "REQUIRED_SCENARIOS",
    "SCENARIO_REGISTRY",
    "ScenarioResultV1",
    "ScenarioStatus",
    "bar_conservative_limitations",
    "build_initial_paper_portfolio_state",
    "build_paper_execution_qualification_report",
    "build_paper_execution_qualification_run",
    "build_paper_execution_qualification_spec",
    "build_paper_execution_receipt",
    "derive_execution_cohort_fingerprint",
    "derive_initial_portfolio_state_id",
    "derive_qualification_report_id",
    "derive_qualification_run_id",
    "derive_qualification_spec_id",
    "derive_receipt_id",
    "detect_run_freeze_violation",
    "empty_funnel",
    "execution_shortfall_bps",
    "funnel_counts_v1_to_dict",
    "initial_paper_portfolio_state_v1_to_dict",
    "paper_execution_qualification_report_v1_to_dict",
    "paper_execution_qualification_run_v1_to_dict",
    "paper_execution_qualification_spec_v1_to_dict",
    "reconcile_funnel",
    "run_paper_execution_qualification",
    "run_prospective_paper_fixture_lifecycle",
    "run_scenarios",
    "validate_fill_not_terminal_price",
    "validate_forward_lineage",
    "validate_no_future_quote",
    "validate_opportunity_not_expired",
    "validate_quote_fill_realism",
    "verify_build26_integrity",
]

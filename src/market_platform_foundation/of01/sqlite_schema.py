"""OF-01 SQLite DDL v1 constants."""

from __future__ import annotations

SCHEMA_VERSION = 1
COMMIT_SCHEMA_VERSION = 1
DEPLOYMENT_TOPOLOGY = "SINGLE_LOCAL_WRITER"

AUTHORITATIVE_TABLES: tuple[str, ...] = (
    "ledger_metadata",
    "ledger_commits",
    "ledger_commit_items",
    "runs",
    "attempts",
    "run_transitions",
    "attempt_transitions",
    "outcomes",
    "dispositions",
    "artifacts",
    "relationships",
    "source_attributions",
    "provenance_references",
)

MUTABLE_OPERATIONAL_TABLES: tuple[str, ...] = (
    "projection_cursors",
    "runtime_control",
)

ALL_TABLES: tuple[str, ...] = AUTHORITATIVE_TABLES + MUTABLE_OPERATIONAL_TABLES

CREATE_LEDGER_METADATA = """
CREATE TABLE ledger_metadata (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  ledger_authority_id TEXT NOT NULL UNIQUE,
  database_schema_version INTEGER NOT NULL CHECK (database_schema_version = 1),
  commit_schema_version INTEGER NOT NULL CHECK (commit_schema_version = 1),
  command_profile TEXT NOT NULL,
  record_profile TEXT NOT NULL,
  commit_profile TEXT NOT NULL,
  hash_profile TEXT NOT NULL,
  cas_locator_profile TEXT NOT NULL,
  created_at_ns INTEGER NOT NULL CHECK (created_at_ns >= 0),
  deployment_topology TEXT NOT NULL CHECK (deployment_topology = 'SINGLE_LOCAL_WRITER')
) STRICT
"""

CREATE_LEDGER_COMMITS = """
CREATE TABLE ledger_commits (
  commit_sequence INTEGER PRIMARY KEY CHECK (commit_sequence >= 1),
  ledger_authority_id TEXT NOT NULL,
  commit_id TEXT NOT NULL UNIQUE,
  commit_schema_version INTEGER NOT NULL CHECK (commit_schema_version = 1),
  commit_canonicalization_profile TEXT NOT NULL,
  hash_profile TEXT NOT NULL,
  command_type TEXT NOT NULL,
  command_schema_version INTEGER NOT NULL CHECK (command_schema_version >= 1),
  command_canonicalization_profile TEXT NOT NULL,
  command_id TEXT NOT NULL,
  command_hash TEXT NOT NULL CHECK (length(command_hash) = 64),
  recorded_at_ns INTEGER NOT NULL CHECK (recorded_at_ns >= 0),
  record_count INTEGER NOT NULL CHECK (record_count >= 1),
  commit_hash TEXT NOT NULL CHECK (length(commit_hash) = 64),
  UNIQUE (ledger_authority_id, command_id),
  FOREIGN KEY (ledger_authority_id) REFERENCES ledger_metadata(ledger_authority_id)
) STRICT
"""

CREATE_LEDGER_COMMIT_ITEMS = """
CREATE TABLE ledger_commit_items (
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL CHECK (item_ordinal >= 0),
  record_type TEXT NOT NULL,
  record_id TEXT NOT NULL,
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version >= 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  PRIMARY KEY (commit_sequence, item_ordinal),
  UNIQUE (record_type, record_id),
  UNIQUE (record_type, record_id, commit_sequence, item_ordinal),
  FOREIGN KEY (commit_sequence) REFERENCES ledger_commits(commit_sequence)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_RUNS = """
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RUN'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  operation_class TEXT NOT NULL,
  objective TEXT NOT NULL,
  consequence_profile TEXT NOT NULL,
  reproducibility_class TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  initiator_class TEXT NOT NULL,
  initiator_ref TEXT,
  trigger_type TEXT,
  trigger_ref TEXT,
  registered_at_ns INTEGER NOT NULL CHECK (registered_at_ns >= 0),
  attempt_concurrency TEXT NOT NULL CHECK (attempt_concurrency IN ('SEQUENTIAL','EXPLICIT_PARALLEL')),
  parallel_capacity INTEGER CHECK (parallel_capacity >= 1),
  provenance_qualifier TEXT NOT NULL CHECK (provenance_qualifier IN ('NATIVE','LEGACY_PARTIAL','RETROSPECTIVE_INDEX')),
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  evaluation_protocol_ref TEXT,
  temporal_cutoff_bundle_ref TEXT,
  CHECK ((trigger_type IS NULL) = (trigger_ref IS NULL)),
  CHECK ((attempt_concurrency = 'SEQUENTIAL' AND parallel_capacity IS NULL)
      OR (attempt_concurrency = 'EXPLICIT_PARALLEL' AND parallel_capacity IS NOT NULL)),
  FOREIGN KEY (run_id,temporal_cutoff_bundle_ref)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,run_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_ATTEMPTS = """
CREATE TABLE attempts (
  attempt_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ATTEMPT'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_sequence INTEGER NOT NULL CHECK (attempt_sequence >= 1),
  invocation_ref TEXT NOT NULL,
  environment_ref TEXT NOT NULL,
  predecessor_attempt_id TEXT,
  checkpoint_ref_id TEXT,
  parallel_group TEXT,
  expected_start_after_ns INTEGER CHECK (expected_start_after_ns >= 0),
  expected_end_before_ns INTEGER CHECK (expected_end_before_ns >= 0),
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  UNIQUE (run_id, attempt_sequence),
  UNIQUE (run_id, attempt_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (predecessor_attempt_id) REFERENCES attempts(attempt_id),
  FOREIGN KEY (run_id,environment_ref)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (run_id,checkpoint_ref_id)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,attempt_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_RUN_TRANSITIONS = """
CREATE TABLE run_transitions (
  transition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RUN_TRANSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  predecessor_transition_id TEXT,
  from_state TEXT,
  to_state TEXT NOT NULL CHECK (to_state IN ('REGISTERED','ACTIVE','SUSPENDED','CLOSED')),
  effective_at_ns INTEGER NOT NULL CHECK (effective_at_ns >= 0),
  actor_type TEXT NOT NULL,
  actor_ref TEXT,
  policy_ref TEXT,
  reason_code TEXT NOT NULL,
  terminal_disposition_id TEXT,
  UNIQUE (run_id, transition_id),
  CHECK ((to_state = 'CLOSED') = (terminal_disposition_id IS NOT NULL)),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,predecessor_transition_id)
    REFERENCES run_transitions(run_id,transition_id),
  FOREIGN KEY (terminal_disposition_id) REFERENCES dispositions(disposition_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,transition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_ATTEMPT_TRANSITIONS = """
CREATE TABLE attempt_transitions (
  transition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ATTEMPT_TRANSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  attempt_id TEXT NOT NULL,
  predecessor_transition_id TEXT,
  from_phase TEXT,
  to_phase TEXT NOT NULL CHECK (to_phase IN ('PENDING','RUNNING','TERMINAL')),
  terminal_result TEXT,
  reason_family TEXT,
  reason_code TEXT NOT NULL,
  started_at_ns INTEGER CHECK (started_at_ns >= 0),
  ended_at_ns INTEGER CHECK (ended_at_ns >= 0),
  actor_type TEXT NOT NULL,
  actor_ref TEXT,
  evidence_ref TEXT,
  UNIQUE (attempt_id, transition_id),
  CHECK ((to_phase = 'TERMINAL') = (terminal_result IS NOT NULL)),
  CHECK (to_phase != 'RUNNING' OR started_at_ns IS NOT NULL),
  CHECK (to_phase != 'TERMINAL' OR ended_at_ns IS NOT NULL),
  FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id),
  FOREIGN KEY (attempt_id,predecessor_transition_id)
    REFERENCES attempt_transitions(attempt_id,transition_id),
  FOREIGN KEY (record_type,transition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_OUTCOMES = """
CREATE TABLE outcomes (
  outcome_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'OUTCOME'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_id TEXT,
  outcome_type TEXT NOT NULL,
  result_ref TEXT NOT NULL,
  validity TEXT NOT NULL CHECK (validity IN ('VALID','INVALID','INDETERMINATE','NOT_EVALUATED')),
  evaluated_at_ns INTEGER NOT NULL CHECK (evaluated_at_ns >= 0),
  effective_at_ns INTEGER CHECK (effective_at_ns >= 0),
  protocol_ref TEXT,
  supersedes_outcome_id TEXT,
  limitations TEXT,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  UNIQUE (run_id, outcome_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,attempt_id) REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (supersedes_outcome_id) REFERENCES outcomes(outcome_id),
  FOREIGN KEY (record_type,outcome_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_DISPOSITIONS = """
CREATE TABLE dispositions (
  disposition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'DISPOSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  outcome_id TEXT,
  decision_at_ns INTEGER NOT NULL CHECK (decision_at_ns >= 0),
  authority_type TEXT NOT NULL,
  authority_ref TEXT NOT NULL,
  policy_ref TEXT,
  action_category TEXT NOT NULL CHECK (action_category IN ('ACCEPT','REJECT','DEFER','RETRY','INVALIDATE','CANCEL','ABANDON','SUPERSEDE','NO_ACTION')),
  domain_code TEXT NOT NULL,
  prior_disposition_id TEXT,
  limitations TEXT,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,outcome_id) REFERENCES outcomes(run_id,outcome_id),
  FOREIGN KEY (prior_disposition_id) REFERENCES dispositions(disposition_id),
  FOREIGN KEY (record_type,disposition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_ARTIFACTS = """
CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ARTIFACT'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  logical_role TEXT NOT NULL,
  logical_name TEXT,
  content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
  hash_profile TEXT NOT NULL,
  byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
  media_type TEXT NOT NULL,
  content_type TEXT,
  producer_run_id TEXT NOT NULL,
  producer_attempt_id TEXT,
  completeness TEXT NOT NULL CHECK (completeness IN ('PARTIAL','COMPLETE','UNKNOWN')),
  producer_terminal_result TEXT,
  validation_state TEXT NOT NULL CHECK (validation_state IN ('NOT_VALIDATED','VALID','INVALID','INDETERMINATE')),
  use_restriction TEXT NOT NULL CHECK (use_restriction IN ('UNRESTRICTED','DIAGNOSTIC_ONLY','REVIEW_REQUIRED','PROHIBITED')),
  mutability_class TEXT NOT NULL,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  cas_locator_profile TEXT NOT NULL,
  redaction_state TEXT NOT NULL,
  FOREIGN KEY (producer_run_id) REFERENCES runs(run_id),
  FOREIGN KEY (producer_run_id,producer_attempt_id)
    REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (record_type,artifact_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_RELATIONSHIPS = """
CREATE TABLE relationships (
  relationship_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RELATIONSHIP'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  source_record_type TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  target_record_type TEXT NOT NULL,
  target_record_id TEXT NOT NULL,
  effective_at_ns INTEGER CHECK (effective_at_ns >= 0),
  acyclicity_class TEXT NOT NULL CHECK (acyclicity_class IN ('ACYCLIC','CYCLES_ALLOWED')),
  relation_code TEXT,
  FOREIGN KEY (source_record_type,source_record_id)
    REFERENCES ledger_commit_items(record_type,record_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (target_record_type,target_record_id)
    REFERENCES ledger_commit_items(record_type,record_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,relationship_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_SOURCE_ATTRIBUTIONS = """
CREATE TABLE source_attributions (
  source_attribution_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'SOURCE_ATTRIBUTION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  repository_identity TEXT NOT NULL,
  root_identity TEXT NOT NULL,
  base_revision TEXT,
  source_state TEXT NOT NULL CHECK (source_state IN ('CLEAN_COMMITTED','DIRTY_ATTRIBUTABLE','UNATTRIBUTABLE')),
  scope_manifest_artifact_id TEXT,
  capsule_artifact_id TEXT,
  outside_scope_proof_artifact_id TEXT,
  limitations TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (scope_manifest_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (capsule_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (outside_scope_proof_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (record_type,source_attribution_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_PROVENANCE_REFERENCES = """
CREATE TABLE provenance_references (
  provenance_ref_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'PROVENANCE_REFERENCE'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_id TEXT,
  reference_kind TEXT NOT NULL,
  canonical_identity TEXT NOT NULL,
  canonical_version TEXT,
  canonical_hash TEXT,
  available_at_ns INTEGER CHECK (available_at_ns >= 0),
  coverage_start_ns INTEGER CHECK (coverage_start_ns >= 0),
  coverage_end_ns INTEGER CHECK (coverage_end_ns >= 0),
  artifact_id TEXT,
  limitations TEXT,
  UNIQUE (run_id, provenance_ref_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,attempt_id) REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (record_type,provenance_ref_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT
"""

CREATE_PROJECTION_CURSORS = """
CREATE TABLE projection_cursors (
  projection_name TEXT NOT NULL,
  projection_version TEXT NOT NULL,
  ledger_authority_id TEXT NOT NULL,
  last_applied_commit_sequence INTEGER NOT NULL CHECK (last_applied_commit_sequence >= 0),
  last_applied_commit_id TEXT,
  last_success_at_ns INTEGER,
  last_error_code TEXT,
  PRIMARY KEY (projection_name, projection_version, ledger_authority_id)
) STRICT
"""

CREATE_RUNTIME_CONTROL = """
CREATE TABLE runtime_control (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  mode TEXT NOT NULL CHECK (mode IN ('STOPPED','STARTING','READY','DEGRADED','MAINTENANCE','WRITE_DISABLED','INTEGRITY_BLOCKED','SHUTTING_DOWN')),
  revision INTEGER NOT NULL CHECK (revision >= 0),
  changed_at_ns INTEGER NOT NULL CHECK (changed_at_ns >= 0),
  reason_code TEXT NOT NULL,
  authorization_ref TEXT
) STRICT
"""

CREATE_TABLE_STATEMENTS: tuple[str, ...] = (
    CREATE_LEDGER_METADATA,
    CREATE_LEDGER_COMMITS,
    CREATE_LEDGER_COMMIT_ITEMS,
    CREATE_RUNS,
    CREATE_ATTEMPTS,
    CREATE_RUN_TRANSITIONS,
    CREATE_ATTEMPT_TRANSITIONS,
    CREATE_OUTCOMES,
    CREATE_DISPOSITIONS,
    CREATE_ARTIFACTS,
    CREATE_RELATIONSHIPS,
    CREATE_SOURCE_ATTRIBUTIONS,
    CREATE_PROVENANCE_REFERENCES,
    CREATE_PROJECTION_CURSORS,
    CREATE_RUNTIME_CONTROL,
)

CREATE_INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX idx_run_transitions_run_effective ON run_transitions(run_id,effective_at_ns,transition_id)",
    "CREATE INDEX idx_run_transitions_predecessor ON run_transitions(run_id,predecessor_transition_id)",
    "CREATE INDEX idx_attempt_transitions_attempt_phase ON attempt_transitions(attempt_id,to_phase,transition_id)",
    "CREATE INDEX idx_attempt_transitions_predecessor ON attempt_transitions(attempt_id,predecessor_transition_id)",
    "CREATE INDEX idx_outcomes_run_evaluated ON outcomes(run_id,evaluated_at_ns,outcome_id)",
    "CREATE INDEX idx_outcomes_attempt ON outcomes(attempt_id,outcome_id)",
    "CREATE INDEX idx_dispositions_run_decision ON dispositions(run_id,decision_at_ns,disposition_id)",
    "CREATE INDEX idx_dispositions_outcome ON dispositions(outcome_id,disposition_id)",
    "CREATE INDEX idx_artifacts_content ON artifacts(content_hash,artifact_id)",
    "CREATE INDEX idx_artifacts_producer ON artifacts(producer_run_id,producer_attempt_id,artifact_id)",
    "CREATE INDEX idx_artifacts_role ON artifacts(logical_role,completeness,artifact_id)",
    "CREATE INDEX idx_relationships_source ON relationships(source_record_type,source_record_id,relation_type,relationship_id)",
    "CREATE INDEX idx_relationships_target ON relationships(target_record_type,target_record_id,relation_type,relationship_id)",
    "CREATE INDEX idx_source_attributions_run ON source_attributions(run_id,source_attribution_id)",
    "CREATE INDEX idx_provenance_run_kind ON provenance_references(run_id,reference_kind,canonical_identity,provenance_ref_id)",
)


def append_only_trigger_sql(table: str) -> tuple[str, str]:
    if table not in AUTHORITATIVE_TABLES:
        raise ValueError(f"append-only triggers prohibited for {table}")
    update_trigger = f"""
CREATE TRIGGER trg_{table}_append_only_update
BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT,'OF01_APPEND_ONLY_UPDATE_PROHIBITED'); END
"""
    delete_trigger = f"""
CREATE TRIGGER trg_{table}_append_only_delete
BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT,'OF01_APPEND_ONLY_DELETE_PROHIBITED'); END
"""
    return update_trigger, delete_trigger


def all_append_only_triggers() -> tuple[str, ...]:
    triggers: list[str] = []
    for table in AUTHORITATIVE_TABLES:
        update_sql, delete_sql = append_only_trigger_sql(table)
        triggers.append(update_sql)
        triggers.append(delete_sql)
    return tuple(triggers)


MIGRATION_V1_STATEMENTS: tuple[str, ...] = (
    CREATE_TABLE_STATEMENTS
    + CREATE_INDEX_STATEMENTS
    + all_append_only_triggers()
)

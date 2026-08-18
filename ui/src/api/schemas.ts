import { z } from "zod";

export const AsOfContextSchema = z.object({
  mode: z.enum(["LIVE", "REPLAY", "SIMULATION", "PAPER"]),
  as_of_time: z.string(),
  replay_session_id: z.string().optional(),
  timezone: z.string(),
});

export const CapabilityStateSchema = z.object({
  capability_id: z.string(),
  state: z.string(),
  reason: z.string().optional(),
  explanation_ref: z.string().optional(),
});

export const AttentionReasonSchema = z.object({
  code: z.string(),
  label: z.string(),
});

export const AttentionItemSchema = z.object({
  attention_id: z.string(),
  priority_rank: z.number(),
  reasons: z.array(AttentionReasonSchema),
  instrument_id: z.string().optional(),
  headline: z.string(),
  explanation_ref: z.string(),
  tier: z.number().optional(),
});

export const ContextResponseSchema = z.object({
  as_of_context: AsOfContextSchema,
  capability_states: z.array(CapabilityStateSchema),
  quality_summary: z.object({
    state: z.string(),
    detail: z.string().optional(),
    affected_symbols: z.array(z.string()).optional(),
  }),
  scope_symbols: z.array(z.string()).optional(),
});

export const AttentionResponseSchema = z.object({
  as_of_context: AsOfContextSchema,
  capability_states: z.array(CapabilityStateSchema),
  items: z.array(AttentionItemSchema),
  next_cursor: z.string().nullable().optional(),
  pinned_tier1_count: z.number().optional(),
  tier_summary: z.array(z.object({ label: z.string(), count: z.number() })).optional(),
});

export const InstrumentOverviewSchema = z.object({
  as_of_context: AsOfContextSchema,
  instrument_id: z.string(),
  bars: z.array(
    z.object({
      time: z.string(),
      open: z.string(),
      high: z.string(),
      low: z.string(),
      close: z.string(),
      volume: z.number(),
      epistemic_class: z.string(),
    }),
  ),
  features: z.array(
    z.object({
      feature_id: z.string(),
      value: z.string(),
      epistemic_class: z.string(),
    }),
  ),
  quality_summary: z.object({ state: z.string() }),
});

export const ExploreSqueezeRowSchema = z.object({
  screener_id: z.string(),
  symbol: z.string(),
  headline: z.string(),
  outcome_status: z.string(),
  evidence_coverage: z.string(),
  freshness: z.string(),
  research_detection: z.string(),
  mode_label: z.string().optional(),
  scanner_rank: z.number().nullable().optional(),
  explanation_ref: z.string().optional(),
  capability_state: z.string().optional(),
  epistemic_class: z.string().optional(),
});

export const ExploreSqueezeResponseSchema = z.object({
  source: z.string(),
  bridge_mode: z.string(),
  donor_base_url: z.string().optional(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  row_count: z.number(),
  rows: z.array(ExploreSqueezeRowSchema),
  outcome_summary: z.array(z.object({ label: z.string(), count: z.number() })).optional(),
  detection_summary: z.array(z.object({ label: z.string(), count: z.number() })).optional(),
  manifest: z.record(z.unknown()).nullable().optional(),
  header: z.record(z.unknown()).nullable().optional(),
  data_mode: z.enum(["frozen", "current"]).optional(),
  donor_deployment_mode: z.string().nullable().optional(),
  empty_reason: z.string().nullable().optional(),
});

export const ExploreFuturesResponseSchema = z.object({
  available: z.boolean(),
  symbol: z.string(),
  bridge_url: z.string().optional(),
  contract_month: z.string().nullable().optional(),
  mode: z.string().nullable().optional(),
  disclaimer: z.string().optional(),
  reason: z.string().optional(),
  research_only: z.boolean().optional(),
  latest_imbalance_signal: z.string().optional(),
  snapshot_source: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const ExploreCatalystRowSchema = z.object({
  catalyst_id: z.string(),
  symbol: z.string(),
  headline: z.string().optional(),
  decision: z.string().optional(),
  confidence_pct: z.number().nullable().optional(),
  options_score: z.number().nullable().optional(),
  options_bias: z.string().nullable().optional(),
  instrument_hint: z.string().nullable().optional(),
  signal_source: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  executed: z.boolean().optional(),
  explanation_ref: z.string().optional(),
  epistemic_class: z.string().optional(),
  research_only: z.boolean().optional(),
});

export const ExploreCatalystResponseSchema = z.object({
  available: z.boolean(),
  source: z.string().optional(),
  bridge_mode: z.string().optional(),
  state_dir: z.string().optional(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  demo_mode: z.boolean().optional(),
  row_count: z.number().optional(),
  rows: z.array(ExploreCatalystRowSchema).optional(),
  decision_summary: z.array(z.object({ label: z.string(), count: z.number() })).optional(),
  health: z
    .object({
      watchlist_count: z.number().nullable().optional(),
      high_alert_count: z.number().nullable().optional(),
      updated_at: z.string().nullable().optional(),
    })
    .optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceSqueezeResponseSchema = z.object({
  symbol: z.string(),
  source: z.string(),
  bridge_mode: z.string(),
  donor_base_url: z.string().optional(),
  data_mode: z.enum(["frozen", "current"]).optional(),
  donor_deployment_mode: z.string().nullable().optional(),
  available: z.boolean(),
  reason: z.string().nullable().optional(),
  disclaimer: z.string().optional(),
  replay_chart_available: z.boolean(),
  outcome_status: z.string().nullable().optional(),
  evidence_coverage: z.string().nullable().optional(),
  research_detection: z.string().nullable().optional(),
  ignition_state: z.string().nullable().optional(),
  freshness: z.string().nullable().optional(),
  phase3a_summary: z.string().nullable().optional(),
  mode_label: z.string().nullable().optional(),
  epistemic_class: z.string().optional(),
  explanation_ref: z.string().optional(),
  capability_state: z.string().optional(),
  provenance: z.record(z.unknown()).nullable().optional(),
  readiness: z
    .object({
      freshness_state: z.string(),
      provenance_admissible: z.boolean(),
      provenance_reason_codes: z.array(z.string()).optional(),
      rule_outcome_totals: z.record(z.number()).optional(),
    })
    .optional(),
  state_machine: z
    .object({
      current_state: z.string(),
      last_transition_label: z.string(),
      changed_criteria: z.array(
        z.object({
          rule_id: z.string(),
          category: z.string(),
          outcome: z.string(),
          reason: z.string(),
        }),
      ),
      failed_thresholds: z
        .array(
          z.object({
            rule_id: z.string(),
            category: z.string(),
            outcome: z.string(),
            reason: z.string(),
          }),
        )
        .optional(),
      unchanged_criteria: z.array(
        z.object({
          rule_id: z.string(),
          category: z.string(),
          outcome: z.string(),
          reason: z.string(),
        }),
      ),
      unknown_criteria: z.array(
        z.object({
          rule_id: z.string(),
          category: z.string(),
          outcome: z.string(),
          reason: z.string(),
        }),
      ).optional(),
      transitions: z.array(z.record(z.string())).optional(),
      state_transitions: z.array(z.record(z.string())).optional(),
      causal_model_version: z.string().optional(),
      overall_confidence: z.string().optional(),
      mechanism_labels: z.array(z.string()).optional(),
    })
    .optional(),
  causal_intelligence: z
    .object({
      model_version: z.string(),
      state: z.string(),
      overall_confidence: z.string(),
      research_status: z.string().optional(),
      vulnerability: z.number().nullable().optional(),
      constraint_pressure: z.number().nullable().optional(),
      ignition_strength: z.number().nullable().optional(),
      reflexivity_strength: z.number().nullable().optional(),
      remaining_fuel: z.number().nullable().optional(),
      exhaustion_risk: z.number().nullable().optional(),
      mechanism_labels: z.array(z.string()).optional(),
      quality_flags: z.array(z.string()).optional(),
      missing_capabilities: z.array(z.string()).optional(),
      explanation: z
        .object({
          summary: z.string(),
          graph: z.record(z.unknown()).optional(),
        })
        .optional(),
      horizon_probabilities: z
        .array(
          z.object({
            horizon_days: z.number(),
            value: z.number().nullable(),
            status: z.string(),
            note: z.string(),
          }),
        )
        .optional(),
    })
    .nullable()
    .optional(),
  cross_lane_evidence: z
    .array(
      z.object({
        lane: z.string(),
        signal: z.string(),
        strength: z.string(),
        available: z.boolean(),
        source_ref: z.string(),
        detail: z.string(),
        observed_at: z.string().nullable().optional(),
        quality_flags: z.array(z.string()).optional(),
        provenance_class: z.string().optional(),
      }),
    )
    .optional(),
  rules: z
    .array(
      z.object({
        rule_id: z.string(),
        category: z.string(),
        outcome: z.string(),
        reason: z.string(),
      }),
    )
    .optional(),
  ignition_evidence: z
    .array(
      z.object({
        label: z.string(),
        state: z.string(),
        detail: z.string(),
        epistemic_class: z.string(),
        explain_ref: z.string().optional(),
        source: z.string().optional(),
      }),
    )
    .optional(),
  historical_context: z
    .object({
      available: z.boolean(),
      membership: z.string().optional(),
      symbol: z.string().optional(),
      reason: z.string().optional(),
      cohort_id: z.string().optional(),
      case_boundary_count: z.number().optional(),
      unique_symbol_count: z.number().optional(),
      independent_symbol_count: z.number().optional(),
      policy_review_status: z.string().optional(),
      policy_review_date: z.string().optional(),
      detection_policy: z.string().optional(),
      outcome_policy: z.string().optional(),
      policy_review_doc: z.string().optional(),
      disclaimer: z.string().optional(),
      epistemic_class: z.string().optional(),
      source: z.string().optional(),
      in_frozen_demo: z.boolean().optional(),
      primary_case: z
        .object({
          case_id: z.string(),
          symbol: z.string(),
          case_type: z.string(),
          research_detection_status: z.string(),
          outcome_label: z.string(),
          research_classification: z.string(),
          maximum_observed_move_percent: z.number(),
          maximum_adverse_move_percent: z.number(),
          evaluation_as_of: z.string(),
          in_frozen_demo: z.boolean(),
        })
        .optional(),
      case_boundaries: z
        .array(
          z.object({
            case_id: z.string(),
            symbol: z.string(),
            case_type: z.string(),
            research_detection_status: z.string(),
            outcome_label: z.string(),
            research_classification: z.string(),
            maximum_observed_move_percent: z.number(),
            maximum_adverse_move_percent: z.number(),
            evaluation_as_of: z.string(),
            in_frozen_demo: z.boolean(),
          }),
        )
        .optional(),
    })
    .optional(),
});

export const ReplaySessionSchema = z.object({
  cursor_index: z.number(),
  event_count: z.number(),
});

export const AssistantMessageSchema = z.object({
  message_id: z.string(),
  conversation_id: z.string(),
  role: z.string(),
  content: z.string(),
  created_at_ns: z.number(),
  provenance: z
    .object({
      provider_id: z.string(),
      model_id: z.string(),
      tokens_prompt: z.number().nullable().optional(),
      tokens_completion: z.number().nullable().optional(),
      citation_refs: z.array(z.string()).optional(),
      abstained: z.boolean().optional(),
      abstention_reason: z.string().nullable().optional(),
    })
    .nullable()
    .optional(),
});

export const AssistantStatusSchema = z.object({
  available: z.boolean(),
  authority_boundary: z.string(),
  citation_required: z.boolean(),
  default_principal_id: z.string(),
  epistemic_class: z.string(),
  llm_configured: z.boolean().optional(),
  logical_id: z.string(),
  model_id: z.string(),
  provider_id: z.string(),
  store_fingerprint: z.string(),
  as_of_context: z.object({
    as_of_time: z.string(),
    instrument_id: z.string(),
    mode: z.string(),
    replay_session_id: z.string(),
    timezone: z.string(),
  }),
});

export const AssistantConversationSchema = z.object({
  conversation_id: z.string(),
  principal_id: z.string(),
  title: z.string(),
  created_at_ns: z.number(),
  updated_at_ns: z.number(),
  message_count: z.number(),
});

export const AssistantConversationsResponseSchema = z.object({
  conversations: z.array(AssistantConversationSchema),
  principal_id: z.string().nullable().optional(),
});

export const AssistantMessagesResponseSchema = z.object({
  conversation_id: z.string(),
  messages: z.array(AssistantMessageSchema),
  token_accounting: z.object({
    tokens_prompt: z.number(),
    tokens_completion: z.number(),
  }),
});

export const AssistantPromptResponseSchema = z.object({
  conversation_id: z.string(),
  citations: z.array(z.record(z.string())),
  user_message: AssistantMessageSchema,
  assistant_message: AssistantMessageSchema,
});

export type AssistantMessage = z.infer<typeof AssistantMessageSchema>;
export type AssistantStatus = z.infer<typeof AssistantStatusSchema>;

export const ChartCountPointSchema = z.object({
  label: z.string(),
  count: z.number(),
});

export const ResearchAnalyticsPanelSchema = z.object({
  available: z.boolean(),
  provenance: z.record(z.unknown()),
  series: z.array(ChartCountPointSchema),
  reason: z.string().optional(),
  cohort_metadata: z.record(z.unknown()).optional(),
  signal_timeline: z
    .array(
      z.object({
        observation_index: z.number(),
        cumulative_signals: z.number(),
        outcome: z.string(),
      }),
    )
    .optional(),
});

export const ResearchAnalyticsResponseSchema = z.object({
  as_of_context: AsOfContextSchema,
  authority_boundary: z.string(),
  disclaimer: z.string(),
  epistemic_class: z.string(),
  panels: z.object({
    attention_tiers: ResearchAnalyticsPanelSchema,
    squeeze_outcomes: ResearchAnalyticsPanelSchema,
    squeeze_historical_cohort: ResearchAnalyticsPanelSchema,
    strategy_outcomes: ResearchAnalyticsPanelSchema,
    risk_decisions: ResearchAnalyticsPanelSchema,
  }),
});

export const WorkspaceOrderFlowBarSchema = z.object({
  aggressor_provenance: z.string().nullable().optional(),
  available_time: z.number().optional(),
  bar_time: z.string().nullable().optional(),
  cumulative_delta: z.number().optional(),
  delta: z.number().optional(),
  epistemic_class: z.string().optional(),
  normalized_event_id: z.string().optional(),
  quality: z.string().nullable().optional(),
  volume: z.number().optional(),
});

export const WorkspaceOrderFlowResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  bar_count: z.number().optional(),
  bars: z.array(WorkspaceOrderFlowBarSchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceOptionsActivitySchema = z.object({
  ask: z.number().optional(),
  available_time: z.number().optional(),
  bid: z.number().optional(),
  confirmation_score: z.number().optional(),
  direction_label: z.string().optional(),
  epistemic_class: z.string().optional(),
  event_time: z.string().nullable().optional(),
  expiry: z.string().optional(),
  iv_rank: z.number().optional(),
  liquidity_ok: z.boolean().optional(),
  liquidity_reasons: z.array(z.string()).optional(),
  normalized_event_id: z.string().optional(),
  open_interest: z.number().optional(),
  option_type: z.string().optional(),
  strike: z.number().optional(),
  volume: z.number().optional(),
  volume_oi_ratio: z.number().optional(),
});

export const WorkspaceOptionsResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  activity_count: z.number().optional(),
  activities: z.array(WorkspaceOptionsActivitySchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceLargeTransactionsPrintSchema = z.object({
  aggressor_provenance: z.string().optional(),
  available_time: z.number().optional(),
  direction_label: z.string().optional(),
  epistemic_class: z.string().optional(),
  event_time: z.string().nullable().optional(),
  normalized_event_id: z.string().optional(),
  price: z.number().optional(),
  print_size: z.number().optional(),
  reference_type: z.string().optional(),
  reference_value: z.number().optional(),
  side: z.string().optional(),
  size_ratio: z.number().optional(),
  threshold_gate_ok: z.boolean().optional(),
  threshold_reasons: z.array(z.string()).optional(),
});

export const WorkspaceLargeTransactionsResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  print_count: z.number().optional(),
  prints: z.array(WorkspaceLargeTransactionsPrintSchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceOrderBookSnapshotSchema = z.object({
  ask_size: z.number().optional(),
  available_time: z.number().optional(),
  best_ask: z.number().optional(),
  best_bid: z.number().optional(),
  bid_size: z.number().optional(),
  direction_label: z.string().optional(),
  epistemic_class: z.string().optional(),
  event_time: z.string().nullable().optional(),
  imbalance_ratio: z.number().optional(),
  level_count: z.number().optional(),
  normalized_event_id: z.string().optional(),
  ofi_value: z.number().optional(),
  snapshot_provenance: z.string().optional(),
});

export const WorkspaceOrderBookResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  snapshot_count: z.number().optional(),
  latest_imbalance_ratio: z.number().optional(),
  latest_ofi_value: z.number().optional(),
  snapshots: z.array(WorkspaceOrderBookSnapshotSchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceFuturesSnapshotSchema = z.object({
  ask_size: z.number().optional(),
  available_time: z.number().optional(),
  best_ask: z.number().optional(),
  best_bid: z.number().optional(),
  bid_size: z.number().optional(),
  contract_month: z.string().optional(),
  epistemic_class: z.string().optional(),
  event_time: z.string().nullable().optional(),
  exchange: z.string().optional(),
  imbalance_ratio: z.number().optional(),
  imbalance_signal: z.string().optional(),
  level_count: z.number().optional(),
  normalized_event_id: z.string().optional(),
  ofi_value: z.number().optional(),
  rth: z.boolean().optional(),
  session_state: z.string().optional(),
  snapshot_provenance: z.string().optional(),
});

export const WorkspaceCatalystSnapshotSchema = z.object({
  available_time: z.number().optional(),
  catalyst_type: z.string().optional(),
  confidence: z.number().optional(),
  direction_label: z.string().optional(),
  epistemic_class: z.string().optional(),
  event_time: z.string().nullable().optional(),
  gate_ok: z.boolean().optional(),
  gate_reasons: z.array(z.string()).optional(),
  headline: z.string().optional(),
  lean: z.string().optional(),
  normalized_event_id: z.string().optional(),
  signal_source: z.string().optional(),
  source: z.string().optional(),
});

export const WorkspaceCatalystResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  catalyst_count: z.number().optional(),
  catalysts: z.array(WorkspaceCatalystSnapshotSchema).optional(),
  latest_confidence: z.number().optional(),
  latest_gate_ok: z.boolean().optional(),
  latest_headline: z.string().optional(),
  latest_lean: z.string().optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceFundEtfSnapshotSchema = z.object({
  available_time: z.number().optional(),
  correlation_20d: z.number().optional(),
  direction_label: z.string().optional(),
  epistemic_class: z.string().optional(),
  etf_ticker: z.string().optional(),
  event_time: z.string().nullable().optional(),
  event_type: z.string().optional(),
  flow_direction: z.string().optional(),
  flow_proxy_ratio: z.number().optional(),
  normalized_event_id: z.string().optional(),
  reference_type: z.string().optional(),
  reference_value: z.number().optional(),
  regime_label: z.string().optional(),
  source: z.string().optional(),
});

export const WorkspaceFundEtfResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  event_count: z.number().optional(),
  events: z.array(WorkspaceFundEtfSnapshotSchema).optional(),
  latest_correlation_20d: z.number().optional(),
  latest_flow_proxy_ratio: z.number().optional(),
  latest_regime_label: z.string().optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceFuturesResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  contract_month: z.string().optional(),
  exchange: z.string().optional(),
  session_state: z.string().optional(),
  snapshot_count: z.number().optional(),
  latest_imbalance_ratio: z.number().optional(),
  latest_imbalance_signal: z.string().optional(),
  latest_ofi_value: z.number().optional(),
  provenance: z.string().optional(),
  synthetic: z.boolean().optional(),
  snapshot: z.record(z.unknown()).optional(),
  snapshots: z.array(WorkspaceFuturesSnapshotSchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const WorkspaceDisclosureEventSchema = z.object({
  accession_number: z.string().optional(),
  accepted_at: z.string().optional(),
  filer: z.string().optional(),
  form_type: z.string().optional(),
  is_amendment: z.boolean().optional(),
  issuer: z.string().optional(),
  transaction_code: z.string().optional(),
  source_url: z.string().optional(),
});

export const WorkspaceDisclosureResponseSchema = z.object({
  symbol: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  disclaimer: z.string().optional(),
  research_only: z.boolean().optional(),
  disclosure_lag_note: z.string().optional(),
  event_count: z.number().optional(),
  events: z.array(WorkspaceDisclosureEventSchema).optional(),
  provider_id: z.string().optional(),
  ledger_id: z.string().optional(),
  as_of_context: AsOfContextSchema.optional(),
});

export const InstitutionalFlowFamilySchema = z.object({
  family_id: z.string(),
  label: z.string(),
  entitled_symbol: z.string(),
  route_path: z.string(),
  available: z.boolean(),
  reason: z.string().nullable().optional(),
  explanation_ref: z.string(),
});

export const WorkspaceInstitutionalFlowResponseSchema = z.object({
  symbol: z.string(),
  family_count: z.number(),
  available_family_count: z.number(),
  disclaimer: z.string().optional(),
  epistemic_class: z.string().optional(),
  research_only: z.boolean().optional(),
  families: z.array(InstitutionalFlowFamilySchema),
  as_of_context: AsOfContextSchema.optional(),
  capability_states: z.array(CapabilityStateSchema).optional(),
});

export const ResearchModelsResponseSchema = z.object({
  authority_boundary: z.string(),
  disclaimer: z.string().optional(),
  epistemic_class: z.string().optional(),
  walk_forward_fold_count: z.number(),
  preregistration_status: z.string().optional(),
  model_summary: z.record(z.unknown()),
  strategy_spec: z.record(z.unknown()),
  dataset_manifest: z.record(z.unknown()),
  preregistration: z.record(z.unknown()),
  interpretation_summary: z.object({
    abstention_count: z.number(),
    signal_count: z.number(),
    total_at_cutoff: z.number(),
  }),
  interpretations: z.array(z.record(z.unknown())),
  as_of_context: AsOfContextSchema.optional(),
  capability_states: z.array(CapabilityStateSchema).optional(),
});

export const ResearchSimulationResponseSchema = z.object({
  authority_boundary: z.string(),
  mode_label: z.string(),
  disclaimer: z.string().optional(),
  epistemic_class: z.string().optional(),
  risk_policy_id: z.string().nullable().optional(),
  ledger_summary: z.object({
    cash_minor: z.number().nullable().optional(),
    position_shares: z.number().nullable().optional(),
    realized_pnl_minor: z.number().nullable().optional(),
    entry_count: z.number(),
  }),
  risk_decisions: z.array(z.record(z.unknown())),
  fills: z.array(z.record(z.unknown())),
  orders: z.array(z.record(z.unknown())),
  intents: z.array(z.record(z.unknown())),
  attributions: z.array(z.record(z.unknown())),
  reconciliation: z.record(z.unknown()),
  fill_audit: z.record(z.unknown()).optional(),
  as_of_context: AsOfContextSchema.optional(),
  capability_states: z.array(CapabilityStateSchema).optional(),
});

export type ResearchAnalyticsResponse = z.infer<typeof ResearchAnalyticsResponseSchema>;
export type AsOfContext = z.infer<typeof AsOfContextSchema>;
export type AttentionItem = z.infer<typeof AttentionItemSchema>;
export type ExploreSqueezeResponse = z.infer<typeof ExploreSqueezeResponseSchema>;
export type ExploreFuturesResponse = z.infer<typeof ExploreFuturesResponseSchema>;
export type ExploreCatalystResponse = z.infer<typeof ExploreCatalystResponseSchema>;
export type WorkspaceSqueezeResponse = z.infer<typeof WorkspaceSqueezeResponseSchema>;
export type WorkspaceOrderFlowResponse = z.infer<typeof WorkspaceOrderFlowResponseSchema>;
export type WorkspaceOptionsResponse = z.infer<typeof WorkspaceOptionsResponseSchema>;
export type WorkspaceLargeTransactionsResponse = z.infer<typeof WorkspaceLargeTransactionsResponseSchema>;
export type WorkspaceOrderBookResponse = z.infer<typeof WorkspaceOrderBookResponseSchema>;
export type WorkspaceFuturesResponse = z.infer<typeof WorkspaceFuturesResponseSchema>;
export type WorkspaceCatalystResponse = z.infer<typeof WorkspaceCatalystResponseSchema>;
export type WorkspaceFundEtfResponse = z.infer<typeof WorkspaceFundEtfResponseSchema>;
export type WorkspaceDisclosureResponse = z.infer<typeof WorkspaceDisclosureResponseSchema>;
export type WorkspaceInstitutionalFlowResponse = z.infer<typeof WorkspaceInstitutionalFlowResponseSchema>;
export type ResearchModelsResponse = z.infer<typeof ResearchModelsResponseSchema>;
export type ResearchSimulationResponse = z.infer<typeof ResearchSimulationResponseSchema>;
export type ReplaySession = z.infer<typeof ReplaySessionSchema>;

export const ADMITTED_REPLAY_INSTRUMENT_ID = "BIYA";
export const ADMITTED_ORDER_FLOW_INSTRUMENT_ID = "NVDA";
export const ADMITTED_FUTURES_INSTRUMENT_ID = "ES";
export const ADMITTED_CATALYST_INSTRUMENT_ID = "BOXL";
export const ADMITTED_FUND_ETF_INSTRUMENT_ID = "NVDA";
export const FROZEN_DEMO_REFERENCE_SYMBOL = "AVTX";

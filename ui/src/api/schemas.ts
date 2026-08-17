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
  manifest: z.record(z.unknown()).nullable().optional(),
  header: z.record(z.unknown()).nullable().optional(),
});

export const WorkspaceSqueezeResponseSchema = z.object({
  symbol: z.string(),
  source: z.string(),
  bridge_mode: z.string(),
  donor_base_url: z.string().optional(),
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
    })
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
      }),
    )
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

export type ResearchAnalyticsResponse = z.infer<typeof ResearchAnalyticsResponseSchema>;
export type AsOfContext = z.infer<typeof AsOfContextSchema>;
export type AttentionItem = z.infer<typeof AttentionItemSchema>;
export type ExploreSqueezeResponse = z.infer<typeof ExploreSqueezeResponseSchema>;
export type WorkspaceSqueezeResponse = z.infer<typeof WorkspaceSqueezeResponseSchema>;
export type WorkspaceOrderFlowResponse = z.infer<typeof WorkspaceOrderFlowResponseSchema>;
export type WorkspaceOptionsResponse = z.infer<typeof WorkspaceOptionsResponseSchema>;
export type ReplaySession = z.infer<typeof ReplaySessionSchema>;

export const ADMITTED_REPLAY_INSTRUMENT_ID = "BIYA";
export const ADMITTED_ORDER_FLOW_INSTRUMENT_ID = "NVDA";
export const FROZEN_DEMO_REFERENCE_SYMBOL = "AVTX";

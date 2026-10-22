import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";

const Numeric = z.union([z.string(), z.number()]).nullable();
export const MetricsSchema = z.object({
  decisions:z.number(), signal_outcomes:z.number(), completed_trades:z.number(), open_censored:z.number(), unavailable:z.number(),
  wins:z.number(), losses:z.number(), flat:z.number(), win_rate:Numeric, net_pnl_minor:Numeric, gross_pnl_minor:Numeric,
  average_win_minor:Numeric, average_loss_minor:Numeric, median_win_minor:Numeric, median_loss_minor:Numeric,
  expectancy_minor:Numeric, profit_factor:Numeric, profit_factor_status:z.string(), costs_minor:Numeric,
  longest_losing_streak:z.number(), current_losing_streak:z.number(), executed_notional_minor:z.number(),
  exposure_seconds:Numeric, time_in_market_fraction:Numeric,
  average_gross_notional_to_equity:Numeric, peak_gross_notional_to_equity:Numeric,
  turnover:Numeric.optional(), turnover_reference_equity_minor:Numeric.optional(), payoff_ratio:Numeric,
  signal_market_return_mean:Numeric,signal_directional_return_mean:Numeric,
}).passthrough();
const DrawdownSchema=z.object({amount_minor:z.number(),fraction:Numeric,start:z.string().nullable(),trough:z.string().nullable(),
  recovered_at:z.string().nullable(),duration_seconds:Numeric}).nullable();
export const EvaluationRecordSchema=z.object({evaluation_id:z.string(),instrument_id:z.string(),action_state:z.string(),
  evidence_class:z.string(),decision_time:z.string().optional(),origin:z.string(),trade_episode_id:z.string().nullable().optional(),
  model:z.record(z.unknown()).optional(),segments:z.record(z.string()).optional(),
  execution_outcome:z.object({state:z.string(),net_pnl_minor:Numeric,gross_pnl_minor:Numeric,costs_minor:Numeric,
    entry_time:z.string().nullable(),exit_time:z.string().nullable()}).passthrough().nullable().optional(),
  excluded_reason:z.string().nullable().optional(),signal_outcomes:z.array(z.record(z.unknown())),limitations:z.array(z.string()),
}).passthrough();
export const EvaluationSummarySchema=z.object({schema_version:z.literal("prospective-evaluation-run/1.0.0"),run_id:z.string(),
  cutoff:z.string(),git_sha:z.string(),metric_definition_version:z.string(),evaluation_policy_id:z.string(),input_fingerprint:z.string(),
  evidence_class:z.string(),currency:z.literal("USD"),metrics:MetricsSchema,
  admission:z.object({total_considered:z.number(),admitted:z.number(),excluded:z.number(),reasons:z.record(z.number())}),
  portfolio_metrics:z.object({snapshot_count:z.number(),resolution:z.string(),drawdown:DrawdownSchema,
    starting_equity_minor:Numeric,ending_equity_minor:Numeric,observed_equity_return:Numeric}).passthrough(),
  segments:z.record(z.array(z.object({label:z.string(),metrics:MetricsSchema}))),
  weekly:z.array(z.object({week:z.string(),metrics:MetricsSchema,observed_start_equity_minor:Numeric,
    observed_end_equity_minor:Numeric,return_fraction:Numeric,drawdown:DrawdownSchema,coverage:z.string()})),
  review:z.array(z.string()),conclusion:z.string(),limitations:z.array(z.string()),finalized:z.boolean().optional(),
  authority:z.object({live_capital:z.literal(false),trading_mutation:z.literal(false),model_promotion:z.literal(false),ftep_activation:z.literal(false)}),
}).passthrough();
export type EvaluationSummary=z.infer<typeof EvaluationSummarySchema>;
export type EvaluationRecord=z.infer<typeof EvaluationRecordSchema>;
export type EvaluationMetrics=z.infer<typeof MetricsSchema>;
const PageSchema=z.object({records:z.array(EvaluationRecordSchema),total_count:z.number(),next_offset:z.number().nullable(),cutoff:z.string(),run_id:z.string()});
const DetailSchema=z.object({record:EvaluationRecordSchema,decision:z.record(z.unknown()).nullable(),source_reconstruction:z.string(),lifecycle_id:z.string().nullable(),cutoff:z.string()});
const RunListSchema=z.object({runs:z.array(z.object({run_id:z.string(),cutoff:z.string(),evidence_class:z.string()}).passthrough())});
const RerunSchema=z.object({status:z.enum(["MATCH","DIFFERENT","NOT_REPRODUCIBLE"]),source_reconstruction:z.string(),missing_or_changed_sources:z.array(z.string())}).passthrough();
export const evaluationApi={
  summary:(params:URLSearchParams)=>fetchJson(`/evaluation/prospective/summary?${params}`,EvaluationSummarySchema),
  records:(params:URLSearchParams)=>fetchJson(`/evaluation/prospective/records?${params}`,PageSchema),
  detail:(params:URLSearchParams)=>fetchJson(`/evaluation/prospective/detail?${params}`,DetailSchema),
  runs:()=>fetchJson('/evaluation/prospective/runs',RunListSchema),
  finalize:(cutoff:string,evidence_class:string)=>postJson('/evaluation/prospective/runs',{cutoff,evidence_class},EvaluationSummarySchema),
  rerun:(run_id:string)=>postJson('/evaluation/prospective/rerun',{run_id},RerunSchema),
};

import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
const Position = z.object({ state: z.enum(["FLAT", "LONG", "SHORT"]), quantity: z.number(), snapshot_at: z.string().nullable(), account_id: z.string(), session_id: z.string() }).passthrough();
const Condition = z.object({ condition_id: z.string(), status: z.enum(["MET", "NOT_MET"]), source: z.string(), source_value: z.union([z.number(), z.string()]).nullable().optional(), as_of: z.string().nullable().optional(), evidence_refs: z.array(z.string()), valid_until: z.string().nullable() }).passthrough();
const Evidence = z.object({ evidence_id: z.string(), capability: z.string(), source: z.string().nullable().optional(), as_of: z.string().nullable(), valid_until: z.string().nullable(), facts: z.record(z.unknown()) }).passthrough();
export const ActionDecisionSchema = z.object({ schema_version: z.literal("action-decision/1.0.0"), decision_id: z.string(), instrument_id: z.string(),
  action_state: z.enum(["NO_ACTION", "CONSIDER_ENTRY", "ENTER", "HOLD", "EXIT", "REVALIDATION_REQUIRED"]), direction: z.enum(["LONG", "SHORT"]).nullable(),
  decision_time: z.string(), valid_until: z.string(), previous_state: z.string().nullable(), previous_decision_id: z.string().nullable(),
  rationale: z.string(), position: Position, execution_readiness: z.enum(["NOT_PREVIEWED", "PREVIEW_ALLOWED", "BLOCKED"]),
  blocker_codes: z.array(z.string()), supporting_refs: z.array(z.string()), conflicting_refs: z.array(z.string()), weak_refs: z.array(z.string()), missing_capabilities: z.array(z.string()),
  model: z.object({ provider_id: z.string().nullable(), model_id: z.string().nullable(), prompt_id: z.string(), prompt_hash: z.string() }).passthrough(),
  entry_plan: z.array(Condition), hold_plan: z.array(Condition), exit_plan: z.array(Condition), reference_quote: Condition.nullable(),
  evidence_snapshot_id: z.string(), evidence_snapshot: z.object({ cutoff: z.string(), evidence: z.object({ current_market_evidence: z.array(Evidence), reference_evidence: z.array(Evidence) }).passthrough() }).passthrough(),
  decision_trace_id: z.string(), opportunity_id: z.string().nullable(), risk_decision_ref: z.unknown().nullable(), paper_preview_ref: z.unknown().nullable(),
  model_proposal: z.object({ uncertainties: z.array(z.string()) }).passthrough().nullable(),
}).passthrough();
export type ActionDecision = z.infer<typeof ActionDecisionSchema>;
const PreviewSchema = z.object({ schema_version: z.literal("action-preview/1.0.0"), decision_cutoff: z.string(), candidate_valid_until: z.string(), candidate_current: z.boolean(),
  paper_authority: z.boolean(), position: Position, opportunity_id: z.string().nullable(), provider_id: z.string().nullable(), model_id: z.string().nullable(), conditions: z.array(Condition),
  available_opportunities: z.array(z.object({ opportunity_id: z.string(), direction: z.string() })) }).passthrough();
export type ActionPreview = z.infer<typeof PreviewSchema>;
const DraftSchema = z.object({ version: z.literal(1), instrumentId: z.string(), side: z.enum(["BUY", "SELL"]), quantity: z.number().int().positive(), orderType: z.literal("MARKET"), sourceAttentionId: z.string(), sourceContext: z.object({ headline: z.string(), source_time: z.number(), reasons: z.array(z.object({ code: z.string(), label: z.string() })) }) });
export const previewAction = (run_id: string, instrument_id: string, signal?: AbortSignal, opportunity_id?: string) => postJson("/screener/action-decision/preview", { run_id, instrument_id, ...(opportunity_id ? { opportunity_id } : {}) }, PreviewSchema, { signal });
export const runAction = (run_id: string, instrument_id: string, signal?: AbortSignal, opportunity_id?: string) => postJson("/screener/action-decision/run", { run_id, instrument_id, ...(opportunity_id ? { opportunity_id } : {}) }, ActionDecisionSchema, { signal });
export const actionHistory = (instrument: string, signal?: AbortSignal) => fetchJson(`/screener/action-decisions?instrument=${encodeURIComponent(instrument)}`, z.object({ decisions: z.array(ActionDecisionSchema) }), { signal });
export const prepareAction = (decision_id: string, signal?: AbortSignal) => postJson("/screener/action-decision/handoff", { decision_id }, DraftSchema, { signal });

import { z } from "zod";
import { fetchJson } from "./fetchJson";
import type { ScreenerFilter, ScreenerUniverse } from "./screener";

const NumberValue = z.number().finite();
const NullableClock = z.string().nullable();
const State = z.enum(["BASELINE", "VULNERABLE", "ARMED", "IGNITION_WATCH", "LIVE_CONFIRMATION",
  "ACTIVE_SQUEEZE", "EXHAUSTION", "POST_SQUEEZE", "UNEVALUABLE"]);
const Clock = z.object({ kind: z.enum(["SNAPSHOT", "PUBLICATION", "DAILY_LIST", "STREAMING", "PROVIDER"]), as_of: NullableClock }).strict();
const Metric = z.object({
  id: z.string().min(1), label: z.string(), value: z.union([NumberValue, z.boolean(), z.string()]).nullable(),
  unit: z.string(), source: z.string(), source_label: z.string(), quality: z.string(), clock: Clock,
  reason: z.string().nullable(), note: z.string().nullable(), detail: z.record(z.unknown()),
}).strict();
export type SqueezeMetric = z.infer<typeof Metric>;
const Evidence = z.object({
  code: z.string(), label: z.string(), class: z.enum(["SHORT_CROWDING", "SECURITIES_LENDING", "IGNITION", "CATALYST",
    "ORDER_FLOW", "OPTIONS_AMPLIFICATION", "REGULATORY_CONTEXT"]),
  polarity: z.enum(["SUPPORTS", "CONTRADICTS", "CONTEXT"]), strength: z.enum(["LOW", "MODERATE", "HIGH"]),
  source: z.string(), detail: z.string(),
}).strict();
const Rule = z.object({
  rule_id: z.string(), class: Evidence.shape.class, outcome: z.enum(["PASS", "FAIL", "UNKNOWN"]),
  observed: NumberValue.nullable(), threshold: NumberValue, operator: z.enum(["gt", "gte", "lte"]),
  threshold_source: z.string(), source: z.string(),
}).strict();
const Assessment = z.object({
  model: z.string(), adapted_from: z.string(), rule_policy: z.string(), state: State,
  state_basis: z.literal("SNAPSHOT_ASSESSMENT"), trigger: z.string(), transition: z.null(),
  hysteresis: z.literal("NOT_APPLIED_NO_STATE_HISTORY"),
  lifecycle: z.array(z.object({ state: State.exclude(["UNEVALUABLE"]), current: z.boolean(), reachable: z.boolean(),
    unreachable_reason: z.string().nullable() }).strict()),
  rules: z.array(Rule), supporting: z.array(Evidence), contradicting: z.array(Evidence), context: z.array(Evidence),
  missing: z.array(z.string()), mechanism_labels: z.array(z.string()), quality_flags: z.array(z.string()),
  classes_supporting: z.array(z.string()), probability: z.null(), score: z.null(),
}).strict().superRefine((assessment, context) => {
  if (assessment.lifecycle.some((item) => (item.current && !item.reachable) || item.current !== (item.state === assessment.state) ||
    (!item.reachable && !item.unreachable_reason))) context.addIssue({ code: "custom", message: "SQUEEZE_LIFECYCLE_INVALID" });
});
const WhyListed = z.object({ state: z.enum(["NO_ACTIVE_FILTERS", "MATCHED", "NOT_MATCHED"]), items: z.array(z.object({
  filter_id: z.string(), field: z.string(), label: z.string(), operator: z.string(),
  value: z.union([NumberValue, z.string(), z.array(NumberValue), z.array(z.string())]),
  observed: z.union([NumberValue, z.string()]).nullable(), passed: z.boolean(), missing: z.boolean(), text: z.string(),
}).strict()) }).strict();
export const SqueezeSchema = z.object({
  schema_version: z.literal("screener-squeeze/1.0.0"), generated_at: z.string(),
  instrument_id: z.string().min(1), universe: z.literal("US_EQUITIES"), symbol: z.string().min(1),
  company: z.string().nullable(), view: z.enum(["summary", "detail"]), market_session: z.string(),
  capability: z.record(z.string()), assessment: Assessment,
  source_state: z.enum(["INSUFFICIENT_EVIDENCE", "PARTIAL", "COMPLETE"]),
  sections: z.object({ structural_pressure: z.array(Metric), ignition: z.array(Metric), live_confirmation: z.array(Metric),
    exhaustion: z.object({ evidence: z.array(Evidence), temporal: z.literal("NOT_EVALUATED_NO_STATE_HISTORY"), note: z.string() }).strict() }).strict(),
  headlines: z.array(z.unknown()), evidence: z.object({ supporting: z.array(Evidence), conflicting: z.array(Evidence),
    context: z.array(Evidence), missing: z.array(z.object({ code: z.string(), label: z.string(), reason: z.string().nullable() }).strict()) }).strict(),
  coverage: z.object({ supporting: z.number().int().nonnegative(), conflicting: z.number().int().nonnegative(),
    unavailable: z.number().int().nonnegative(), stale: z.number().int().nonnegative(), pending: z.number().int().nonnegative() }).strict(),
  sources: z.array(z.object({ id: z.string(), label: z.string(), state: z.string(), clock_kind: Clock.shape.kind,
    as_of: NullableClock, reason: z.string().nullable() }).strict()),
  why_listed: WhyListed,
  discovery_thresholds: z.record(z.object({ value: NumberValue, operator: z.enum(["gt", "gte", "lte"]), source: z.string() }).strict()),
  historical_context: z.null(), disclaimer: z.string(),
}).strict();
export type SqueezePayload = z.infer<typeof SqueezeSchema>;
export type SqueezeView = "summary" | "detail";

export async function fetchScreenerSqueeze(instrumentId: string, { universe, view, filters = [], signal }:
  { universe: ScreenerUniverse; view: SqueezeView; filters?: ScreenerFilter[]; signal?: AbortSignal }) {
  const query = new URLSearchParams({ instrument: instrumentId, universe, view });
  if (filters.length) query.set("filters", JSON.stringify(filters));
  const payload = await fetchJson(`/screener/squeeze?${query}`, SqueezeSchema, { signal });
  if (payload.instrument_id !== instrumentId || payload.universe !== universe || payload.view !== view)
    throw new Error("SQUEEZE_IDENTITY_MISMATCH");
  return payload;
}

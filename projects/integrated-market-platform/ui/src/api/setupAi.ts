import { z } from "zod";
import { fetchJson } from "./fetchJson";
import { SynthesisEngineSchema } from "./screenerNews";

/**
 * Setup's "Which AI decides" card: the machine-wide engine, the paid AI dollar caps, today's and this month's
 * spend, pinned list prices and the benchmark summary. Read-only; never carries a key. The engine is changed with
 * `postSynthesisEngine` and the caps with `saveProviderSettings("paid_ai", ...)`.
 */
const CapSetting = z.object({ source: z.enum(["ENVIRONMENT", "PRIVATE_FILE", "ENV_FILE", "NONE"]), editable: z.boolean() }).passthrough();
const Spend = z.object({
  state: z.string(), reason: z.string().nullable().optional(),
  spent_today_usd: z.number().optional(), spent_month_usd: z.number().optional(),
  daily_cap_usd: z.number(), monthly_cap_usd: z.number(),
}).passthrough();
const Price = z.object({
  engine: z.string(), model: z.string(), priced: z.boolean(),
  input_per_mtok: z.number().nullable(), output_per_mtok: z.number().nullable(),
}).passthrough();
const BenchmarkRun = z.object({
  engine: z.string(), model: z.string(), skipped: z.boolean(), reason: z.string().nullable().optional(),
  start_reason: z.string().nullable().optional(), cases: z.number().nullable().optional(),
  accepted_pct: z.number().nullable().optional(), p50_latency_ms: z.number().nullable().optional(),
  dollars_per_case: z.number().nullable().optional(),
}).passthrough();
const Benchmark = z.object({
  generated_at: z.string(), local_winner: z.string(), paid_pick: z.string(), runs: z.array(BenchmarkRun),
}).passthrough();

export const SetupAiSchema = z.object({
  schema_version: z.literal("setup-ai/1.0.0"),
  engine: z.string(), resolved_engine: z.string(), model: z.string().nullable(),
  source: z.enum(["OPERATOR", "ENVIRONMENT", "AUTOMATIC"]),
  engines: z.array(SynthesisEngineSchema),
  caps: z.object({ daily_usd: z.number(), monthly_usd: z.number(), set: z.boolean(),
    settings: z.object({ IMP_PAID_AI_DAILY_USD: CapSetting, IMP_PAID_AI_MONTHLY_USD: CapSetting }) }).passthrough(),
  spend: Spend,
  prices: z.array(Price),
  benchmark: Benchmark.nullable(),
  engine_lock: z.object({ locked: z.boolean(), reason: z.string().nullable() }),
  secrets_included: z.literal(false),
}).passthrough();
export type SetupAi = z.infer<typeof SetupAiSchema>;

export const SETUP_AI_QUERY_KEY = ["screener-setup-ai"] as const;

export function fetchSetupAi(signal?: AbortSignal) {
  return fetchJson("/screener/setup/ai", SetupAiSchema, signal ? { signal } : undefined);
}

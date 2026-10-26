import { z } from "zod";
import { fetchJson, postJson } from "./fetchJson";
import { authHeaders } from "../auth/session";

const RunSchema = z.object({
  run_id: z.string(), experiment_id: z.string(), first_session: z.string(),
  fixed_10: z.string(), fixed_20: z.string(),
}).passthrough();
const MilestoneSchema = z.object({
  clock: z.enum(["fixed", "covered"]), day: z.union([z.literal(10), z.literal(20)]),
  status: z.enum(["Not due", "Pass", "Fail", "Cannot determine"]),
  session_date: z.string().nullable(), equity_minor: z.number().nullable(),
  completed_trades: z.number(), conditions: z.record(z.boolean().nullable()),
  reasons: z.array(z.string()), supplemental: z.boolean(),
}).passthrough();
const SessionSchema = z.object({
  session_date: z.string(), cutoff_ns: z.number(), covered: z.boolean(),
  equity_minor: z.number().nullable(), ledger_equity_minor: z.number().nullable(),
  spy_equity_minor: z.string().nullable(), completed_trades: z.number(),
  reasons: z.array(z.string()), mixed: z.boolean().optional(),
  coverage: z.object({ reasons: z.array(z.string()), observations: z.number(),
    gaps: z.array(z.object({ start_ns: z.number(), end_ns: z.number(), seconds: z.number() })),
  }).passthrough(),
  costs: z.object({ commission_minor: z.number(), fees_minor: z.number(),
    posted_borrow_minor: z.number(), unposted_borrow_minor: z.number() }),
}).passthrough();
export const PerformanceReportSchema = z.object({
  schema_version: z.literal("paper-performance/1.0.0"), report_id: z.string(), run_id: z.string(),
  experiment_id: z.string(), account_id: z.string(), currency: z.literal("USD"),
  initial_capital_minor: z.number(), first_session: z.string(), fixed_sessions: z.number(),
  covered_sessions: z.number(), complete: z.boolean(), sessions: z.array(SessionSchema),
  milestones: z.object({ fixed_10: MilestoneSchema, fixed_20: MilestoneSchema,
    covered_10: MilestoneSchema, covered_20: MilestoneSchema }),
  assumptions: z.array(z.string()), calendar_version: z.string(), configuration: z.record(z.unknown()),
  authority: z.object({ trading_mutation: z.literal(false), live_capital: z.literal(false) }),
});
export type PerformanceReport = z.infer<typeof PerformanceReportSchema>;
const ResponseSchema = z.object({ run: RunSchema, report: PerformanceReportSchema,
  durability: z.string(), last_observation_ns: z.number().nullable() });
const base = "/evaluation/paper-performance/runs";
export const performanceApi = {
  list: () => fetchJson(base, z.object({ runs: z.array(RunSchema) })),
  read: (runId: string) => fetchJson(base + "/" + encodeURIComponent(runId), ResponseSchema),
  enroll: (experimentId: string) => postJson(base, { experiment_id: experimentId }, RunSchema),
  refreshBenchmark: (runId: string) => postJson(base + "/" + encodeURIComponent(runId) + "/refresh-benchmark", {},
    z.object({ queued: z.literal(true), refresh_id: z.string(), sessions: z.number() })),
  async download(runId: string, reportId: string, format: "html" | "csv") {
    const params = new URLSearchParams({ format, report_id: reportId });
    const response = await fetch(base + "/" + encodeURIComponent(runId) + "/export?" + params,
      { headers: authHeaders() });
    if (!response.ok) throw new Error("The saved report could not be downloaded.");
    return response.blob();
  },
};

import { describe, expect, it } from "vitest";
import { SmaStopConfigSchema, SmaStopEvaluationSchema, SmaStopStatusSchema } from "../../api/paperRiskControl";
import { buildPaperTrailingStopModel, formatStopPrice, formatStopTime } from "./buildPaperTrailingStopModel";
import { breachedStatus, evaluationReceipt, stopConfig, stopStatus } from "./stopFixtures";

const row = (model: ReturnType<typeof buildPaperTrailingStopModel>, id: string) => model.rows.find((item) => item.id === id);

describe("SMA trailing-stop view model", () => {
  it("fixtures match the server schemas", () => {
    expect(SmaStopStatusSchema.safeParse(stopStatus()).success).toBe(true);
    expect(SmaStopStatusSchema.safeParse(breachedStatus()).success).toBe(true);
    expect(SmaStopConfigSchema.safeParse(stopConfig).success).toBe(true);
    expect(SmaStopEvaluationSchema.safeParse(evaluationReceipt).success).toBe(true);
    expect(SmaStopEvaluationSchema.safeParse({ schema_version: "sma-stop-evaluation/1.0.0", result_status: "NOT_EXECUTED", reason_codes: ["EVALUATION_RECEIPT_NOT_FOUND"] }).success).toBe(true);
    expect(SmaStopStatusSchema.safeParse({ ...stopStatus(), paper_close: "SUBMITTED" }).success).toBe(false);
  });

  it("formats server prices and times without recomputing them", () => {
    expect(formatStopPrice("186.1")).toBe("$186.10");
    expect(formatStopPrice("185")).toBe("$185.00");
    expect(formatStopPrice("184.7300")).toBe("$184.7300");
    expect(formatStopPrice(null)).toBe("Unavailable");
    expect(formatStopTime("2026-10-05T14:42:00Z")).toBe("2026-10-05 10:42:00 ET");
    expect(formatStopTime(null)).toBe("Unavailable");
  });

  it("shows an active long stop with policy, SMA, levels, distance and monitoring", () => {
    const model = buildPaperTrailingStopModel(stopStatus());
    expect(model.statusLabel).toBe("Active");
    expect(model.directionLabel).toBe("LONG stop");
    expect(row(model, "position")?.value).toBe("LONG 7");
    expect(row(model, "window")).toMatchObject({ value: "20 completed 1m bars", detail: "reference test configuration — not optimized" });
    expect(row(model, "sma")?.value).toBe("$184.7300");
    expect(row(model, "candidate")?.value).toBe("$184.73");
    expect(row(model, "active")).toMatchObject({ value: "$185.12", detail: "LONG stop" });
    expect(row(model, "previous")?.value).toBe("$184.90");
    expect(row(model, "distance")?.value).toBe("$2.28 (121.7 bps)");
    expect(row(model, "updated")?.value).toBe("2026-10-05 10:40:00 ET");
    expect(row(model, "monitoring")?.value).toBe("RUNNING");
    expect(model.messages).toContain("Stop held at previous level — trailing rule does not loosen protection.");
    expect(model.breach).toBeNull();
    expect(model.canEvaluate).toBe(true);
  });

  it("labels a short stop in words", () => {
    const model = buildPaperTrailingStopModel(stopStatus({ position: { state: "SHORT", quantity: 7 }, reason_codes: [] }, { side: "SHORT" }));
    expect(model.directionLabel).toBe("SHORT stop");
    expect(row(model, "active")?.detail).toBe("SHORT stop");
    expect(row(model, "position")?.value).toBe("SHORT 7");
  });

  it("says not configured, warming up, stale, blocked and closed in text", () => {
    const off = buildPaperTrailingStopModel(stopStatus({ status: "NOT_CONFIGURED", reason_codes: ["STOP_NOT_CONFIGURED"], policy: null, monitoring: undefined }, null));
    expect(off.messages[0]).toMatch(/No SMA trailing stop is configured/);
    expect(off.canEvaluate).toBe(false);
    const warming = buildPaperTrailingStopModel(stopStatus({ status: "WARMING_UP", reason_codes: ["INSUFFICIENT_HISTORY"] },
      { active_stop: null, candidate_stop: null, sma_value: null, previous_stop: null, bars_available: 12, distance_to_stop: null, distance_bps: null }));
    expect(warming.messages).toContain("Warming up — 20 completed bars required; 12 available. No stop exists yet.");
    expect(row(warming, "active")?.value).toBe("Unavailable");
    const stale = buildPaperTrailingStopModel(stopStatus({ status: "STALE", reason_codes: ["STOP_UPDATE_STALE", "STALE_BAR_SOURCE"] }));
    expect(stale.statusLabel).toBe("Stop update stale");
    expect(stale.messages).toContain("Stop update stale — last legitimate stop $185.12, last bar 2026-10-05 10:42:00 ET. Reason: STALE_BAR_SOURCE.");
    const blocked = buildPaperTrailingStopModel(stopStatus({ status: "BLOCKED", reason_codes: ["OPEND_UNAVAILABLE"] }, { active_stop: null }));
    expect(blocked.messages).toContain("Stop cannot be computed: OPEND_UNAVAILABLE. No stop is in force.");
    const closed = buildPaperTrailingStopModel(stopStatus({ status: "CLOSED", reason_codes: ["POSITION_FLAT"], position: { state: "FLAT", quantity: 0 } }, { closed_reason: "POSITION_FLAT" }));
    expect(closed.messages).toContain("Stop episode closed: POSITION_FLAT.");
    expect(closed.canEvaluate).toBe(false);
  });

  it("separates an unresolved trigger, late activation and unobserved time from a breach", () => {
    const unresolved = buildPaperTrailingStopModel(stopStatus({ reason_codes: [] }, { trigger_state: "TRIGGER_UNAVAILABLE", trigger_reason_codes: ["REVALIDATION_REQUIRED", "FEED_SILENT"], activation_reason: "LATE_ACTIVATION" }));
    expect(unresolved.breach).toBeNull();
    expect(unresolved.messages.join(" ")).toMatch(/Trigger unavailable — revalidation required \(FEED_SILENT\)\. The stop is neither confirmed breached nor confirmed safe\./);
    expect(unresolved.messages.join(" ")).toMatch(/Late activation — this stop began 2026-10-05 10:20:00 ET, not at position entry\./);
    const gap = buildPaperTrailingStopModel(stopStatus({ monitoring: { state: "NOT_RUNNING", worker_state: "STOPPED", last_evaluated_at: "2026-10-05T13:00:00Z", liveness: "NOT_OBSERVED" } }));
    expect(row(gap, "monitoring")?.value).toBe("NOT RUNNING");
    expect(gap.messages.join(" ")).toMatch(/Not observed — the stop was not evaluated for an interval\. No protection is claimed/);
  });

  it("presents a breach with an EXIT decision and an unsubmitted Paper close", () => {
    const model = buildPaperTrailingStopModel(breachedStatus());
    expect(model.statusLabel).toBe("SMA stop breached");
    expect(model.breach).toEqual({ stop: "$186.10", trigger: "$185.95", observedAt: "2026-10-05 10:45:00 ET", decision: "EXIT", decisionId: "AD-exit",
      paperClose: "NOT SUBMITTED", canPrepareExit: true, blockers: [] });
    const blocked = buildPaperTrailingStopModel(breachedStatus({ decision_id: "AD-exit", action_state: "EXIT", execution_readiness: "BLOCKED", blocker_codes: ["PENDING_ORDER_REVALIDATION"], decision_time: "t" }));
    expect(blocked.breach).toMatchObject({ canPrepareExit: false, blockers: ["PENDING_ORDER_REVALIDATION"] });
    const undecided = buildPaperTrailingStopModel({ ...breachedStatus(null), exit_decision_error: "STOP_EXIT_EVIDENCE_UNAVAILABLE" });
    expect(undecided.breach).toMatchObject({ decision: "EXIT decision not yet recorded", decisionId: null, canPrepareExit: false });
    expect(undecided.messages.join(" ")).toMatch(/EXIT decision could not be written: STOP_EXIT_EVIDENCE_UNAVAILABLE/);
  });
});

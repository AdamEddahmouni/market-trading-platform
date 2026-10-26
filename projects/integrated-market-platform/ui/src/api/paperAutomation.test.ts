import { describe, expect, it } from "vitest";
import { PaperAutomationStatusSchema } from "./paperAutomation";

const status = {
  schema_version: "paper-automation-status/1.0.0", status: "RUNNING", status_label: "Running",
  required_configuration: [], arm_acknowledgement: "ack", durability: "PERSISTED", evaluated_at: "2026-10-05T19:52:00Z",
  session: { label: "REGULAR", trading_day: true, session_date: "2026-10-05", minutes_to_close: 8 },
  boundary: { execution: "INTERNAL_PAPER_SIMULATION_ONLY", live_capital: false, real_money_order_routes: "UNREACHABLE",
    execution_mode: "INTERNAL_SIMULATION", execution_provider: "INTERNAL" },
};
const cycle = { cycle_id: "cycle", scheduled_for: "2026-10-05T19:52:00Z", error: null, blockers: [],
  missed_cycles_before: 0, reevaluation: null };
describe("automation close-out status contract", () => {
  for (const decision_id of [null, undefined]) {
    it(`accepts a close-out with ${String(decision_id)} decision ID and a string quantity`, () => {
      const result = PaperAutomationStatusSchema.parse({ ...status, last_cycle: { ...cycle, actions: [
        { decision_id, instrument_id: "AAPL", action: "EOD_FLATTEN", outcome: "SUBMITTED",
          reason_codes: [], quantity: "6", filled_quantity: 6 },
      ] } });
      expect(result.last_cycle?.actions[0].quantity).toBe("6");
    });
  }
  it("preserves approved and unplanned carry status", () => {
    const result = PaperAutomationStatusSchema.parse({ ...status,
      carry: { session_date: "2026-10-05", approved: { AAPL: { quantity: 6 } }, pending: { NVDA: { quantity: -2 } } } });
    expect(Object.keys(result.carry?.pending ?? {})).toEqual(["NVDA"]);
  });
});

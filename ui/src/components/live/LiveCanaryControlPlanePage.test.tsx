import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { LiveCanaryControlPlanePage } from "./LiveCanaryControlPlanePage";

const snapshotPayload = {
  snapshot: {
    live_blocked: true,
    block_reasons: ["PROGRAM_KILL_SWITCH"],
    execution_mode_label: "LIVE_CANARY",
    program_state: "PROGRAM_ACTIVE",
    session_state: "SESSION_PREPARED",
    broker: "tradier.paper",
    account_environment: "LIVE",
    account_fingerprint: "ACCTFP-test",
    broker_health: "HEALTHY",
    reconciliation_health: "CLEAN",
    kill_switch_global: "ACTIVE_BLOCK",
    kill_switch_program: "ACTIVE_BLOCK",
    kill_switch_session: "INACTIVE",
    authorization_status: null,
    authorization_expires_at_ns: null,
    program_cap_remaining: { sessions: 3, orders: 3, notional_minor: 7500 },
    incident_summary: { open: 0, critical_open: 0 },
    unresolved_critical_incidents: [],
    allowed_next_actions: ["ACTIVATE_KILL_SWITCH"],
    action_queue: [],
    snapshot_id: "OPSNA-test",
    as_of_ns: 1,
  },
  real_money_warning: "LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED",
};

describe("LiveCanaryControlPlanePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => snapshotPayload,
      }),
    );
  });

  it("renders without submitting orders", async () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <LiveCanaryControlPlanePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId("live-canary-control-plane")).toBeInTheDocument();
    expect(screen.getByText(/REAL MONEY/i)).toBeInTheDocument();
    expect(screen.getByText(/PAPER — INTERNAL SIMULATION ONLY/i)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/canary/snapshot");
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.every((call) => String(call[0]).includes("/canary/orders") === false)).toBe(true);
  });
});

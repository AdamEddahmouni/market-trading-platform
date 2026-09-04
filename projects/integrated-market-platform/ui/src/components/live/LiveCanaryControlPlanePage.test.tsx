import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Mode } from "../mode-session/types";
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

const reliabilityPayload = {
  observability_state: "OBSERVABILITY_HEALTHY",
  as_of_ns: 1,
  health_matrix: {
    entries: [],
    blocking_dependencies: [],
  },
  slo_summary: {
    overall_status: "HEALTHY",
    objectives: [],
  },
  persistence_health: {
    disposition: "HEALTHY",
    blocking_live: false,
  },
  backup_status: {
    integrity_status: "VERIFIED",
    last_backup_id: "BACKUP-test",
  },
  alert_delivery_configured: true,
};

describe("LiveCanaryControlPlanePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (path: string) => ({
        ok: true,
        json: async () =>
          path.includes("/canary/reliability") ? reliabilityPayload : snapshotPayload,
      })),
    );
  });

  it.each(["DEMO", "PAPER", "LIVE"] as const)(
    "keeps %s canary observability read-only",
    async (mode: Mode) => {
      const client = new QueryClient();
      render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <LiveCanaryControlPlanePage mode={mode} />
          </MemoryRouter>
        </QueryClientProvider>,
      );
      expect(await screen.findByTestId("live-canary-control-plane")).toBeInTheDocument();
      expect(screen.getByText(/REAL MONEY/i)).toBeInTheDocument();
      expect(screen.getByText(/PAPER — INTERNAL SIMULATION ONLY/i)).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Safety State" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Incidents" })).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /Operational Reliability/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(new RegExp(`${mode} workstation.*read-only`, "i")),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Activate program kill switch" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Prepare session authorization preview" }),
      ).not.toBeInTheDocument();
      expect(fetch).toHaveBeenCalledWith("/canary/snapshot?account_id=fp-canary-local");
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(
        calls.every((call) => (call[1] as RequestInit | undefined)?.method !== "POST"),
      ).toBe(true);
    },
  );
});

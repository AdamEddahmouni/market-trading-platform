import { describe, expect, it } from "vitest";
import type { OperatorLifecycleStatus, ProviderReadiness } from "../../api/schemas";
import {
  applyUpdateAction,
  checkUpdateAction,
  providerConfigSaveAction,
  providerRefreshAction,
  restartPlatformAction,
} from "./controlOperatorActions";

const ready: OperatorLifecycleStatus = {
  status: "RUNNING",
  update: { status: "CURRENT", detail: "Local branch is current." },
};

describe("control operator actions", () => {
  it("keeps restart unavailable until lifecycle status loads", () => {
    const action = restartPlatformAction({ loading: true, failed: false });
    expect(action.availability).toBe("UNAVAILABLE");
    expect(action.reason?.code).toBe("LIFECYCLE_STATUS_UNAVAILABLE");
    expect(action.domain).toBe("platform.lifecycle");
  });

  it("requires confirmation before restarting a known runtime", () => {
    const action = restartPlatformAction({ loading: false, failed: false, lifecycle: ready });
    expect(action.availability).toBe("AVAILABLE");
    expect(action.confirmation?.confirmLabel).toBe("Confirm restart");
    expect(action.confirmation?.facts.map((fact) => fact.label)).toEqual([
      "What will change",
      "Target",
      "Current runtime",
      "Unchanged",
    ]);
  });

  it("blocks apply-update when the snapshot says current", () => {
    const action = applyUpdateAction({ loading: false, failed: false, lifecycle: ready });
    expect(action.availability).toBe("BLOCKED");
    expect(action.reason?.code).toBe("UPDATE_NOT_AVAILABLE");
    expect(action.confirmation).toBeUndefined();
  });

  it("confirms apply-update only when the backend says an update is available", () => {
    const action = applyUpdateAction({
      loading: false,
      failed: false,
      lifecycle: { status: "RUNNING", update: { status: "AVAILABLE", detail: "2 commits behind." } },
    });
    expect(action.availability).toBe("AVAILABLE");
    expect(action.confirmation?.confirmLabel).toBe("Confirm apply and restart");
    expect(action.confirmation?.facts.some((fact) => fact.value.includes("2 commits behind"))).toBe(true);
  });

  it("preserves an unknown update status instead of inventing availability", () => {
    const action = applyUpdateAction({
      loading: false,
      failed: false,
      lifecycle: { status: "RUNNING", update: { status: "WHATEVER" } },
    });
    expect(action.availability).toBe("UNAVAILABLE");
    expect(action.reason?.code).toBe("WHATEVER");
  });

  it("marks update check unavailable when lifecycle failed to load", () => {
    const action = checkUpdateAction({ loading: false, failed: true });
    expect(action.availability).toBe("UNAVAILABLE");
    expect(action.reason?.detail).toMatch(/could not be loaded/);
  });

  it("does not put provider secrets on a configuration submit descriptor", () => {
    const action = providerConfigSaveAction("Finviz discovery");
    expect(JSON.stringify(action)).not.toMatch(/API|token|secret|password/i);
    expect(action.domain).toBe("platform.configuration");
  });

  it("offers provider refresh without a generic execute command", () => {
    const provider = {
      provider: "moomoo_observational",
      label: "Moomoo observational",
      credential_state: "NOT_REQUIRED",
      gate_state: "ENABLED",
      transport_state: "REACHABLE",
      next_action: "Confirm OpenD",
    } satisfies ProviderReadiness;
    const action = providerRefreshAction(provider);
    expect(action.domain).toBe("platform.provider");
    expect(action.availability).toBe("AVAILABLE");
    expect(action).not.toHaveProperty("endpoint");
    expect(action.confirmation).toBeUndefined();
  });
});

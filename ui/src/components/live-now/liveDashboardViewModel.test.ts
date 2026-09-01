import { describe, expect, it } from "vitest";
import { canarySnapshot, providerHealth } from "./liveNowTestFixtures";
import {
  channelHealthLabel,
  liveConnectionMetrics,
  liveSafetyAlerts,
  liveSafetySummary,
} from "./liveDashboardViewModel";

describe("live dashboard view model", () => {
  it("labels channel health from entitlement and runtime test state", () => {
    expect(channelHealthLabel(false, false)).toBe("UNAVAILABLE");
    expect(channelHealthLabel(true, false)).toBe("DEGRADED");
    expect(channelHealthLabel(true, true)).toBe("HEALTHY");
  });

  it("returns unavailable connection metrics when observational mode is disabled", () => {
    expect(liveConnectionMetrics(providerHealth({ available: false, reason: "disabled" }))[0]).toEqual({
      id: "observational",
      label: "Observational mode",
      value: "UNAVAILABLE",
      detail: "disabled",
    });
  });

  it("derives truthful provider metrics when observational mode is available", () => {
    const metrics = liveConnectionMetrics(providerHealth());
    expect(metrics.find((metric) => metric.id === "connection")?.value).toBe("CONNECTED");
    expect(metrics.find((metric) => metric.id === "quota")?.value).toBe("2 / 50");
    expect(metrics.find((metric) => metric.id === "execution")?.value).toBe("DISPLAY_ONLY");
  });

  it("builds safety summary and caps explicit alerts", () => {
    const snapshot = canarySnapshot({
      live_blocked: true,
      block_reasons: ["HUMAN_CONFIRMATION_REQUIRED"],
      kill_switch_global: "ACTIVE",
      incident_summary: { open: 2, critical_open: 1 },
      unresolved_critical_incidents: ["incident-1", "incident-2"],
    });
    expect(liveSafetySummary(snapshot).find((metric) => metric.id === "live-blocked")?.value).toBe("YES");
    expect(liveSafetyAlerts(snapshot).length).toBeLessThanOrEqual(5);
    expect(liveSafetyAlerts(snapshot)[0]?.title).toBe("Live execution blocked");
  });
});

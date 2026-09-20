import { describe, expect, it } from "vitest";
import type { OperatorReadiness, ProviderReadiness } from "../../api/schemas";
import {
  CONTROL_SECTIONS,
  authoritySummary,
  buildAttentionItems,
  controlSectionHref,
  partitionProviders,
    presentProviderRole,
    presentProviderTransport,
    providerNeedsAction,
    isLiveClockWithheldFeed,
} from "./controlPresentation";

function provider(overrides: Partial<ProviderReadiness>): ProviderReadiness {
  return {
    provider: "p",
    credential_state: "NOT_REQUIRED",
    gate_state: "DISABLED",
    transport_state: "IMPLEMENTED",
    next_action: "No action required.",
    ...overrides,
  };
}

function readiness(overrides: Partial<OperatorReadiness>): OperatorReadiness {
  return { status: "READY", checks: [], providers: [], ...overrides };
}

describe("presentProviderRole", () => {
  it("translates known backend roles into capability and impact language", () => {
    const primary = presentProviderRole("primary_observational_market_data");
    expect(primary?.capability).toContain("market data");
    expect(primary?.impact).toContain("Live quotes");
    const discovery = presentProviderRole("discovery");
    expect(discovery?.impact).toContain("opportunity feed");
  });

  it("humanizes unknown roles mechanically without inventing impact", () => {
    const unknown = presentProviderRole("future_role_x");
    expect(unknown?.capability).toBe("Future role x");
    expect(unknown?.impact).toBe("");
  });

  it("returns null when the role is absent", () => {
    expect(presentProviderRole(undefined)).toBeNull();
  });
});

describe("presentProviderTransport", () => {
  it("does not treat enabled-gate UNAVAILABLE as a subscription gap", () => {
    const state = presentProviderTransport(
      provider({ gate_state: "ENABLED", transport_state: "UNAVAILABLE" }),
    );
    expect(state.label).toBe("Transport unavailable");
    expect(state.tone).toBe("caution");
    expect(state.raw).toBe("UNAVAILABLE");
    expect(state.sentence).toMatch(/not a data-subscription gap/i);
    expect(state.label).not.toMatch(/subscription/i);
  });

  it("keeps configured-gate UNAVAILABLE as a transport fact", () => {
    const state = presentProviderTransport(
      provider({ gate_state: "CONFIGURED", transport_state: "UNAVAILABLE" }),
    );
    expect(state.label).toBe("Transport unavailable");
  });

  it("does not treat off-by-configuration UNAVAILABLE as a live transport failure", () => {
    const state = presentProviderTransport(
      provider({ gate_state: "DISABLED", transport_state: "UNAVAILABLE" }),
    );
    expect(state.label).toBe("Unavailable");
    expect(state.tone).toBe("neutral");
    expect(state.sentence).toMatch(/off by configuration/i);
    expect(state.sentence).not.toMatch(/subscription/i);
  });

  it("leaves other transport tokens on the shared adapter", () => {
    const reachable = presentProviderTransport(
      provider({ gate_state: "ENABLED", transport_state: "REACHABLE" }),
    );
    expect(reachable.label).toBe("Reachable");
    expect(reachable.tone).toBe("live");
  });

  it("keeps entitlement gaps on the shared adapter vocabulary", () => {
    const state = presentProviderTransport(
      provider({ gate_state: "ENABLED", transport_state: "ENTITLEMENT_MISSING" }),
    );
    expect(state.label).not.toBe("Transport unavailable");
    expect(state.label).toMatch(/subscription/i);
  });
});

describe("providerNeedsAction", () => {
  it("flags enabled gates with unavailable or blocked transport (backend rule)", () => {
    expect(
      providerNeedsAction(
        provider({ gate_state: "ENABLED", transport_state: "UNAVAILABLE" }),
      ),
    ).toBe(true);
    expect(
      providerNeedsAction(
        provider({ gate_state: "ENABLED", transport_state: "BLOCKED_NON_LOOPBACK" }),
      ),
    ).toBe(true);
  });

  it("flags enabled gates with missing credentials", () => {
    expect(
      providerNeedsAction(
        provider({ gate_state: "ENABLED", credential_state: "MISSING" }),
      ),
    ).toBe(true);
  });

  it("does not flag disabled gates or healthy enabled providers", () => {
    expect(
      providerNeedsAction(
        provider({ gate_state: "DISABLED", transport_state: "UNAVAILABLE" }),
      ),
    ).toBe(false);
    expect(
      providerNeedsAction(
        provider({ gate_state: "ENABLED", transport_state: "REACHABLE" }),
      ),
    ).toBe(false);
  });
});

describe("partitionProviders", () => {
  it("splits attention / active / inactive without inventing state", () => {
    const groups = partitionProviders([
      provider({ provider: "a", gate_state: "ENABLED", transport_state: "UNAVAILABLE" }),
      provider({ provider: "b", gate_state: "ENABLED", transport_state: "REACHABLE" }),
      provider({ provider: "c", gate_state: "DISABLED" }),
      provider({ provider: "d", gate_state: "OPTIONAL" }),
    ]);
    expect(groups.attention.map((p) => p.provider)).toEqual(["a"]);
    expect(groups.active.map((p) => p.provider)).toEqual(["b"]);
    expect(groups.inactive.map((p) => p.provider)).toEqual(["c", "d"]);
  });
});

describe("buildAttentionItems", () => {
  const base = {
    mode: "DEMO" as const,
    contextState: "ready" as const,
    evaluation: { status: "compatible" as const, paperActionsPermitted: false, actualSummary: "" },
    readiness: readiness({}),
    lifecycleStatus: "READY",
    feedStatus: "READY",
  };

  it("returns no items when everything is healthy", () => {
    expect(buildAttentionItems(base)).toEqual([]);
  });

  it("surfaces required failing checks as critical with the backend next action", () => {
    const items = buildAttentionItems({
      ...base,
      readiness: readiness({
        status: "ACTION_REQUIRED",
        checks: [
          {
            id: "python",
            label: "Python 3.11",
            status: "FAIL",
            detail: "Detected Python 3.12.",
            required: true,
            next_action: "Install CPython 3.11 and run setup again.",
          },
        ],
      }),
    });
    expect(items[0]).toMatchObject({ tone: "critical", title: "Python 3.11" });
    expect(items[0]?.detail).toContain("Install CPython 3.11");
  });

  it("ignores optional non-pass checks (not operator work)", () => {
    const items = buildAttentionItems({
      ...base,
      readiness: readiness({
        checks: [
          {
            id: "git",
            label: "Git",
            status: "OPTIONAL",
            detail: "Git is unavailable.",
            required: false,
          },
        ],
      }),
    });
    expect(items).toEqual([]);
  });

  it("surfaces providers needing action with a link to the provider section", () => {
    const items = buildAttentionItems({
      ...base,
      readiness: readiness({
        providers: [
          provider({
            provider: "moomoo_observational",
            label: "Moomoo observational",
            gate_state: "ENABLED",
            transport_state: "UNAVAILABLE",
            next_action: "Start OpenD",
          }),
        ],
      }),
    });
    const item = items.find((entry) => entry.id === "provider-moomoo_observational");
    expect(item).toMatchObject({ tone: "caution", title: "Moomoo observational needs attention" });
    expect(item?.action?.href).toBe(`/control#${CONTROL_SECTIONS.providers}`);
  });

  it("treats a non-live UNAVAILABLE feed as critical but Live as by-design", () => {
    const paper = buildAttentionItems({ ...base, mode: "PAPER", feedStatus: "UNAVAILABLE" });
    expect(paper.find((entry) => entry.id === "feed-unavailable")?.tone).toBe("critical");
    const live = buildAttentionItems({ ...base, mode: "LIVE", feedStatus: "UNAVAILABLE" });
    expect(live.find((entry) => entry.id === "feed-unavailable")).toBeUndefined();
  });

  it("does not treat live-clock withheld UNREADY as a radar repair item", () => {
    expect(
      isLiveClockWithheldFeed({
        feedStatus: "UNREADY",
        feedUnreadyReason: "LIVE_AS_OF_UNAVAILABLE",
      }),
    ).toBe(true);
    const items = buildAttentionItems({
      ...base,
      mode: "LIVE",
      feedStatus: "UNREADY",
      feedUnreadyReason: "LIVE_AS_OF_UNAVAILABLE",
      humanizedUnreadyReason: "the live clock is unavailable",
    });
    expect(items.find((entry) => entry.id === "feed-unready")).toBeUndefined();
  });

  it("still treats ordinary UNREADY as caution attention", () => {
    const items = buildAttentionItems({
      ...base,
      feedStatus: "UNREADY",
      humanizedUnreadyReason: "Provider warmup",
    });
    const item = items.find((entry) => entry.id === "feed-unready");
    expect(item?.tone).toBe("caution");
    expect(item?.detail).toContain("Provider warmup");
  });

  it("fails closed when the backend context is unavailable", () => {
    const items = buildAttentionItems({ ...base, contextState: "error", evaluation: undefined });
    expect(items.find((entry) => entry.id === "context-unavailable")).toMatchObject({
      tone: "caution",
    });
  });

  it("surfaces mode mismatch as critical", () => {
    const items = buildAttentionItems({
      ...base,
      evaluation: { status: "mismatch", paperActionsPermitted: false, actualSummary: "DATA X" },
    });
    expect(items.find((entry) => entry.id === "context-mismatch")?.tone).toBe("critical");
  });

  it("surfaces a missing paper session only in Paper mode", () => {
    const paper = buildAttentionItems({ ...base, mode: "PAPER", paperSessionOpen: false });
    expect(paper.find((entry) => entry.id === "paper-session-closed")?.action?.href).toBe(
      "/portfolio",
    );
    const demo = buildAttentionItems({ ...base, mode: "DEMO", paperSessionOpen: false });
    expect(demo.find((entry) => entry.id === "paper-session-closed")).toBeUndefined();
  });

  it("surfaces a failed lifecycle endpoint honestly", () => {
    const items = buildAttentionItems({ ...base, lifecycleStatus: undefined, lifecycleError: true });
    expect(items.find((entry) => entry.id === "lifecycle-unavailable")?.tone).toBe("caution");
  });

  it("orders critical items before caution items", () => {
    const items = buildAttentionItems({
      ...base,
      lifecycleStatus: "PARTIAL",
      evaluation: { status: "mismatch", paperActionsPermitted: false, actualSummary: "" },
    });
    expect(items[0]?.tone).toBe("critical");
    expect(items[1]?.tone).toBe("caution");
  });
});

describe("authoritySummary", () => {
  const compatible = {
    status: "compatible" as const,
    paperActionsPermitted: false,
    actualSummary: "",
  };

  it("fails closed while the context is loading or unavailable", () => {
    expect(authoritySummary("PAPER", "loading", undefined)).toContain("Verifying");
    expect(authoritySummary("PAPER", "error", undefined)).toContain("locked");
  });

  it("never implies live execution", () => {
    expect(authoritySummary("LIVE", "ready", compatible)).toContain("execution stays locked");
    expect(authoritySummary("DEMO", "ready", compatible)).toContain("read-only");
    expect(authoritySummary("PAPER", "ready", compatible)).toContain("Paper orders");
  });

  it("explains mismatch without implying authority change", () => {
    expect(
      authoritySummary("LIVE", "ready", {
        status: "mismatch",
        paperActionsPermitted: false,
        actualSummary: "",
      }),
    ).toContain("does not change backend authority");
  });
});

describe("controlSectionHref", () => {
  it("builds stable section deep-links", () => {
    expect(controlSectionHref("feed")).toBe("/control#control-feed");
    expect(controlSectionHref("authority")).toBe("/control#control-authority");
  });
});

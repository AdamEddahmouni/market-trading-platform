import { describe, expect, it } from "vitest";
import { humanizeEnum, resolveSemanticState, SEMANTIC_TONE_ICON } from "./semanticState";

describe("resolveSemanticState", () => {
  describe("mode domain", () => {
    it("maps UI modes to human sentences with tones", () => {
      expect(resolveSemanticState("mode", "DEMO")).toMatchObject({
        tone: "replay",
        label: "Demo replay",
        raw: "DEMO",
      });
      expect(resolveSemanticState("mode", "PAPER").sentence).toContain("simulated fills");
      expect(resolveSemanticState("mode", "LIVE").sentence).toContain("read-only");
    });

    it("maps backend mode labels", () => {
      expect(resolveSemanticState("mode", "REPLAY").tone).toBe("replay");
      expect(resolveSemanticState("mode", "SIMULATION").tone).toBe("paper");
    });

    it("maps alignment states", () => {
      expect(resolveSemanticState("mode", "compatible").tone).toBe("live");
      expect(resolveSemanticState("mode", "mismatch").tone).toBe("critical");
      expect(resolveSemanticState("mode", "unavailable").action?.href).toBe(
        "/control#control-authority",
      );
    });
  });

  describe("session domain", () => {
    it("maps data modes", () => {
      expect(resolveSemanticState("session", "FIXTURE_REPLAY").label).toBe(
        "Demo replay (recorded data)",
      );
      expect(resolveSemanticState("session", "HISTORICAL_CAPTURE").tone).toBe("replay");
      expect(
        resolveSemanticState("session", "LIVE_OBSERVATIONAL", { params: { provider: "Moomoo" } })
          .label,
      ).toBe("Live market data · Moomoo");
      expect(resolveSemanticState("session", "BROKER_DELAYED").tone).toBe("caution");
    });

    it("falls back when interpolation params are missing", () => {
      expect(resolveSemanticState("session", "LIVE_OBSERVATIONAL").label).toBe("Live market data");
    });

    it("maps crash recovery states with 3-question content", () => {
      const recovered = resolveSemanticState("session", "OPEN_SESSION_DETECTED");
      expect(recovered.tone).toBe("caution");
      expect(recovered.sentence).toContain("No action needed");
      const corrupt = resolveSemanticState("session", "CORRUPT_DB");
      expect(corrupt.tone).toBe("critical");
      expect(corrupt.action?.href).toBe("/settings");
    });
  });

  describe("executionAuthority domain", () => {
    it("maps authority triple values", () => {
      expect(resolveSemanticState("executionAuthority", "NONE").label).toBe("No execution");
      expect(resolveSemanticState("executionAuthority", "INTERNAL_SIMULATION").tone).toBe("paper");
      expect(resolveSemanticState("executionAuthority", "PAPER_ONLY").label).toBe(
        "Paper orders only",
      );
      expect(resolveSemanticState("executionAuthority", "BLOCKED").label).toBe(
        "No trading authority",
      );
      expect(resolveSemanticState("executionAuthority", "AUTHORIZED").tone).toBe("caution");
      expect(resolveSemanticState("executionAuthority", "LIVE").tone).toBe("critical");
    });

    it("maps preview/revalidation states", () => {
      expect(resolveSemanticState("executionAuthority", "PREVIEW_REQUIRED").tone).toBe("critical");
      expect(resolveSemanticState("executionAuthority", "PREVIEW_EXPIRED").tone).toBe("caution");
      expect(resolveSemanticState("executionAuthority", "PREVIEW_INTENT_MISMATCH").tone).toBe(
        "critical",
      );
      expect(resolveSemanticState("executionAuthority", "ACCEPTED").tone).toBe("live");
      expect(resolveSemanticState("executionAuthority", "AUTHORITY_UNAVAILABLE").label).toContain(
        "ticket locked",
      );
    });
  });

  describe("providerHealth domain", () => {
    it("maps connection states with provider interpolation", () => {
      expect(
        resolveSemanticState("providerHealth", "CONNECTED", { params: { provider: "Moomoo" } })
          .label,
      ).toBe("Moomoo — connected");
      expect(resolveSemanticState("providerHealth", "CONNECTED_DEGRADED").tone).toBe("caution");
      expect(resolveSemanticState("providerHealth", "DISCONNECTED").tone).toBe("critical");
      expect(resolveSemanticState("providerHealth", "ENTITLEMENT_MISSING").tone).toBe("neutral");
    });
  });

  describe("dataHealth domain", () => {
    it("maps both quality vocabularies", () => {
      expect(resolveSemanticState("dataHealth", "GOOD").tone).toBe("live");
      expect(resolveSemanticState("dataHealth", "PASS").tone).toBe("live");
      expect(resolveSemanticState("dataHealth", "PARTIAL").tone).toBe("caution");
      expect(resolveSemanticState("dataHealth", "DEGRADED").tone).toBe("caution");
      expect(resolveSemanticState("dataHealth", "STALE").sentence).toContain("delayed");
      expect(resolveSemanticState("dataHealth", "UNAVAILABLE").tone).toBe("critical");
      expect(resolveSemanticState("dataHealth", "DISCONNECTED").tone).toBe("critical");
      expect(resolveSemanticState("dataHealth", "RESTORED").tone).toBe("caution");
    });

    it("maps discover data_status and OE freshness vocabularies", () => {
      expect(resolveSemanticState("dataHealth", "LIVE").label).toBe("Live");
      expect(resolveSemanticState("dataHealth", "DELAYED").tone).toBe("caution");
      expect(resolveSemanticState("dataHealth", "SNAPSHOT").label).toContain("Snapshot");
      expect(resolveSemanticState("dataHealth", "FRESH").tone).toBe("live");
      expect(resolveSemanticState("dataHealth", "NOT_APPLICABLE").tone).toBe("neutral");
    });
  });

  describe("portfolio domain", () => {
    it("maps order states", () => {
      expect(resolveSemanticState("portfolio", "FILLED").tone).toBe("live");
      expect(resolveSemanticState("portfolio", "CANCELLED").tone).toBe("neutral");
      expect(resolveSemanticState("portfolio", "RISK_REJECTED").label).toBe(
        "Rejected by risk controls",
      );
    });

    it("resolves reconciliation and kill-switch rule sets", () => {
      expect(resolveSemanticState("portfolio", "INTERNAL_AUTHORITATIVE").label).toBe("Reconciled");
      expect(resolveSemanticState("portfolio", "OFF").label).toBe("Kill switch: off");
      expect(resolveSemanticState("portfolio", "ON").tone).toBe("critical");
      expect(resolveSemanticState("portfolio", "RISK_BLOCKED").tone).toBe("critical");
    });
  });

  describe("research domain", () => {
    it("maps epistemic classes", () => {
      expect(resolveSemanticState("research", "OBSERVED").label).toBe("From provider data");
      expect(resolveSemanticState("research", "DERIVED").label).toBe("Calculated by IMP");
      expect(resolveSemanticState("research", "INFERRED").tone).toBe("caution");
    });

    it("maps opportunity feed states with 3-question content", () => {
      expect(resolveSemanticState("research", "READY").label).toBe("Radar ready");
      const unready = resolveSemanticState("research", "UNREADY", {
        params: { reason: "provider warmup" },
      });
      expect(unready.tone).toBe("caution");
      expect(unready.sentence).toContain("provider warmup");
      expect(unready.action?.href).toBe("/control#control-feed");
      expect(resolveSemanticState("research", "EMPTY").tone).toBe("neutral");
      expect(resolveSemanticState("research", "UNAVAILABLE").tone).toBe("critical");
    });

    it("maps opportunity action and eligibility values", () => {
      expect(resolveSemanticState("research", "OPEN_WORKSPACE").label).toBe("Open workspace");
      expect(resolveSemanticState("research", "STOP").tone).toBe("critical");
      expect(resolveSemanticState("research", "NONE").label).toBe("No action");
      expect(resolveSemanticState("research", "INELIGIBLE").label).toBe("Not eligible");
      expect(resolveSemanticState("research", "NORMALIZED_AWAITING_FORECAST").tone).toBe(
        "caution",
      );
    });
  });

  describe("platform domain", () => {
    it("maps lifecycle aggregate states", () => {
      expect(resolveSemanticState("platform", "READY")).toMatchObject({
        tone: "live",
        label: "Ready",
      });
      expect(resolveSemanticState("platform", "PARTIAL")).toMatchObject({
        tone: "caution",
        label: "Partially running",
      });
      expect(resolveSemanticState("platform", "STOPPED").tone).toBe("neutral");
    });

    it("maps setup readiness and check states", () => {
      expect(resolveSemanticState("platform", "ACTION_REQUIRED")).toMatchObject({
        tone: "caution",
        label: "Action required",
      });
      expect(resolveSemanticState("platform", "PASS").tone).toBe("live");
      expect(resolveSemanticState("platform", "FAIL").tone).toBe("critical");
      expect(resolveSemanticState("platform", "OPTIONAL").tone).toBe("neutral");
    });

    it("maps update states", () => {
      expect(resolveSemanticState("platform", "AVAILABLE").label).toBe("Update available");
      expect(resolveSemanticState("platform", "CURRENT").label).toBe("Up to date");
      expect(resolveSemanticState("platform", "UNAVAILABLE").tone).toBe("neutral");
    });

    it("maps the shared BLOCKED value critically (readiness and update)", () => {
      // collect_preflight emits BLOCKED when required checks fail — never caution.
      expect(resolveSemanticState("platform", "BLOCKED")).toMatchObject({
        tone: "critical",
        label: "Blocked",
      });
    });

    it("renders unknown platform values neutral with raw preserved", () => {
      const state = resolveSemanticState("platform", "DEGRADED_FUTURE");
      expect(state.tone).toBe("neutral");
      expect(state.raw).toBe("DEGRADED_FUTURE");
    });
  });

  describe("providerHealth transport and credential gaps", () => {
    it("maps IMPLEMENTED transport variants to available", () => {
      for (const raw of ["IMPLEMENTED", "IMPLEMENTED_READ_ONLY", "IMPLEMENTED_PUBLIC", "IMPLEMENTED_OPTIONAL"]) {
        expect(resolveSemanticState("providerHealth", raw).tone).toBe("live");
      }
      expect(resolveSemanticState("providerHealth", "REACHABLE").tone).toBe("live");
      expect(resolveSemanticState("providerHealth", "NOT_CHECKED").tone).toBe("neutral");
      expect(resolveSemanticState("providerHealth", "HTTPS_PAPER_HOST").tone).toBe("paper");
    });

    it("maps interactive brokerage credential states", () => {
      expect(
        resolveSemanticState("providerHealth", "CREDENTIAL_FILE_PRESENT_MANUAL_LOGIN_REQUIRED").tone,
      ).toBe("caution");
      expect(resolveSemanticState("providerHealth", "MANUAL_SESSION_REQUIRED").tone).toBe(
        "caution",
      );
    });
  });

  describe("error domain", () => {
    it("maps the twelve canonical error categories", () => {
      expect(resolveSemanticState("error", "STALE_DATA").tone).toBe("caution");
      expect(resolveSemanticState("error", "RATE_LIMITED").tone).toBe("caution");
      expect(resolveSemanticState("error", "TIMEOUT").tone).toBe("caution");
      expect(resolveSemanticState("error", "VALIDATION_ERROR").tone).toBe("neutral");
      expect(resolveSemanticState("error", "RISK_BLOCKED").label).toBe(
        "Risk controls blocked this order",
      );
      expect(resolveSemanticState("error", "PROVIDER_UNAVAILABLE").tone).toBe("critical");
      expect(resolveSemanticState("error", "INTERNAL_ERROR").tone).toBe("critical");
    });
  });

  describe("unknown and empty values", () => {
    it("renders unknown values neutral with the raw string preserved", () => {
      const state = resolveSemanticState("dataHealth", "SOME_FUTURE_STATE");
      expect(state.tone).toBe("neutral");
      expect(state.label).toBe("Some future state");
      expect(state.raw).toBe("SOME_FUTURE_STATE");
    });

    it("renders null/undefined/empty as unavailable neutral", () => {
      for (const value of [null, undefined, ""]) {
        const state = resolveSemanticState("mode", value);
        expect(state.tone).toBe("neutral");
        expect(state.label).toBe("Unavailable");
        expect(state.raw).toBe("UNAVAILABLE");
      }
    });

    it("never throws on arbitrary input", () => {
      expect(() => resolveSemanticState("research", "@@@")).not.toThrow();
      expect(() => resolveSemanticState("portfolio", "Working")).not.toThrow();
    });
  });

  describe("humanizeEnum", () => {
    it("humanizes SNAKE_CASE mechanically", () => {
      expect(humanizeEnum("NORMALIZED_AWAITING_FORECAST")).toBe("Normalized awaiting forecast");
      expect(humanizeEnum("")).toBe("Unknown");
    });
  });

  describe("SEMANTIC_TONE_ICON", () => {
    it("provides an icon for every tone", () => {
      for (const tone of ["live", "paper", "replay", "research", "caution", "critical", "neutral"]) {
        expect(SEMANTIC_TONE_ICON[tone as keyof typeof SEMANTIC_TONE_ICON]).toBeTruthy();
      }
    });
  });
});

import type { CapabilityState } from "../../api/schemas";

export type CapabilityTone = "ok" | "warn" | "blocked";

/** Fail-closed: unknown states render as blocked. */
export function capabilityTone(state: string | undefined): CapabilityTone {
  const normalized = (state ?? "").toUpperCase();
  if (["READY", "AVAILABLE", "ENABLED", "AUTHORIZED", "PASS"].includes(normalized)) {
    return "ok";
  }
  if (["DEGRADED", "LIMITED", "PARTIAL", "WARN", "WARNING"].includes(normalized)) {
    return "warn";
  }
  return "blocked";
}

export function formatCapabilityId(capabilityId: string): string {
  return capabilityId.replace(/_/g, " ");
}

export type CapabilityPresentation = {
  capability: CapabilityState;
  tone: CapabilityTone;
  label: string;
};

export function presentCapabilityStates(states: CapabilityState[]): CapabilityPresentation[] {
  return states.map((capability) => ({
    capability,
    tone: capabilityTone(capability.state),
    label: formatCapabilityId(capability.capability_id),
  }));
}

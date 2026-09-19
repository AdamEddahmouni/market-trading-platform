import type { AsOfContext, CapabilityState } from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";

export type GovernanceFact = {
  id: string;
  label: string;
  value: string;
  tone: SemanticTone;
  raw?: string;
  detail?: string;
};

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

function findCapability(
  capabilities: CapabilityState[] | undefined,
  pattern: RegExp,
): CapabilityState | undefined {
  return (capabilities ?? []).find((row) => pattern.test(row.capability_id));
}

/**
 * Operator governance facts derived only from `/context` and readiness passthrough.
 * Never invents Item 9 calibration progress, runtime SHA, or collector state.
 */
export function buildGovernanceFacts(input: {
  asOf?: AsOfContext | null;
  capabilityStates?: CapabilityState[] | null;
  readinessRoot?: string | null;
}): GovernanceFact[] {
  const asOf = input.asOf;
  const capabilities = input.capabilityStates ?? [];

  const liveExecutionOff =
    asOf?.execution_authority !== "AUTHORIZED" || asOf?.execution_mode !== "LIVE";
  const facts: GovernanceFact[] = [
    {
      id: "live-execution",
      label: "Live real-money execution",
      value: liveExecutionOff ? "OFF (governed)" : "Authorized path only",
      tone: liveExecutionOff ? "neutral" : "critical",
      raw: asOf?.execution_authority,
      detail: liveExecutionOff
        ? "LIVE-001 remains blocked; observational Live does not place broker orders."
        : "Execution authority reports AUTHORIZED — still subject to platform gates.",
    },
    {
      id: "runtime-sha",
      label: "Runtime git SHA",
      value: "UNAVAILABLE",
      tone: "neutral",
      detail:
        "Not exposed on operator readiness/context APIs. Use diagnostics receipts or governed collector checkout for empirical SHA pins.",
    },
  ];

  const item9Cap = findCapability(capabilities, /item9|calibration|prospective/i);
  if (item9Cap) {
    const calibrated = /CALIBRATED/i.test(item9Cap.state) && !/NOT_CALIBRATED/i.test(item9Cap.state);
    facts.push({
      id: "item9-calibration",
      label: "Item 9 calibration",
      value: calibrated ? display(item9Cap.state) : display(item9Cap.state),
      tone: calibrated ? "live" : "caution",
      raw: item9Cap.state,
      detail: item9Cap.reason ?? "Capability state from backend context.",
    });
  } else {
    facts.push({
      id: "item9-calibration",
      label: "Item 9 calibration",
      value: "NOT CALIBRATED (status not on API)",
      tone: "caution",
      detail:
        "Corpus sample gates are not projected to the UI yet. Never display 3/3 calibrated without a backend field.",
    });
  }

  const collectorCap = findCapability(capabilities, /collector|frozen/i);
  if (collectorCap) {
    facts.push({
      id: "collector-state",
      label: "Prospective collector",
      value: display(collectorCap.state),
      tone: /READY|CONNECTED/i.test(collectorCap.state) ? "live" : "caution",
      raw: collectorCap.state,
      detail: collectorCap.reason,
    });
  }

  if (input.readinessRoot) {
    facts.push({
      id: "readiness-root",
      label: "Readiness scan root",
      value: input.readinessRoot,
      tone: "neutral",
      detail: "Local workstation path from operator readiness (not empirical receipt SHA).",
    });
  }

  return facts;
}

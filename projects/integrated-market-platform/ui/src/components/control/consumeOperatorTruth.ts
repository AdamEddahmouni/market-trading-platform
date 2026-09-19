import type { OperatorDiagnostics } from "../../api/schemas";
import { operatorTruthById as readOperatorTruthById } from "../../api/operatorTruth";

export { operatorTruthById, operatorTruthSection } from "../../api/operatorTruth";

const ITEM9_TRUTH_IDS = new Set(["item9-corpus", "item9-preflight"]);

/**
 * Item 9 IDLE vs DEGRADED: prefer backend `operator_truth` when present.
 * Calendar-incomplete local IDLE (e.g. 2/3) is never upgraded to DEGRADED.
 * Real gates (BLOCKED) and Live execution stay on Control's local mapping.
 */
export function preferItem9OperatorTruth<T extends string>(
  diagnostics: OperatorDiagnostics | null | undefined,
  id: "item9-corpus" | "item9-preflight",
  local: T,
): T {
  if (!ITEM9_TRUTH_IDS.has(id)) return local;
  const backend = readOperatorTruthById(diagnostics, id);
  if (!backend) return local;
  if (local === "IDLE") return local;
  if (
    (backend === "IDLE" || backend === "DEGRADED") &&
    (local === "DEGRADED" || local === "UNKNOWN")
  ) {
    return backend as T;
  }
  return local;
}

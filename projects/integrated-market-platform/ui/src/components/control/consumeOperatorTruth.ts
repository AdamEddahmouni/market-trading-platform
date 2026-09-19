import type { OperatorDiagnostics, OperatorTruthSection } from "../../api/schemas";

/**
 * Optional reader matching `ui/src/api/operatorTruth.ts` (#298) when that field exists.
 * Control does not import that module so this lane can land before Lane E merges.
 */
export function operatorTruthSection(
  diagnostics: OperatorDiagnostics | null | undefined,
): OperatorTruthSection | undefined {
  if (diagnostics?.operator_truth?.by_id) return diagnostics.operator_truth;
  const nested = diagnostics?.sections?.operator_truth;
  if (nested && typeof nested === "object" && nested !== null && "by_id" in nested) {
    return nested as OperatorTruthSection;
  }
  return undefined;
}

export function operatorTruthById(
  diagnostics: OperatorDiagnostics | null | undefined,
  id: string,
): string | undefined {
  const token = operatorTruthSection(diagnostics)?.by_id?.[id];
  return typeof token === "string" && token.trim() ? token.toUpperCase() : undefined;
}

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
  const backend = operatorTruthById(diagnostics, id);
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

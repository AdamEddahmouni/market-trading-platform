import type { OperatorDiagnostics, OperatorTruthClass, OperatorTruthSection } from "./schemas";

/**
 * Lane B should consume backend-owned operator truth rather than remapping
 * lifecycle/readiness/Item 9 corpus tokens in Control presentation.
 */
export function operatorTruthSection(
  diagnostics: OperatorDiagnostics | null | undefined,
): OperatorTruthSection | undefined {
  if (diagnostics?.operator_truth?.by_id) return diagnostics.operator_truth;
  const nested = diagnostics?.sections?.operator_truth;
  if (nested && typeof nested === "object" && "by_id" in nested) {
    return nested as OperatorTruthSection;
  }
  return undefined;
}

export function operatorTruthById(
  diagnostics: OperatorDiagnostics | null | undefined,
  id: string,
): OperatorTruthClass | undefined {
  return operatorTruthSection(diagnostics)?.by_id?.[id];
}

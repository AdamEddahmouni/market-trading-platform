import type { AsOfContext } from "./schemas";

export type QueryMode = "DEMO" | "PAPER" | "LIVE";

/** Map backend as-of context to UI query mode for cache isolation. */
export function deriveQueryMode(
  context?: Pick<AsOfContext, "mode" | "data_mode" | "execution_mode" | "execution_authority">,
): QueryMode {
  if (!context) return "DEMO";
  if (context.data_mode === "LIVE_OBSERVATIONAL" || context.data_mode === "BROKER_DELAYED") {
    return "LIVE";
  }
  if (
    context.execution_mode === "INTERNAL_SIMULATION" &&
    context.execution_authority === "PAPER_ONLY"
  ) {
    return "PAPER";
  }
  return "DEMO";
}

export type CanonicalQueryDimensions = {
  mode?: QueryMode;
  accountId?: string;
  provider?: string;
  instrumentId?: string;
  capability?: string;
  asOf?: string;
  interval?: string;
  workspace?: string;
  params?: Record<string, string | number | boolean | null | undefined>;
};

function stableParamSegment(params?: CanonicalQueryDimensions["params"]): string {
  if (!params) return "";
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null)
    .sort(([left], [right]) => left.localeCompare(right));
  if (entries.length === 0) return "";
  return entries.map(([key, value]) => `${key}=${String(value)}`).join("&");
}

/** Deterministic canonical query-key segments for G14 converged surfaces. */
export function canonicalQueryKey(
  root: string,
  dimensions: CanonicalQueryDimensions = {},
): readonly string[] {
  const segments: string[] = [root];
  if (dimensions.mode) segments.push("m", dimensions.mode);
  if (dimensions.accountId) segments.push("a", dimensions.accountId);
  if (dimensions.provider) segments.push("p", dimensions.provider);
  if (dimensions.instrumentId) segments.push("i", dimensions.instrumentId);
  if (dimensions.capability) segments.push("c", dimensions.capability);
  if (dimensions.asOf) segments.push("t", dimensions.asOf);
  if (dimensions.interval) segments.push("v", dimensions.interval);
  if (dimensions.workspace) segments.push("w", dimensions.workspace);
  const paramSegment = stableParamSegment(dimensions.params);
  if (paramSegment) segments.push("x", paramSegment);
  return segments as readonly string[];
}

const unbound = (accountId?: string) => accountId ?? "u";

/** Compact workspace lane keys for runtime bundle budget. */
export function workspaceLaneKey(
  lane: string,
  instrumentId: string,
  mode: QueryMode,
  accountId?: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): readonly string[] {
  const paramSegment = stableParamSegment(params);
  return paramSegment
    ? (["ws", lane, instrumentId, mode, unbound(accountId), paramSegment] as const)
    : (["ws", lane, instrumentId, mode, unbound(accountId)] as const);
}

export function optionsProductKey(
  instrumentId: string,
  mode: QueryMode,
  accountId?: string,
  provider = "fixture",
): readonly string[] {
  return ["op", instrumentId, mode, unbound(accountId), provider] as const;
}

export function futuresProductKey(
  instrumentId: string,
  mode: QueryMode,
  accountId?: string,
  provider = "fixture",
): readonly string[] {
  return ["fp", instrumentId, mode, unbound(accountId), provider] as const;
}

export function instrumentSelectorKey(query: string, limit = 25): readonly string[] {
  return ["is", query, String(limit)] as const;
}

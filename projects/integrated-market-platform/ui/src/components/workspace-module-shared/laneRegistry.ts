export const WORKSPACE_LANE_REGISTRY = [
  { id: "overview", label: "Overview", shortTitle: "Overview", routeSuffix: "", navOrder: 0 },
  {
    id: "institutional-flow",
    label: "Institutional Flow",
    shortTitle: "Institutional Flow",
    routeSuffix: "/institutional-flow",
    navOrder: 1,
  },
  { id: "disclosure", label: "Disclosure", shortTitle: "Disclosure", routeSuffix: "/disclosure", navOrder: 2 },
  { id: "squeeze", label: "Short Squeeze", shortTitle: "Squeeze", routeSuffix: "/squeeze", navOrder: 3 },
  { id: "order-flow", label: "Order Flow", shortTitle: "Order Flow", routeSuffix: "/order-flow", navOrder: 4 },
  { id: "order-book", label: "Order Book", shortTitle: "Order Book", routeSuffix: "/order-book", navOrder: 5 },
  { id: "futures", label: "Futures", shortTitle: "Futures", routeSuffix: "/futures", navOrder: 6 },
  { id: "catalyst", label: "Catalyst", shortTitle: "Catalyst", routeSuffix: "/catalyst", navOrder: 7 },
  { id: "fund-etf", label: "Fund / ETF", shortTitle: "Fund / ETF", routeSuffix: "/fund-etf", navOrder: 8 },
  { id: "options", label: "Options", shortTitle: "Options", routeSuffix: "/options", navOrder: 9 },
  {
    id: "large-transactions",
    label: "Large Transactions",
    shortTitle: "Large Transactions",
    routeSuffix: "/large-transactions",
    navOrder: 10,
  },
] as const;

export type WorkspaceModuleId = (typeof WORKSPACE_LANE_REGISTRY)[number]["id"];

/** Lane modules with observability content (excludes workspace overview). */
export type WorkspaceLaneModuleId = Exclude<WorkspaceModuleId, "overview">;

export type LaneRegistryEntry = {
  id: WorkspaceModuleId;
  label: string;
  shortTitle: string;
  routeSuffix: string;
  navOrder: number;
};

export function laneById(id: WorkspaceModuleId): LaneRegistryEntry | undefined {
  return WORKSPACE_LANE_REGISTRY.find((lane) => lane.id === id) as LaneRegistryEntry | undefined;
}

/**
 * Canonical ordered lane-module ids (excludes the workspace overview page).
 *
 * Single source of truth for workspace lane identity: backend Paper provenance
 * (`paper/decision_source.py`) deliberately does NOT enumerate lane modules, and
 * UI paper/evidence surfaces derive their lists and labels from this registry.
 */
export const WORKSPACE_LANE_MODULE_IDS: readonly WorkspaceLaneModuleId[] = WORKSPACE_LANE_REGISTRY.filter(
  (entry) => entry.id !== "overview",
).map((entry) => entry.id) as WorkspaceLaneModuleId[];

/** Canonical display labels for lane modules, derived from the registry. */
export const WORKSPACE_LANE_LABELS: Readonly<Record<WorkspaceLaneModuleId, string>> = Object.fromEntries(
  WORKSPACE_LANE_REGISTRY.filter((entry) => entry.id !== "overview").map((entry) => [entry.id, entry.label]),
) as Readonly<Record<WorkspaceLaneModuleId, string>>;

export function workspaceLanePath(instrumentId: string, laneId: WorkspaceModuleId, squeezeQuery = ""): string {
  const lane = laneById(laneId);
  if (!lane) return `/workspace/${instrumentId}`;
  const suffix = laneId === "squeeze" ? `${lane.routeSuffix}${squeezeQuery}` : lane.routeSuffix;
  return `/workspace/${instrumentId}${suffix}`;
}

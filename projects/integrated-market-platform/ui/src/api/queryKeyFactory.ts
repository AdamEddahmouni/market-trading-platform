import { canonicalQueryKey, type CanonicalQueryDimensions, type QueryMode } from "./canonicalQueryKey";

export type { QueryMode, CanonicalQueryDimensions };
export { deriveQueryMode } from "./canonicalQueryKey";
export {
  canonicalQueryKey,
  futuresProductKey,
  instrumentSelectorKey,
  optionsProductKey,
  workspaceLaneKey,
} from "./canonicalQueryKey";

export const queryKeyFactory = {
  context: () => canonicalQueryKey("context"),
  attention: () => canonicalQueryKey("attention"),
  instrument: (instrumentId: string) => canonicalQueryKey("ins", { instrumentId }),
  exploreSqueeze: () => canonicalQueryKey("explore", { workspace: "squeeze" }),
  exploreSqueezeScanner: () => canonicalQueryKey("explore", { workspace: "squeeze-scanner" }),
  exploreFutures: () => canonicalQueryKey("explore", { workspace: "futures" }),
  exploreCatalyst: () => canonicalQueryKey("explore", { workspace: "catalyst" }),
  workspaceLane: (
    lane: string,
    instrumentId: string,
    mode: QueryMode,
    accountId?: string,
    provider?: string,
    asOf?: string,
    params?: CanonicalQueryDimensions["params"],
  ) =>
    canonicalQueryKey("wl", {
      mode,
      accountId: accountId ?? "unbound",
      provider,
      instrumentId,
      workspace: lane,
      asOf,
      params,
    }),
  workspaceSqueeze: (
    instrumentId: string,
    mode: QueryMode,
    dataMode: "frozen" | "current" = "frozen",
    accountId?: string,
  ) =>
    queryKeyFactory.workspaceLane("squeeze", instrumentId, mode, accountId, undefined, undefined, {
      dataMode,
    }),
  workspaceEvidence: (
    instrumentId: string,
    mode: QueryMode,
    dataMode: "frozen" | "current" = "frozen",
    accountId?: string,
  ) =>
    queryKeyFactory.workspaceLane("evidence", instrumentId, mode, accountId, undefined, undefined, {
      dataMode,
    }),
  replaySession: () => canonicalQueryKey("replay-session"),
  researchAnalytics: () => canonicalQueryKey("research", { workspace: "analytics" }),
  researchModels: () => canonicalQueryKey("research", { workspace: "models" }),
  researchSimulation: () => canonicalQueryKey("research", { workspace: "simulation" }),
  assistantStatus: () => canonicalQueryKey("assistant", { capability: "status" }),
  assistantConversations: () => canonicalQueryKey("assistant", { capability: "conversations" }),
  assistantMessages: (conversationId: string) =>
    canonicalQueryKey("assistant", { instrumentId: conversationId, capability: "messages" }),
  paperPortfolio: (mode: QueryMode, accountId?: string) =>
    canonicalQueryKey("pp", { mode, accountId: accountId ?? "unbound" }),
  paperOrderHistory: (mode: QueryMode, accountId?: string) =>
    canonicalQueryKey("poh", { mode, accountId: accountId ?? "unbound" }),
  paperTrace: (
    mode: QueryMode,
    accountId: string | undefined,
    intentId?: string,
    orderId?: string,
    fillId?: string,
    allocationDecisionId?: string,
  ) =>
    canonicalQueryKey("pt", {
      mode,
      accountId: accountId ?? "unbound",
      params: { intentId, orderId, fillId, allocationDecisionId },
    }),
  paperStrategyProfitability: (mode: QueryMode, accountId?: string, sessionId?: string) =>
    canonicalQueryKey("psp", {
      mode,
      accountId: accountId ?? "unbound",
      params: { sessionId: sessionId ?? "unbound" },
    }),
  liveCanarySnapshot: (laneId?: string, accountId?: string) =>
    canonicalQueryKey("lcs", {
      mode: "LIVE",
      workspace: laneId ?? "account",
      accountId: accountId ?? "fp-canary-local",
    }),
  liveCanaryReconciliation: (accountId?: string) =>
    canonicalQueryKey("lcr", { mode: "LIVE", accountId: accountId ?? "fp-canary-local" }),
  providerHealth: () => canonicalQueryKey("provider", { capability: "health" }),
  symbolSearch: (query: string) =>
    canonicalQueryKey("symbol-search", { capability: "search", params: { q: query } }),
  instrumentSearch: (query: string, limit = 25) =>
    canonicalQueryKey("instrument-search", { capability: "search", params: { q: query, limit } }),
  instrumentSelector: (query: string, limit = 25) =>
    canonicalQueryKey("is", { capability: "selector", params: { q: query, limit } }),
  instrumentCapabilities: (instrumentId: string) =>
    canonicalQueryKey("instrument-capabilities", { instrumentId }),
  marketState: (instrumentId: string) =>
    canonicalQueryKey("market-state", { instrumentId, mode: "LIVE" }),
  optionsProduct: (instrumentId: string, mode: QueryMode, accountId?: string, provider = "fixture") =>
    canonicalQueryKey("op", {
      mode,
      accountId: accountId ?? "unbound",
      provider,
      instrumentId,
      workspace: "options",
    }),
  futuresProduct: (instrumentId: string, mode: QueryMode, accountId?: string, provider = "fixture") =>
    canonicalQueryKey("fp", {
      mode,
      accountId: accountId ?? "unbound",
      provider,
      instrumentId,
      workspace: "futures",
    }),
  paperPreview: (instrumentId: string, mode: QueryMode, accountId?: string) =>
    canonicalQueryKey("ppv", { mode, accountId: accountId ?? "unbound", instrumentId }),
  paperOrders: (instrumentId: string, mode: QueryMode, accountId?: string) =>
    canonicalQueryKey("paper-orders", { mode, accountId: accountId ?? "unbound", instrumentId }),
} as const;

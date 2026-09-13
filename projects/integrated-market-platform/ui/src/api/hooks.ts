import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./endpoints";
import { fetchLiveCanaryReconciliation, fetchLiveCanarySnapshot } from "./liveCanary";
import type { PaperOrderRequest } from "./schemas";
import type { Mode } from "../components/mode-session/types";

export const queryKeys = {
  context: ["context"] as const,
  attention: ["attention"] as const,
  opportunitiesSummary: ["opportunities", "summary"] as const,
  instrument: (instrumentId: string) => ["instrument", instrumentId] as const,
  exploreSqueeze: ["explore", "squeeze"] as const,
  exploreSqueezeScanner: ["explore", "squeeze", "scanner"] as const,
  exploreFutures: ["explore", "futures"] as const,
  exploreCatalyst: ["explore", "catalyst"] as const,
  workspaceSqueeze: (instrumentId: string, dataMode: "frozen" | "current" = "frozen") =>
    ["workspace", instrumentId, "squeeze", dataMode] as const,
  workspaceOrderFlow: (instrumentId: string) => ["workspace", instrumentId, "order-flow"] as const,
  workspaceOptions: (instrumentId: string) => ["workspace", instrumentId, "options"] as const,
  workspaceLargeTransactions: (instrumentId: string) => ["workspace", instrumentId, "large-transactions"] as const,
  workspaceOrderBook: (instrumentId: string) => ["workspace", instrumentId, "order-book"] as const,
  workspaceFutures: (instrumentId: string) => ["workspace", instrumentId, "futures"] as const,
  workspaceCatalyst: (instrumentId: string) => ["workspace", instrumentId, "catalyst"] as const,
  workspaceFundEtf: (instrumentId: string) => ["workspace", instrumentId, "fund-etf"] as const,
  workspaceDisclosure: (instrumentId: string) => ["workspace", instrumentId, "disclosure"] as const,
  workspaceInstitutionalFlow: (instrumentId: string) =>
    ["workspace", instrumentId, "institutional-flow"] as const,
  workspaceEvidence: (instrumentId: string, dataMode: "frozen" | "current" = "frozen") =>
    ["workspace", instrumentId, "evidence", dataMode] as const,
  replaySession: ["replay", "session"] as const,
  researchAnalytics: ["research", "analytics"] as const,
  researchModels: ["research", "models"] as const,
  researchSimulation: ["research", "simulation"] as const,
  assistantStatus: ["assistant", "status"] as const,
  assistantConversations: ["assistant", "conversations"] as const,
  assistantMessages: (conversationId: string) => ["assistant", conversationId, "messages"] as const,
  paperPortfolio: ["paper", "portfolio"] as const,
  paperForwardTests: (accountId?: string) => ["paper", "forward-tests", accountId ?? "unbound"] as const,
  demoPortfolio: ["demo", "portfolio"] as const,
  paperOrderHistory: ["paper", "order-history"] as const,
  paperTrace: (
    intentId?: string,
    orderId?: string,
    fillId?: string,
    allocationDecisionId?: string,
  ) => ["paper", "trace", intentId, orderId, fillId, allocationDecisionId] as const,
  paperStrategyProfitability: (accountId?: string, sessionId?: string) =>
    ["paper", "strategy-profitability", accountId ?? "unbound", sessionId ?? "unbound"] as const,
  liveCanarySnapshot: (laneId?: string, accountId?: string) =>
    ["live", "canary-snapshot", laneId ?? "account", accountId ?? "fp-canary-local"] as const,
  liveCanaryReconciliation: (accountId?: string) =>
    ["live", "canary-reconciliation", accountId ?? "fp-canary-local"] as const,
  providerHealth: ["provider", "health"] as const,
  symbolSearch: (query: string) => ["symbols", "search", query] as const,
  instrumentSearch: (query: string, limit = 25) => ["is", query, String(limit)] as const,
  optionsProduct: (instrumentId: string, mode: Mode, accountId?: string, provider = "fixture") =>
    ["op", instrumentId, mode, accountId ?? "u", provider] as const,
  futuresProduct: (instrumentId: string, mode: Mode, accountId?: string, provider = "fixture") =>
    ["fp", instrumentId, mode, accountId ?? "u", provider] as const,
  instrumentCapabilities: (instrumentId: string) => ["instruments", instrumentId, "capabilities"] as const,
  marketState: (instrumentId: string) => ["market-state", instrumentId] as const,
};

export function useContextQuery() {
  return useQuery({ queryKey: queryKeys.context, queryFn: api.getContext });
}

export function useAttentionQuery() {
  return useQuery({ queryKey: queryKeys.attention, queryFn: api.getAttention });
}

export function useOpportunitiesSummaryQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunitiesSummary,
    queryFn: api.getOpportunitiesSummary,
    enabled,
  });
}

export function useInstrumentQuery(instrumentId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.instrument(instrumentId),
    queryFn: () => api.getInstrument(instrumentId),
    enabled: enabled && instrumentId.length > 0,
  });
}

export function useExploreSqueezeQuery() {
  return useQuery({ queryKey: queryKeys.exploreSqueeze, queryFn: api.getExploreSqueeze });
}

export function useExploreSqueezeScannerQuery() {
  return useQuery({
    queryKey: queryKeys.exploreSqueezeScanner,
    queryFn: api.getExploreSqueezeScanner,
  });
}

export function useExploreFuturesQuery() {
  return useQuery({ queryKey: queryKeys.exploreFutures, queryFn: api.getExploreFutures });
}

export function useExploreCatalystQuery() {
  return useQuery({ queryKey: queryKeys.exploreCatalyst, queryFn: api.getExploreCatalyst });
}

export function useWorkspaceSqueezeQuery(instrumentId: string, dataMode: "frozen" | "current" = "frozen") {
  return useQuery({
    queryKey: queryKeys.workspaceSqueeze(instrumentId, dataMode),
    queryFn: () => api.getWorkspaceSqueeze(instrumentId, dataMode),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceOrderFlowQuery(instrumentId: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return useQuery({
    queryKey: queryKeys.workspaceOrderFlow(instrumentId),
    queryFn: () => api.getWorkspaceOrderFlow(instrumentId),
    enabled: instrumentId.length > 0,
    refetchInterval: isLive ? 2000 : false,
  });
}

export function useWorkspaceEvidenceQuery(instrumentId: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const dataMode = isLive ? "current" : "frozen";
  return useQuery({
    queryKey: queryKeys.workspaceEvidence(instrumentId, dataMode),
    queryFn: () => api.getWorkspaceEvidence(instrumentId, dataMode),
    enabled: instrumentId.length > 0,
    refetchInterval: isLive ? 5000 : false,
  });
}

export function useWorkspaceOptionsQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceOptions(instrumentId),
    queryFn: () => api.getWorkspaceOptions(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceLargeTransactionsQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceLargeTransactions(instrumentId),
    queryFn: () => api.getWorkspaceLargeTransactions(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceOrderBookQuery(instrumentId: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return useQuery({
    queryKey: queryKeys.workspaceOrderBook(instrumentId),
    queryFn: () => api.getWorkspaceOrderBook(instrumentId),
    enabled: instrumentId.length > 0,
    refetchInterval: isLive ? 2000 : false,
  });
}

export function useWorkspaceFuturesQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceFutures(instrumentId),
    queryFn: () => api.getWorkspaceFutures(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceCatalystQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceCatalyst(instrumentId),
    queryFn: () => api.getWorkspaceCatalyst(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceFundEtfQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceFundEtf(instrumentId),
    queryFn: () => api.getWorkspaceFundEtf(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useReplaySessionQuery() {
  return useQuery({ queryKey: queryKeys.replaySession, queryFn: api.getReplaySession });
}

export function useResearchAnalyticsQuery() {
  return useQuery({ queryKey: queryKeys.researchAnalytics, queryFn: api.getResearchAnalytics });
}

export function useResearchModelsQuery() {
  return useQuery({ queryKey: queryKeys.researchModels, queryFn: api.getResearchModels });
}

export function useResearchSimulationQuery() {
  return useQuery({ queryKey: queryKeys.researchSimulation, queryFn: api.getResearchSimulation });
}

export function useWorkspaceDisclosureQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceDisclosure(instrumentId),
    queryFn: () => api.getWorkspaceDisclosure(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useWorkspaceInstitutionalFlowQuery(instrumentId: string) {
  return useQuery({
    queryKey: queryKeys.workspaceInstitutionalFlow(instrumentId),
    queryFn: () => api.getWorkspaceInstitutionalFlow(instrumentId),
    enabled: instrumentId.length > 0,
  });
}

export function useAssistantStatusQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.assistantStatus,
    queryFn: api.getAssistantStatus,
    enabled,
  });
}

export function useAssistantMessagesQuery(conversationId: string | null) {
  return useQuery({
    queryKey: queryKeys.assistantMessages(conversationId ?? ""),
    queryFn: () => api.getAssistantMessages(conversationId!),
    enabled: Boolean(conversationId),
  });
}

export function usePaperPortfolioQuery(viewMode: "DEMO" | "PAPER" = "PAPER") {
  const queryKey = viewMode === "DEMO" ? queryKeys.demoPortfolio : queryKeys.paperPortfolio;
  return useQuery({
    queryKey,
    queryFn: () => api.getPaperPortfolio(viewMode),
  });
}

export function usePaperForwardTestsQuery(accountId?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.paperForwardTests(accountId),
    queryFn: () => api.getPaperForwardTests(accountId),
    enabled: enabled && Boolean(accountId),
  });
}

export function usePaperOrderHistoryInfiniteQuery(enabled = true) {
  return useInfiniteQuery({
    queryKey: queryKeys.paperOrderHistory,
    queryFn: ({ pageParam }) => api.getPaperOrderHistory({ cursor: pageParam }),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
    enabled,
  });
}

export function usePaperTraceQuery(
  params: {
    intentId?: string;
    orderId?: string;
    fillId?: string;
    allocationDecisionId?: string;
  },
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.paperTrace(
      params.intentId,
      params.orderId,
      params.fillId,
      params.allocationDecisionId,
    ),
    queryFn: () => api.getPaperTrace(params),
    enabled: enabled && Boolean(
      params.intentId || params.orderId || params.fillId || params.allocationDecisionId,
    ),
  });
}

export function usePaperStrategyProfitabilityQuery(enabled = true) {
  const portfolioQuery = usePaperPortfolioQuery("PAPER");
  const accountId = portfolioQuery.data?.account.paper_account_id;
  const sessionId = portfolioQuery.data?.session?.session_id;
  return useQuery({
    queryKey: queryKeys.paperStrategyProfitability(accountId, sessionId),
    queryFn: () => api.getPaperStrategyProfitability(),
    enabled,
  });
}

function useInvalidatePaper() {
  const queryClient = useQueryClient();
  return (scope?: { instrumentId?: string; mode?: Mode; accountId?: string }) => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.paperPortfolio });
    void queryClient.invalidateQueries({ queryKey: queryKeys.demoPortfolio });
    void queryClient.invalidateQueries({ queryKey: queryKeys.paperOrderHistory });
    void queryClient.invalidateQueries({ queryKey: ["paper", "strategy-profitability"] });
    void queryClient.invalidateQueries({ queryKey: ["paper", "trace"] });
    void queryClient.invalidateQueries({ queryKey: ["context"] });
    if (scope?.instrumentId && scope.mode) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.optionsProduct(scope.instrumentId, scope.mode, scope.accountId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.futuresProduct(scope.instrumentId, scope.mode, scope.accountId),
      });
    }
  };
}

export function usePreviewPaperOrderMutation() {
  return useMutation({ mutationFn: (body: PaperOrderRequest) => api.previewPaperOrder(body) });
}

export function useSubmitPaperOrderMutation() {
  const invalidate = useInvalidatePaper();
  return useMutation({
    mutationFn: (body: PaperOrderRequest) => api.submitPaperOrder(body),
    onSuccess: () => invalidate(),
  });
}

export function useOpenPaperSessionMutation() {
  const invalidate = useInvalidatePaper();
  return useMutation({
    mutationFn: (preferredInstrument?: string) => api.openPaperSession("INTERNAL_SIMULATION", preferredInstrument),
    onSuccess: () => invalidate(),
  });
}

export function useClosePaperSessionMutation() {
  const invalidate = useInvalidatePaper();
  return useMutation({
    mutationFn: () => api.closePaperSession(),
    onSuccess: () => invalidate(),
  });
}

export function useProviderHealthQuery() {
  return useQuery({
    queryKey: queryKeys.providerHealth,
    queryFn: api.getProviderHealth,
    refetchInterval: 5000,
  });
}

export function useLiveCanarySnapshotQuery(laneId = "account", accountId = "fp-canary-local", enabled = true) {
  return useQuery({
    queryKey: queryKeys.liveCanarySnapshot(laneId, accountId),
    queryFn: () => fetchLiveCanarySnapshot(accountId),
    enabled,
    staleTime: 15000,
    refetchInterval: enabled ? 15000 : false,
  });
}

export function useLiveCanaryReconciliationQuery(accountId = "fp-canary-local", enabled = true) {
  return useQuery({
    queryKey: queryKeys.liveCanaryReconciliation(accountId),
    queryFn: () => fetchLiveCanaryReconciliation(accountId),
    enabled,
    refetchInterval: enabled ? 15000 : false,
  });
}

export function useSymbolSearchQuery(query: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.symbolSearch(query),
    queryFn: () => api.searchSymbols(query),
    enabled: enabled && query.length > 0,
  });
}

export function useInstrumentSelectorQuery(query: string, enabled = true, limit = 25) {
  return useQuery({
    queryKey: queryKeys.instrumentSearch(query, limit),
    queryFn: () => api.searchInstruments(query, limit),
    enabled: enabled && query.length > 0,
  });
}

export function useOptionsProductQuery(
  instrumentId: string,
  mode: Mode,
  accountId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.optionsProduct(instrumentId, mode, accountId),
    queryFn: () => api.getOptionsProduct(instrumentId, mode, accountId),
    enabled: enabled && instrumentId.length > 0,
  });
}

export function useFuturesProductQuery(
  instrumentId: string,
  mode: Mode,
  accountId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.futuresProduct(instrumentId, mode, accountId),
    queryFn: () => api.getFuturesProduct(instrumentId, mode, accountId),
    enabled: enabled && instrumentId.length > 0,
  });
}

export function useInstrumentCapabilitiesQuery(instrumentId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.instrumentCapabilities(instrumentId),
    queryFn: () => api.getInstrumentCapabilities(instrumentId),
    enabled: enabled && instrumentId.length > 0,
  });
}

export function useMarketStateQuery(instrumentId: string, enabled = true) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return useQuery({
    queryKey: queryKeys.marketState(instrumentId),
    queryFn: () => api.getMarketState(instrumentId),
    enabled: enabled && instrumentId.length > 0 && isLive,
    refetchInterval: isLive ? 2000 : false,
  });
}

export function useSubscribeMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (params: { instrumentId: string; capabilities: string[]; consumerId?: string }) =>
      api.subscribeLive({
        instrument_id: params.instrumentId,
        capabilities: params.capabilities,
        consumer_id: params.consumerId ?? "ui-explore",
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.providerHealth });
      client.invalidateQueries({ queryKey: queryKeys.context });
    },
  });
}

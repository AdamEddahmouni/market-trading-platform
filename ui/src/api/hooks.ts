import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./endpoints";
import type { PaperOrderRequest } from "./schemas";

export const queryKeys = {
  context: ["context"] as const,
  attention: ["attention"] as const,
  instrument: (id: string) => ["instrument", id] as const,
  exploreSqueeze: ["explore", "squeeze"] as const,
  exploreSqueezeScanner: ["explore", "squeeze", "scanner"] as const,
  exploreFutures: ["explore", "futures"] as const,
  exploreCatalyst: ["explore", "catalyst"] as const,
  workspaceSqueeze: (symbol: string, dataMode: "frozen" | "current" = "frozen") =>
    ["workspace", symbol, "squeeze", dataMode] as const,
  workspaceOrderFlow: (symbol: string) => ["workspace", symbol, "order-flow"] as const,
  workspaceOptions: (symbol: string) => ["workspace", symbol, "options"] as const,
  workspaceLargeTransactions: (symbol: string) => ["workspace", symbol, "large-transactions"] as const,
  workspaceOrderBook: (symbol: string) => ["workspace", symbol, "order-book"] as const,
  workspaceFutures: (symbol: string) => ["workspace", symbol, "futures"] as const,
  workspaceCatalyst: (symbol: string) => ["workspace", symbol, "catalyst"] as const,
  workspaceFundEtf: (symbol: string) => ["workspace", symbol, "fund-etf"] as const,
  replaySession: ["replay", "session"] as const,
  researchAnalytics: ["research", "analytics"] as const,
  researchModels: ["research", "models"] as const,
  researchSimulation: ["research", "simulation"] as const,
  workspaceDisclosure: (symbol: string) => ["workspace", symbol, "disclosure"] as const,
  workspaceInstitutionalFlow: (symbol: string) => ["workspace", symbol, "institutional-flow"] as const,
  workspaceEvidence: (symbol: string, dataMode: "frozen" | "current" = "frozen") =>
    ["workspace", symbol, "evidence", dataMode] as const,
  assistantStatus: ["assistant", "status"] as const,
  assistantConversations: ["assistant", "conversations"] as const,
  assistantMessages: (conversationId: string) => ["assistant", conversationId, "messages"] as const,
  paperPortfolio: ["paper", "portfolio"] as const,
  paperTrace: (intentId?: string, orderId?: string) => ["paper", "trace", intentId, orderId] as const,
  providerHealth: ["provider", "health"] as const,
  symbolSearch: (query: string) => ["symbols", "search", query] as const,
  instrumentCapabilities: (id: string) => ["instruments", id, "capabilities"] as const,
  marketState: (id: string) => ["market-state", id] as const,
};

export function useContextQuery() {
  return useQuery({ queryKey: queryKeys.context, queryFn: api.getContext });
}

export function useAttentionQuery() {
  return useQuery({ queryKey: queryKeys.attention, queryFn: api.getAttention });
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

export function useWorkspaceSqueezeQuery(symbol: string, dataMode: "frozen" | "current" = "frozen") {
  return useQuery({
    queryKey: queryKeys.workspaceSqueeze(symbol, dataMode),
    queryFn: () => api.getWorkspaceSqueeze(symbol, dataMode),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceOrderFlowQuery(symbol: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return useQuery({
    queryKey: queryKeys.workspaceOrderFlow(symbol),
    queryFn: () => api.getWorkspaceOrderFlow(symbol),
    enabled: symbol.length > 0,
    refetchInterval: isLive ? 2000 : false,
  });
}

export function useWorkspaceEvidenceQuery(symbol: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  const dataMode = isLive ? "current" : "frozen";
  return useQuery({
    queryKey: queryKeys.workspaceEvidence(symbol, dataMode),
    queryFn: () => api.getWorkspaceEvidence(symbol, dataMode),
    enabled: symbol.length > 0,
    refetchInterval: isLive ? 5000 : false,
  });
}

export function useWorkspaceOptionsQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceOptions(symbol),
    queryFn: () => api.getWorkspaceOptions(symbol),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceLargeTransactionsQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceLargeTransactions(symbol),
    queryFn: () => api.getWorkspaceLargeTransactions(symbol),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceOrderBookQuery(symbol: string) {
  const contextQuery = useContextQuery();
  const isLive = contextQuery.data?.as_of_context.data_mode === "LIVE_OBSERVATIONAL";
  return useQuery({
    queryKey: queryKeys.workspaceOrderBook(symbol),
    queryFn: () => api.getWorkspaceOrderBook(symbol),
    enabled: symbol.length > 0,
    refetchInterval: isLive ? 2000 : false,
  });
}

export function useWorkspaceFuturesQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceFutures(symbol),
    queryFn: () => api.getWorkspaceFutures(symbol),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceCatalystQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceCatalyst(symbol),
    queryFn: () => api.getWorkspaceCatalyst(symbol),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceFundEtfQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceFundEtf(symbol),
    queryFn: () => api.getWorkspaceFundEtf(symbol),
    enabled: symbol.length > 0,
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

export function useWorkspaceDisclosureQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceDisclosure(symbol),
    queryFn: () => api.getWorkspaceDisclosure(symbol),
    enabled: symbol.length > 0,
  });
}

export function useWorkspaceInstitutionalFlowQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceInstitutionalFlow(symbol),
    queryFn: () => api.getWorkspaceInstitutionalFlow(symbol),
    enabled: symbol.length > 0,
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

export function usePaperPortfolioQuery() {
  return useQuery({ queryKey: queryKeys.paperPortfolio, queryFn: api.getPaperPortfolio });
}

export function usePaperTraceQuery(params: { intentId?: string; orderId?: string; fillId?: string }, enabled = true) {
  return useQuery({
    queryKey: queryKeys.paperTrace(params.intentId, params.orderId),
    queryFn: () => api.getPaperTrace(params),
    enabled: enabled && Boolean(params.intentId || params.orderId || params.fillId),
  });
}

function useInvalidatePaper() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.paperPortfolio });
    void queryClient.invalidateQueries({ queryKey: ["context"] });
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

export function useSymbolSearchQuery(query: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.symbolSearch(query),
    queryFn: () => api.searchSymbols(query),
    enabled: enabled && query.length > 0,
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

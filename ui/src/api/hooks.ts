import { useQuery } from "@tanstack/react-query";
import { api } from "./endpoints";

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
  assistantStatus: ["assistant", "status"] as const,
  assistantConversations: ["assistant", "conversations"] as const,
  assistantMessages: (conversationId: string) => ["assistant", conversationId, "messages"] as const,
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
  return useQuery({
    queryKey: queryKeys.workspaceOrderFlow(symbol),
    queryFn: () => api.getWorkspaceOrderFlow(symbol),
    enabled: symbol.length > 0,
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
  return useQuery({
    queryKey: queryKeys.workspaceOrderBook(symbol),
    queryFn: () => api.getWorkspaceOrderBook(symbol),
    enabled: symbol.length > 0,
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

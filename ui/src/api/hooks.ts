import { useQuery } from "@tanstack/react-query";
import { api } from "./endpoints";

export const queryKeys = {
  context: ["context"] as const,
  attention: ["attention"] as const,
  instrument: (id: string) => ["instrument", id] as const,
  exploreSqueeze: ["explore", "squeeze"] as const,
  workspaceSqueeze: (symbol: string) => ["workspace", symbol, "squeeze"] as const,
  workspaceOrderFlow: (symbol: string) => ["workspace", symbol, "order-flow"] as const,
  workspaceOptions: (symbol: string) => ["workspace", symbol, "options"] as const,
  workspaceLargeTransactions: (symbol: string) => ["workspace", symbol, "large-transactions"] as const,
  replaySession: ["replay", "session"] as const,
  researchAnalytics: ["research", "analytics"] as const,
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

export function useWorkspaceSqueezeQuery(symbol: string) {
  return useQuery({
    queryKey: queryKeys.workspaceSqueeze(symbol),
    queryFn: () => api.getWorkspaceSqueeze(symbol),
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

export function useReplaySessionQuery() {
  return useQuery({ queryKey: queryKeys.replaySession, queryFn: api.getReplaySession });
}

export function useResearchAnalyticsQuery() {
  return useQuery({ queryKey: queryKeys.researchAnalytics, queryFn: api.getResearchAnalytics });
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

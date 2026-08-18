import { fetchJson, fetchRawJson } from "./fetchJson";
import {
  AttentionResponseSchema,
  ContextResponseSchema,
  ExploreSqueezeResponseSchema,
  ExploreFuturesResponseSchema,
  ExploreCatalystResponseSchema,
  InstrumentOverviewSchema,
  ReplaySessionSchema,
  WorkspaceSqueezeResponseSchema,
  WorkspaceOrderFlowResponseSchema,
  WorkspaceOptionsResponseSchema,
  WorkspaceLargeTransactionsResponseSchema,
  WorkspaceOrderBookResponseSchema,
  WorkspaceFuturesResponseSchema,
  WorkspaceCatalystResponseSchema,
  WorkspaceFundEtfResponseSchema,
  AssistantConversationSchema,
  AssistantStatusSchema,
  AssistantConversationsResponseSchema,
  AssistantMessagesResponseSchema,
  AssistantPromptResponseSchema,
  ResearchAnalyticsResponseSchema,
  ResearchModelsResponseSchema,
  ResearchSimulationResponseSchema,
  WorkspaceDisclosureResponseSchema,
  WorkspaceInstitutionalFlowResponseSchema,
} from "./schemas";

export const api = {
  getContext: () => fetchJson("/context", ContextResponseSchema),
  getAttention: () => fetchJson("/attention", AttentionResponseSchema),
  getInstrument: (id: string) =>
    fetchJson(`/instruments/${encodeURIComponent(id)}/overview`, InstrumentOverviewSchema),
  getExplain: (ref: string) => fetchRawJson(`/explain/${encodeURIComponent(ref)}`),
  getInspect: (ref: string) => fetchRawJson(`/inspect/${encodeURIComponent(ref)}`),
  scrubReplay: async (cursorIndex: number) => {
    const response = await fetch("/replay/scrub", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cursor_index: cursorIndex }),
    });
    if (!response.ok) throw new Error("scrub failed");
    return response.json();
  },
  getReplaySession: () => fetchJson("/replay/session", ReplaySessionSchema),
  getResearchAnalytics: () => fetchJson("/research/analytics", ResearchAnalyticsResponseSchema),
  getResearchModels: () => fetchJson("/research/models", ResearchModelsResponseSchema),
  getResearchSimulation: () => fetchJson("/research/simulation", ResearchSimulationResponseSchema),
  getWorkspaceDisclosure: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/disclosure`, WorkspaceDisclosureResponseSchema),
  getWorkspaceInstitutionalFlow: (symbol: string) =>
    fetchJson(
      `/workspace/${encodeURIComponent(symbol)}/institutional-flow`,
      WorkspaceInstitutionalFlowResponseSchema,
    ),
  getExploreSqueeze: () => fetchJson("/explore/squeeze", ExploreSqueezeResponseSchema),
  getExploreSqueezeScanner: () => fetchJson("/explore/squeeze/scanner", ExploreSqueezeResponseSchema),
  getExploreFutures: () => fetchJson("/explore/futures", ExploreFuturesResponseSchema),
  getExploreCatalyst: () => fetchJson("/explore/catalyst", ExploreCatalystResponseSchema),
  getWorkspaceSqueeze: (symbol: string, dataMode: "frozen" | "current" = "frozen") => {
    const suffix = dataMode === "current" ? "?data_mode=current" : "";
    return fetchJson(
      `/workspace/${encodeURIComponent(symbol)}/squeeze${suffix}`,
      WorkspaceSqueezeResponseSchema,
    );
  },
  getWorkspaceOrderFlow: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/order-flow`, WorkspaceOrderFlowResponseSchema),
  getWorkspaceOptions: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/options`, WorkspaceOptionsResponseSchema),
  getWorkspaceLargeTransactions: (symbol: string) =>
    fetchJson(
      `/workspace/${encodeURIComponent(symbol)}/large-transactions`,
      WorkspaceLargeTransactionsResponseSchema,
    ),
  getWorkspaceOrderBook: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/order-book`, WorkspaceOrderBookResponseSchema),
  getWorkspaceFutures: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/futures`, WorkspaceFuturesResponseSchema),
  getWorkspaceCatalyst: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/catalyst`, WorkspaceCatalystResponseSchema),
  getWorkspaceFundEtf: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/fund-etf`, WorkspaceFundEtfResponseSchema),
  getAssistantStatus: () => fetchJson("/assistant/status", AssistantStatusSchema),
  getAssistantConversations: (principalId?: string) => {
    const query = principalId ? `?principal_id=${encodeURIComponent(principalId)}` : "";
    return fetchJson(`/assistant/conversations${query}`, AssistantConversationsResponseSchema);
  },
  getAssistantMessages: (conversationId: string) =>
    fetchJson(
      `/assistant/conversations/${encodeURIComponent(conversationId)}/messages`,
      AssistantMessagesResponseSchema,
    ),
  createAssistantConversation: async (title: string) => {
    const response = await fetch("/assistant/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) throw new Error("create conversation failed");
    const payload = await response.json();
    return AssistantConversationSchema.parse(payload);
  },
  submitAssistantPrompt: async (conversationId: string, prompt: string, selectionRef?: string) => {
    const response = await fetch(
      `/assistant/conversations/${encodeURIComponent(conversationId)}/prompt`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, selection_ref: selectionRef ?? null }),
      },
    );
    if (!response.ok) throw new Error("assistant prompt failed");
    return AssistantPromptResponseSchema.parse(await response.json());
  },
};

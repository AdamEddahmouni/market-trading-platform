import { fetchJson, fetchRawJson, postJson } from "./fetchJson";
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
  WorkspaceEvidenceResponseSchema,
  PaperPortfolioResponseSchema,
  PaperOrderHistoryPageSchema,
  PaperOrderPreviewResponseSchema,
  PaperOrderSubmitResponseSchema,
  PaperSessionResponseSchema,
  PaperTraceResponseSchema,
  PaperStrategyProfitabilityResponseSchema,
  ProviderHealthResponseSchema,
  SymbolSearchResponseSchema,
  InstrumentCapabilitiesResponseSchema,
  MarketStateResponseSchema,
  OperatorLifecycleStatusSchema,
  OperatorReadinessSchema,
  OperatorConfigSchema,
  OperationStatusSchema,
  type LifecycleAction,
  type PaperOrderRequest,
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
  getWorkspaceEvidence: (symbol: string, dataMode: "frozen" | "current" = "frozen") => {
    const suffix = dataMode === "current" ? "?data_mode=current" : "";
    return fetchJson(
      `/workspace/${encodeURIComponent(symbol)}/evidence${suffix}`,
      WorkspaceEvidenceResponseSchema,
    );
  },
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
  getPaperPortfolio: (viewMode: "DEMO" | "PAPER" = "PAPER") =>
    fetchJson(`/paper/portfolio?view_mode=${viewMode}`, PaperPortfolioResponseSchema),
  getPaperOrderHistory: (params?: { cursor?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.cursor) query.set("cursor", params.cursor);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString();
    return fetchJson(`/paper/order-history${suffix ? `?${suffix}` : ""}`, PaperOrderHistoryPageSchema);
  },
  previewPaperOrder: (body: PaperOrderRequest) =>
    postJson("/paper/orders/preview", body, PaperOrderPreviewResponseSchema),
  submitPaperOrder: (body: PaperOrderRequest) =>
    postJson("/paper/orders", body, PaperOrderSubmitResponseSchema),
  openPaperSession: (executionMode = "INTERNAL_SIMULATION", preferredInstrument?: string) =>
    postJson(
      "/paper/sessions",
      {
        execution_mode: executionMode,
        ...(preferredInstrument ? { preferred_instrument: preferredInstrument } : {}),
      },
      PaperSessionResponseSchema,
    ),
  closePaperSession: () => postJson("/paper/sessions/close", {}, PaperSessionResponseSchema),
  cancelPaperOrder: (orderId: string) =>
    postJson("/paper/orders/cancel", { order_id: orderId }, PaperOrderSubmitResponseSchema),
  getPaperTrace: (params: { intentId?: string; orderId?: string; fillId?: string }) => {
    const query = new URLSearchParams();
    if (params.intentId) query.set("intent_id", params.intentId);
    if (params.orderId) query.set("order_id", params.orderId);
    if (params.fillId) query.set("fill_id", params.fillId);
    return fetchJson(`/paper/trace?${query.toString()}`, PaperTraceResponseSchema);
  },
  getPaperStrategyProfitability: (params?: {
    allocationDecisionId?: string;
    asOfNs?: number;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.allocationDecisionId) query.set("allocation_decision_id", params.allocationDecisionId);
    if (params?.asOfNs !== undefined) query.set("as_of_ns", String(params.asOfNs));
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    const suffix = query.toString();
    return fetchJson(
      `/paper/strategy-profitability${suffix ? `?${suffix}` : ""}`,
      PaperStrategyProfitabilityResponseSchema,
    );
  },
  searchSymbols: (query: string) =>
    fetchJson(`/symbols/search?q=${encodeURIComponent(query)}`, SymbolSearchResponseSchema),
  getInstrumentCapabilities: (instrumentId: string) =>
    fetchJson(`/instruments/${encodeURIComponent(instrumentId)}/capabilities`, InstrumentCapabilitiesResponseSchema),
  getProviderHealth: () => fetchJson("/provider/health", ProviderHealthResponseSchema),
  getMarketState: (instrumentId: string) =>
    fetchJson(`/market-state/${encodeURIComponent(instrumentId)}`, MarketStateResponseSchema),
  getOperatorLifecycleStatus: () =>
    fetchJson("/operator/lifecycle/status", OperatorLifecycleStatusSchema),
  getOperatorReadiness: () => fetchJson("/operator/readiness", OperatorReadinessSchema),
  getOperatorConfig: () => fetchJson("/operator/config", OperatorConfigSchema),
  runOperatorLifecycleAction: (action: LifecycleAction) =>
    postJson("/operator/lifecycle/actions", { action }, OperationStatusSchema),
  refreshOperatorProvider: (provider: string) =>
    postJson(`/operator/providers/${encodeURIComponent(provider)}/refresh`, {}, OperationStatusSchema),
  saveOperatorProviderConfig: (provider: string, values: Record<string, string>) =>
    postJson("/operator/config/provider", { provider, values }, OperatorConfigSchema),
  subscribeLive: async (body: { instrument_id: string; capabilities: string[]; consumer_id?: string }) => {
    const response = await fetch("/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("subscription failed");
    return response.json();
  },
};

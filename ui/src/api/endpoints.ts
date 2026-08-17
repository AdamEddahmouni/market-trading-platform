import { fetchJson, fetchRawJson } from "./fetchJson";
import {
  AttentionResponseSchema,
  ContextResponseSchema,
  ExploreSqueezeResponseSchema,
  InstrumentOverviewSchema,
  ReplaySessionSchema,
  WorkspaceSqueezeResponseSchema,
  WorkspaceOrderFlowResponseSchema,
  WorkspaceOptionsResponseSchema,
  AssistantConversationSchema,
  AssistantStatusSchema,
  AssistantConversationsResponseSchema,
  AssistantMessagesResponseSchema,
  AssistantPromptResponseSchema,
  ResearchAnalyticsResponseSchema,
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
  getExploreSqueeze: () => fetchJson("/explore/squeeze", ExploreSqueezeResponseSchema),
  getWorkspaceSqueeze: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/squeeze`, WorkspaceSqueezeResponseSchema),
  getWorkspaceOrderFlow: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/order-flow`, WorkspaceOrderFlowResponseSchema),
  getWorkspaceOptions: (symbol: string) =>
    fetchJson(`/workspace/${encodeURIComponent(symbol)}/options`, WorkspaceOptionsResponseSchema),
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

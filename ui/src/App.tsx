import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, type AttentionItem } from "./api/client";
import {
  queryKeys,
  useAttentionQuery,
  useAssistantMessagesQuery,
  useAssistantStatusQuery,
  useContextQuery,
  useReplaySessionQuery,
} from "./api/hooks";
import { AssistantHistoryPage } from "./components/AssistantHistoryPage";
import { AssistantSidecar } from "./components/AssistantSidecar";
import { ContextBar } from "./components/ContextBar";
import { ExplanationDrawer } from "./components/ExplanationDrawer";
import { ExplorePage } from "./components/ExplorePage";
import { ResearchPage } from "./components/ResearchPage";
import { SqueezeWorkspacePage } from "./components/squeeze/SqueezeWorkspacePage";
import { OrderFlowWorkspacePage } from "./components/orderflow/OrderFlowWorkspacePage";
import { OptionsWorkspacePage } from "./components/options/OptionsWorkspacePage";
import { LargeTransactionsWorkspacePage } from "./components/largetransactions/LargeTransactionsWorkspacePage";
import { OrderBookWorkspacePage } from "./components/orderbook/OrderBookWorkspacePage";
import { FuturesWorkspacePage } from "./components/futures/FuturesWorkspacePage";
import { CatalystWorkspacePage } from "./components/catalyst/CatalystWorkspacePage";
import { FundEtfWorkspacePage } from "./components/fundetf/FundEtfWorkspacePage";
import { DisclosureWorkspacePage } from "./components/disclosure/DisclosureWorkspacePage";
import { InstitutionalFlowWorkspacePage } from "./components/institutional/InstitutionalFlowWorkspacePage";
import { InspectorPanel } from "./components/InspectorPanel";
import { NavShell } from "./components/NavShell";
import { NowPage } from "./components/NowPage";
import { WorkspaceRoute } from "./components/WorkspaceRoute";
import "./styles/tokens.css";
import "./styles/layout.css";

const queryClient = new QueryClient();

function GatedPage({ title }: { title: string }) {
  return (
    <section className="page gated-page">
      <h1>{title}</h1>
      <div className="capability-panel unavailable">
        <p>UNAVAILABLE — separate authorization required.</p>
      </div>
    </section>
  );
}

function Shell() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [drawerPayload, setDrawerPayload] = useState<Record<string, unknown> | null>(null);
  const [inspectorPayload, setInspectorPayload] = useState<Record<string, unknown> | null>(null);
  const [inspectorTab, setInspectorTab] = useState<string | null>(null);
  const [cursorIndex, setCursorIndex] = useState(0);
  const [maxIndex, setMaxIndex] = useState(0);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [selectionRef, setSelectionRef] = useState<string | null>(null);

  const contextQuery = useContextQuery();
  const attentionQuery = useAttentionQuery();
  const replaySessionQuery = useReplaySessionQuery();
  const assistantStatusQuery = useAssistantStatusQuery(assistantOpen);
  const assistantMessagesQuery = useAssistantMessagesQuery(conversationId);

  useEffect(() => {
    if (replaySessionQuery.data) {
      setCursorIndex(replaySessionQuery.data.cursor_index);
      setMaxIndex(Math.max(0, replaySessionQuery.data.event_count - 1));
    }
  }, [replaySessionQuery.data]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDrawerPayload(null);
        setInspectorPayload(null);
        if (assistantOpen) setAssistantOpen(false);
      }
      if (event.key === "a" || event.key === "A") {
        const target = event.target as HTMLElement | null;
        if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
        setAssistantOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [assistantOpen]);

  useEffect(() => {
    if (!assistantOpen) return;
    if (conversationId) return;
    let cancelled = false;
    api.createAssistantConversation("Replay research session").then((conversation) => {
      if (!cancelled) setConversationId(conversation.conversation_id);
    });
    return () => {
      cancelled = true;
    };
  }, [assistantOpen, conversationId]);

  const refreshAll = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.context }),
      client.invalidateQueries({ queryKey: queryKeys.attention }),
      client.invalidateQueries({ queryKey: ["instrument"] }),
    ]);
  };

  const openExplainRef = async (ref: string) => {
    setSelectionRef(ref);
    setDrawerPayload(await api.getExplain(ref));
  };

  const openInspectRef = async (ref: string) => {
    setInspectorPayload(await api.getInspect(ref));
    setInspectorTab(null);
  };

  const openSqueezeHistory = async (symbol: string) => {
    const ref = `inspect:squeeze:timeline:${symbol.toUpperCase()}`;
    setInspectorPayload(await api.getInspect(ref));
    setInspectorTab("TIMELINE");
  };

  const openExplain = async (item: AttentionItem) => {
    await openExplainRef(item.explanation_ref);
  };

  const openInspect = async (item: AttentionItem) => {
    await openInspectRef(item.explanation_ref.replace("explain:", "inspect:"));
  };

  const scrub = async (index: number) => {
    await api.scrubReplay(index);
    setCursorIndex(index);
    setMaxIndex(Math.max(maxIndex, index));
    await refreshAll();
  };

  const submitAssistantPrompt = async (prompt: string) => {
    if (!conversationId) return;
    setAssistantBusy(true);
    try {
      await api.submitAssistantPrompt(conversationId, prompt, selectionRef);
      await client.invalidateQueries({
        queryKey: queryKeys.assistantMessages(conversationId),
      });
      await client.invalidateQueries({ queryKey: queryKeys.assistantConversations });
    } finally {
      setAssistantBusy(false);
    }
  };

  if (contextQuery.isLoading) {
    return <div className="app-loading">Loading replay context…</div>;
  }
  if (contextQuery.error || !contextQuery.data) {
    return (
      <div className="app-loading">
        API unavailable. Start backend: python tools/ui1/run_ui_api.py --serve
      </div>
    );
  }

  return (
    <div className="app-shell">
      <NavShell />
      <ContextBar context={contextQuery.data} />
      <div className="app-body">
        <main className="main-content">
          <Routes>
            <Route
              path="/"
              element={
                <NowPage
                  items={attentionQuery.data?.items ?? []}
                  tierSummary={attentionQuery.data?.tier_summary}
                  onWhy={openExplain}
                  onExplain={openExplain}
                  onInspect={openInspect}
                  onOpenWorkspace={(item) => {
                    if (item.instrument_id) {
                      navigate(`/workspace/${item.instrument_id}`);
                    }
                  }}
                />
              }
            />
            <Route path="/explore" element={<ExplorePage onExplain={openExplainRef} />} />
            <Route path="/workspace" element={<Navigate to="/workspace/BIYA" replace />} />
            <Route
              path="/workspace/:symbol"
              element={
                <WorkspaceRoute
                  cursorIndex={cursorIndex}
                  maxIndex={maxIndex}
                  onScrub={scrub}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                  onOpenSqueezeHistory={openSqueezeHistory}
                />
              }
            />
            <Route
              path="/workspace/:symbol/squeeze"
              element={
                <SqueezeWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                  onOpenHistory={openSqueezeHistory}
                />
              }
            />
            <Route
              path="/workspace/:symbol/order-flow"
              element={
                <OrderFlowWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/order-book"
              element={
                <OrderBookWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/futures"
              element={
                <FuturesWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/catalyst"
              element={
                <CatalystWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/fund-etf"
              element={
                <FundEtfWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/options"
              element={
                <OptionsWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/large-transactions"
              element={
                <LargeTransactionsWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/disclosure"
              element={
                <DisclosureWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/institutional-flow"
              element={
                <InstitutionalFlowWorkspacePage
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route path="/research" element={<ResearchPage />} />
            <Route path="/portfolio" element={<GatedPage title="PORTFOLIO" />} />
            <Route path="/assistant/history" element={<AssistantHistoryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <AssistantSidecar
          open={assistantOpen}
          status={assistantStatusQuery.data}
          messages={assistantMessagesQuery.data?.messages ?? []}
          loading={assistantBusy || assistantMessagesQuery.isLoading}
          conversationId={conversationId}
          selectionRef={selectionRef}
          onClose={() => setAssistantOpen(false)}
          onSubmit={submitAssistantPrompt}
          onCitationClick={async (ref) => {
            if (ref.startsWith("inspect:")) {
              await openInspectRef(ref);
              return;
            }
            await openExplainRef(ref);
          }}
        />
      </div>
      {!assistantOpen ? (
        <button
          type="button"
          className="assistant-toggle"
          onClick={() => setAssistantOpen(true)}
          title="Toggle research assistant (A)"
        >
          Assistant
        </button>
      ) : null}
      <ExplanationDrawer payload={drawerPayload} onClose={() => setDrawerPayload(null)} />
      <InspectorPanel
        payload={inspectorPayload}
        preferredTab={inspectorTab}
        onClose={() => {
          setInspectorPayload(null);
          setInspectorTab(null);
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

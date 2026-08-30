import { lazy, useEffect, useState } from "react";
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
import { ContextBar } from "./components/ContextBar";
import { ExplanationDrawer } from "./components/ExplanationDrawer";
import { InspectorPanel } from "./components/InspectorPanel";
import { LazyBoundary } from "./components/LazyBoundary";
import { NavShell } from "./components/NavShell";
import { NowPage } from "./components/NowPage";
import "./styles/tokens.css";
import "./styles/layout.css";

const AssistantHistoryPage = lazy(() =>
  import("./components/AssistantHistoryPage").then((module) => ({
    default: module.AssistantHistoryPage,
  })),
);
const AssistantSidecar = lazy(() =>
  import("./components/AssistantSidecar").then((module) => ({
    default: module.AssistantSidecar,
  })),
);
const ExplorePage = lazy(() =>
  import("./components/ExplorePage").then((module) => ({ default: module.ExplorePage })),
);
const DiscoverPage = lazy(() =>
  import("./components/DiscoverPage").then((module) => ({ default: module.DiscoverPage })),
);
const ResearchPage = lazy(() =>
  import("./components/ResearchPage").then((module) => ({ default: module.ResearchPage })),
);
const SqueezeWorkspacePage = lazy(() =>
  import("./components/squeeze/SqueezeWorkspacePage").then((module) => ({
    default: module.SqueezeWorkspacePage,
  })),
);
const OrderFlowWorkspacePage = lazy(() =>
  import("./components/orderflow/OrderFlowWorkspacePage").then((module) => ({
    default: module.OrderFlowWorkspacePage,
  })),
);
const OptionsWorkspacePage = lazy(() =>
  import("./components/options/OptionsWorkspacePage").then((module) => ({
    default: module.OptionsWorkspacePage,
  })),
);
const LargeTransactionsWorkspacePage = lazy(() =>
  import("./components/largetransactions/LargeTransactionsWorkspacePage").then((module) => ({
    default: module.LargeTransactionsWorkspacePage,
  })),
);
const OrderBookWorkspacePage = lazy(() =>
  import("./components/orderbook/OrderBookWorkspacePage").then((module) => ({
    default: module.OrderBookWorkspacePage,
  })),
);
const FuturesWorkspacePage = lazy(() =>
  import("./components/futures/FuturesWorkspacePage").then((module) => ({
    default: module.FuturesWorkspacePage,
  })),
);
const CatalystWorkspacePage = lazy(() =>
  import("./components/catalyst/CatalystWorkspacePage").then((module) => ({
    default: module.CatalystWorkspacePage,
  })),
);
const FundEtfWorkspacePage = lazy(() =>
  import("./components/fundetf/FundEtfWorkspacePage").then((module) => ({
    default: module.FundEtfWorkspacePage,
  })),
);
const DisclosureWorkspacePage = lazy(() =>
  import("./components/disclosure/DisclosureWorkspacePage").then((module) => ({
    default: module.DisclosureWorkspacePage,
  })),
);
const InstitutionalFlowWorkspacePage = lazy(() =>
  import("./components/institutional/InstitutionalFlowWorkspacePage").then((module) => ({
    default: module.InstitutionalFlowWorkspacePage,
  })),
);
const PortfolioPage = lazy(() =>
  import("./components/PortfolioPage").then((module) => ({ default: module.PortfolioPage })),
);
const OperatorSettingsPage = lazy(() =>
  import("./components/OperatorSettingsPage").then((module) => ({
    default: module.OperatorSettingsPage,
  })),
);
const ProviderHealthPanel = lazy(() =>
  import("./components/live/ProviderHealthPanel").then((module) => ({
    default: module.ProviderHealthPanel,
  })),
);
const LiveCanaryControlPlanePage = lazy(() =>
  import("./components/live/LiveCanaryControlPlanePage").then((module) => ({
    default: module.LiveCanaryControlPlanePage,
  })),
);
const WorkspaceRoute = lazy(() =>
  import("./components/WorkspaceRoute").then((module) => ({ default: module.WorkspaceRoute })),
);
const WorkspaceIndex = lazy(() =>
  import("./components/WorkspaceIndex").then((module) => ({ default: module.WorkspaceIndex })),
);

const queryClient = new QueryClient();

function StartupRecoveryBanner() {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    void fetch("/state/startup")
      .then((response) => response.json())
      .then((payload) => {
        if (payload?.crash_recovery === "OPEN_SESSION_DETECTED") {
          setMessage(
            `Previous paper session detected (${payload.restore}). Positions restore from events; live marks wait for fresh Moomoo evidence.`,
          );
        } else if (payload?.crash_recovery === "CORRUPT_DB") {
          setMessage("Local state database failed integrity check. Original file was preserved.");
        }
      })
      .catch(() => undefined);
  }, []);
  if (!message) return null;
  return (
    <div className="startup-recovery-banner" role="status">
      {message}
    </div>
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
      await api.submitAssistantPrompt(conversationId, prompt, selectionRef ?? undefined);
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
      <StartupRecoveryBanner />
      <div className="app-body">
        <main className="main-content">
          <LazyBoundary>
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
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/workspace" element={<WorkspaceIndex />} />
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
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/live-canary" element={<LiveCanaryControlPlanePage />} />
            <Route path="/settings" element={<OperatorSettingsPage />} />
            <Route path="/diagnostics/provider" element={<ProviderHealthPanel />} />
            <Route path="/assistant/history" element={<AssistantHistoryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </LazyBoundary>
        </main>
        {assistantOpen ? (
          <LazyBoundary label="Loading assistant…">
            <AssistantSidecar
              open
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
          </LazyBoundary>
        ) : null}
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

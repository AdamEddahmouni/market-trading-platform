import { lazy, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { ADMITTED_REPLAY_INSTRUMENT_ID, api, type AttentionItem } from "./api/client";
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
import { ModeDiscoverRoute } from "./components/ModeDiscoverRoute";
import { ModeExploreRoute } from "./components/ModeExploreRoute";
import { ModeNowRoute } from "./components/ModeNowRoute";
import { ModePortfolioRoute } from "./components/ModePortfolioRoute";
import { ModeResearchRoute } from "./components/ModeResearchRoute";
import type { ScrubState } from "./components/demo-now/DemoNowPage";
import { AuthProvider, useOptionalAuth } from "./auth/AuthProvider";
import { OperatorLoginGate } from "./auth/OperatorLoginGate";
import { ApplicationBootstrap } from "./components/mode-session/ApplicationBootstrap";
import { ModeEnvironmentBar } from "./components/mode-session/ModeEnvironmentBar";
import { evaluateModeContext } from "./components/mode-session/modeAuthority";
import type { Mode } from "./components/mode-session/types";
import "./styles/tokens.css";
import "./styles/layout.css";
import "./styles/mode-session.css";
import "./styles/demo-now.css";
import "./styles/paper-now.css";
import "./styles/live-now.css";
import "./styles/demo-portfolio.css";
import "./styles/paper-portfolio.css";
import "./styles/live-portfolio.css";
import "./styles/demo-workspace.css";
import "./styles/paper-workspace.css";
import "./styles/live-workspace.css";
import "./styles/demo-explore.css";
import "./styles/paper-explore.css";
import "./styles/live-explore.css";
import "./styles/demo-research.css";
import "./styles/paper-research.css";
import "./styles/live-research.css";
import "./styles/demo-discover.css";
import "./styles/paper-discover.css";
import "./styles/live-discover.css";
import "./styles/workspace-module-mode.css";
import "./styles/shared-ui.css";
import "./styles/operator-control.css";

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
const ModeSqueezeWorkspaceRoute = lazy(() =>
  import("./components/squeeze/ModeSqueezeWorkspaceRoute").then((module) => ({
    default: module.ModeSqueezeWorkspaceRoute,
  })),
);
const ModeOrderFlowWorkspaceRoute = lazy(() =>
  import("./components/orderflow/ModeOrderFlowWorkspaceRoute").then((module) => ({
    default: module.ModeOrderFlowWorkspaceRoute,
  })),
);
const ModeOptionsWorkspaceRoute = lazy(() =>
  import("./components/options/ModeOptionsWorkspaceRoute").then((module) => ({
    default: module.ModeOptionsWorkspaceRoute,
  })),
);
const ModeLargeTransactionsWorkspaceRoute = lazy(() =>
  import("./components/largetransactions/ModeLargeTransactionsWorkspaceRoute").then((module) => ({
    default: module.ModeLargeTransactionsWorkspaceRoute,
  })),
);
const ModeOrderBookWorkspaceRoute = lazy(() =>
  import("./components/orderbook/ModeOrderBookWorkspaceRoute").then((module) => ({
    default: module.ModeOrderBookWorkspaceRoute,
  })),
);
const ModeFuturesWorkspaceRoute = lazy(() =>
  import("./components/futures/ModeFuturesWorkspaceRoute").then((module) => ({
    default: module.ModeFuturesWorkspaceRoute,
  })),
);
const ModeCatalystWorkspaceRoute = lazy(() =>
  import("./components/catalyst/ModeCatalystWorkspaceRoute").then((module) => ({
    default: module.ModeCatalystWorkspaceRoute,
  })),
);
const ModeFundEtfWorkspaceRoute = lazy(() =>
  import("./components/fundetf/ModeFundEtfWorkspaceRoute").then((module) => ({
    default: module.ModeFundEtfWorkspaceRoute,
  })),
);
const ModeDisclosureWorkspaceRoute = lazy(() =>
  import("./components/disclosure/ModeDisclosureWorkspaceRoute").then((module) => ({
    default: module.ModeDisclosureWorkspaceRoute,
  })),
);
const ModeInstitutionalFlowWorkspaceRoute = lazy(() =>
  import("./components/institutional/ModeInstitutionalFlowWorkspaceRoute").then((module) => ({
    default: module.ModeInstitutionalFlowWorkspaceRoute,
  })),
);
const OperatorSettingsPage = lazy(() =>
  import("./components/OperatorSettingsPage").then((module) => ({
    default: module.OperatorSettingsPage,
  })),
);
const OperatorControlCenterPage = lazy(() =>
  import("./components/OperatorControlCenterPage").then((module) => ({
    default: module.OperatorControlCenterPage,
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

type WorkstationShellProps = {
  mode: Mode;
  onSwitchMode: () => void;
};

export function WorkstationShell({ mode, onSwitchMode }: WorkstationShellProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [drawerPayload, setDrawerPayload] = useState<Record<string, unknown> | null>(null);
  const [inspectorPayload, setInspectorPayload] = useState<Record<string, unknown> | null>(null);
  const [inspectorTab, setInspectorTab] = useState<string | null>(null);
  const [cursorIndex, setCursorIndex] = useState(0);
  const [maxIndex, setMaxIndex] = useState(0);
  const [scrubState, setScrubState] = useState<ScrubState>("idle");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [selectionRef, setSelectionRef] = useState<string | null>(null);

  const contextQuery = useContextQuery();
  const attentionQuery = useAttentionQuery();
  const replaySessionQuery = useReplaySessionQuery();
  const assistantStatusQuery = useAssistantStatusQuery(assistantOpen);
  const assistantMessagesQuery = useAssistantMessagesQuery(conversationId);
  const contextState = contextQuery.isLoading
    ? "loading"
    : contextQuery.error || !contextQuery.data
      ? "error"
      : "ready";
  const modeEvaluation = evaluateModeContext(mode, contextQuery.data?.as_of_context);
  const paperActionsPermitted =
    contextState === "ready" && modeEvaluation.paperActionsPermitted;
  const auth = useOptionalAuth();
  const operatorPaperSubmitPermitted =
    paperActionsPermitted && (auth?.permitsCapability("paper.order.submit") ?? true);
  const attentionState = attentionQuery.isLoading
    ? "loading"
    : attentionQuery.error || !attentionQuery.data
      ? "error"
      : "ready";
  const replayState = replaySessionQuery.isLoading
    ? "loading"
    : replaySessionQuery.error || !replaySessionQuery.data
      ? "error"
      : "ready";

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
    setScrubState("pending");
    try {
      await api.scrubReplay(index);
      setCursorIndex(index);
      setMaxIndex(Math.max(maxIndex, index));
      await refreshAll();
      setScrubState("idle");
    } catch {
      setScrubState("error");
    }
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

  const returnToLauncher = () => {
    navigate("/", { replace: true });
    onSwitchMode();
  };

  return (
    <div className="app-shell">
      <ModeEnvironmentBar
        mode={mode}
        context={contextQuery.data?.as_of_context}
        contextState={contextState}
        onSwitchMode={returnToLauncher}
      />
      <NavShell mode={mode} />
      {contextQuery.data ? (
        <ContextBar context={contextQuery.data} />
      ) : (
        <div className="context-bar context-bar-unavailable" aria-hidden="true">
          Backend context is not available.
        </div>
      )}
      <StartupRecoveryBanner />
      <div className="app-body">
        <main className="main-content">
          <LazyBoundary>
            <Routes>
            <Route
              path="/"
              element={
                <ModeNowRoute
                  mode={mode}
                  paperActionsPermitted={operatorPaperSubmitPermitted}
                  items={attentionQuery.data?.items ?? []}
                  tierSummary={attentionQuery.data?.tier_summary}
                  attentionState={attentionState}
                  replayState={replayState}
                  cursorIndex={cursorIndex}
                  eventCount={replaySessionQuery.data?.event_count}
                  scrubState={scrubState}
                  onScrub={(index) => {
                    void scrub(index);
                  }}
                  onOpenTimeline={() => navigate(`/workspace/${ADMITTED_REPLAY_INSTRUMENT_ID}`)}
                  onWhy={openExplain}
                  onExplain={openExplain}
                  onInspect={openInspect}
                  onOpenWorkspace={(item) => {
                    if (item.instrument_id) navigate(`/workspace/${item.instrument_id}`);
                  }}
                />
              }
            />
            <Route
              path="/explore"
              element={<ModeExploreRoute mode={mode} onExplain={openExplainRef} />}
            />
            <Route path="/discover" element={<ModeDiscoverRoute mode={mode} />} />
            <Route path="/workspace" element={<WorkspaceIndex />} />
            <Route
              path="/workspace/:symbol"
              element={
                <WorkspaceRoute
                  mode={mode}
                  paperActionsPermitted={operatorPaperSubmitPermitted}
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
                <ModeSqueezeWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                  onOpenHistory={openSqueezeHistory}
                />
              }
            />
            <Route
              path="/workspace/:symbol/order-flow"
              element={
                <ModeOrderFlowWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/order-book"
              element={
                <ModeOrderBookWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/futures"
              element={
                <ModeFuturesWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/catalyst"
              element={
                <ModeCatalystWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/fund-etf"
              element={
                <ModeFundEtfWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/options"
              element={
                <ModeOptionsWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/large-transactions"
              element={
                <ModeLargeTransactionsWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/disclosure"
              element={
                <ModeDisclosureWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route
              path="/workspace/:symbol/institutional-flow"
              element={
                <ModeInstitutionalFlowWorkspaceRoute
                  mode={mode}
                  onExplain={openExplainRef}
                  onInspect={openInspectRef}
                />
              }
            />
            <Route path="/research" element={<ModeResearchRoute mode={mode} />} />
            <Route
              path="/portfolio"
              element={
                <ModePortfolioRoute
                  mode={mode}
                  paperActionsPermitted={operatorPaperSubmitPermitted}
                />
              }
            />
            <Route
              path="/live-canary"
              element={<LiveCanaryControlPlanePage mode={mode} />}
            />
            <Route path="/settings" element={<OperatorSettingsPage mode={mode} />} />
            <Route path="/control" element={<OperatorControlCenterPage />} />
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
    <AuthProvider>
      <OperatorLoginGate>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ApplicationBootstrap>
              {(mode, switchMode) => <WorkstationShell mode={mode} onSwitchMode={switchMode} />}
            </ApplicationBootstrap>
          </BrowserRouter>
        </QueryClientProvider>
      </OperatorLoginGate>
    </AuthProvider>
  );
}

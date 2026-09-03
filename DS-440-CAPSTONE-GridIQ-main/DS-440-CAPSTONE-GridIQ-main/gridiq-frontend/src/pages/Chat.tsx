import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "../ui/primitives/Card";
import { Button } from "../ui/primitives/Button";
import { Input } from "../ui/primitives/Input";
import * as api from "../lib/api/endpoints";
import type { ChatMessage } from "../types";
import axios from "axios";
import { FootballMascot } from "../ui/FootballMascot";

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[min(80%,52rem)] rounded-2xl bg-gray-900 p-3 text-sm text-white">
          <div className="whitespace-pre-wrap">{msg.content}</div>
          {msg.citations?.length ? (
            <div className="mt-2 space-y-1 text-xs opacity-90">
              <div className="font-medium">Citations</div>
              {msg.citations.map((c, i) => (
                <div key={i} className="rounded-xl bg-white/10 px-2 py-1">
                  {c.title}
                  {c.snippet ? <div className="mt-0.5 opacity-80">{c.snippet}</div> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start gap-2">
      <div className="shrink-0 pt-1">
        <FootballMascot className="drop-shadow-sm" />
      </div>
      <div className="max-w-[min(80%,52rem)] rounded-2xl bg-gray-100 p-3 text-sm">
        <div className="whitespace-pre-wrap">{msg.content}</div>
        {msg.citations?.length ? (
          <div className="mt-2 space-y-1 text-xs opacity-90">
            <div className="font-medium">Citations</div>
            {msg.citations.map((c, i) => (
              <div key={i} className="rounded-xl bg-white/10 px-2 py-1">
                {c.title}
                {c.snippet ? <div className="mt-0.5 opacity-80">{c.snippet}</div> : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function Chat() {
  const threadIdStorageKey = useMemo(() => {
    const rawUser = localStorage.getItem("gridiq_user");
    if (!rawUser) return "gridiq_thread_active";
    try {
      const parsed = JSON.parse(rawUser) as { id?: string };
      return `gridiq_thread_active_${parsed.id ?? "anon"}`;
    } catch {
      return "gridiq_thread_active";
    }
  }, []);
  const [threadId, setThreadId] = useState<string | null>(() => localStorage.getItem(threadIdStorageKey));
  const qc = useQueryClient();

  const {
    data: messages = [],
    isLoading: isLoadingMessages,
    isError: isLoadError,
    error: loadError,
  } = useQuery({
    queryKey: ["thread", threadId],
    enabled: !!threadId,
    queryFn: () => api.listThreadMessages(threadId as string),
    refetchOnWindowFocus: false,
  });

  const send = useMutation({
    mutationFn: (content: string) => api.sendMessage(threadId, content),
    onSuccess: ({ conversationId }) => {
      setThreadId(conversationId);
      localStorage.setItem(threadIdStorageKey, conversationId);
      qc.invalidateQueries({ queryKey: ["thread", conversationId] });
    },
  });

  const [text, setText] = useState("");

  useEffect(() => {
    // Optional: setup streaming (SSE/WebSocket) once backend supports it.
  }, []);

  const mocksOn = api.mocksEnabled();

  return (
    <div className="space-y-4">
      <div>
        <div className="text-2xl font-semibold tracking-tight text-slate-900">Chat</div>
        <div className="mt-1 text-sm text-slate-600">
          AI coach with your conversation history. Each request includes a compact{" "}
          <span className="font-medium text-slate-800">nflverse</span> schedule snapshot (scores, PPG leaders, team
          abbreviations you mention) so answers can reference real season data when relevant.
        </div>
      </div>

      {mocksOn ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <span className="font-medium">Local mocks are on.</span> Chat never hits your backend or Gemini—replies are fake.
          Turn off <span className="font-medium">Settings → Use local mocks</span>, make sure the API is running on port 8000,
          then sign in again.
        </div>
      ) : null}

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            variant="ghost"
            type="button"
            onClick={() => {
              localStorage.removeItem(threadIdStorageKey);
              setThreadId(null);
              void qc.invalidateQueries({ queryKey: ["thread"] });
            }}
          >
            New conversation
          </Button>
        </div>
        <p className="rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-2 text-xs text-amber-950">
          <span className="font-medium">Tip:</span> use <strong>New conversation</strong> if replies look stale. Full
          reset: stop the API, delete <code className="rounded bg-white/80 px-1">gridiq-backend/gridiq.db</code>, restart.
        </p>
        <div className="h-[min(70vh,calc(100vh-14rem))] space-y-2 overflow-auto rounded-xl border border-white/60 bg-white/80 p-3">
          {isLoadError ? (
            <div className="text-sm text-red-700">
              {axios.isAxiosError(loadError)
                ? (typeof loadError.response?.data?.detail === "string"
                    ? loadError.response.data.detail
                    : loadError.message)
                : (loadError as Error)?.message ?? "Failed to load conversation"}
            </div>
          ) : isLoadingMessages ? (
            <div className="text-sm text-gray-500">Loading conversation...</div>
          ) : messages.length === 0 ? (
            <div className="text-sm text-gray-500">
              No messages yet. Ask something like: “Explain Cover 3 vs Quarters for 3x1 formations.”
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}
        </div>

        {send.isPending ? (
          <p className="text-xs text-gray-500">Waiting for the model (first reply can take 20–90 seconds)…</p>
        ) : null}

        {send.isError ? (
          <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">
            {(() => {
              const err = send.error;
              if (axios.isAxiosError(err)) {
                const detail = err.response?.data?.detail;
                if (typeof detail === "string") return detail;
                if (err.code === "ECONNABORTED") {
                  return "Request timed out. If the backend is slow or cold-starting Gemini, try again—or we can raise the timeout further.";
                }
                return err.message;
              }
              return err instanceof Error ? err.message : "Failed to send message";
            })()}
          </div>
        ) : null}

        <div className="flex gap-2">
          <Input
            placeholder="Type a question…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (!text.trim()) return;
                send.mutate(text.trim());
                setText("");
              }
            }}
          />
          <Button
            disabled={send.isPending}
            onClick={() => {
              if (!text.trim()) return;
              send.mutate(text.trim());
              setText("");
            }}
          >
            Send
          </Button>
        </div>
      </Card>
    </div>
  );
}

import { z } from "zod";
import axios from "axios";
import { api } from "./client";
import type {
  ChatMessage,
  Game,
  NflverseGameSummary,
  NflversePlay,
  NflverseScheduleGame,
  Play,
  User,
} from "../../types";

// Mocks: build-time VITE_USE_MOCKS=true, or Settings → "Use local mocks" (localStorage).
export function mocksEnabled(): boolean {
  if (import.meta.env.VITE_USE_MOCKS === "true") return true;
  return localStorage.getItem("gridiq_use_mocks") === "true";
}

function useMocks() {
  return mocksEnabled();
}

/** Mock login stores this string; it is not a real JWT and must not be sent to the API. */
export const MOCK_AUTH_TOKEN = "dev-token";

const getThreadKey = (threadId: string) => `gridiq_thread_${threadId}`;

const clearThreadMessages = (threadId: string) => {
  if (!useMocks()) return;
  sessionStorage.removeItem(getThreadKey(threadId));
};

export const clearAllThreadMessages = () => {
  if (!useMocks()) return;
  Object.keys(sessionStorage)
    .filter((k) => k.startsWith("gridiq_thread_"))
    .forEach((k) => sessionStorage.removeItem(k));
};

// Zod schemas (runtime validation)
const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  displayName: z.string(),
  role: z.enum(["coach", "player", "analyst", "admin"]),
});

const ChatMessageSchema = z.object({
  id: z.string(),
  threadId: z.string(),
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
  createdAt: z.string(),
  citations: z
    .array(z.object({ title: z.string(), url: z.string().optional(), snippet: z.string().optional() }))
    .optional(),
});

export async function login(email: string, password: string): Promise<{ token: string; user: User }> {
  if (useMocks()) {
    if (!email || !password) throw new Error("Missing credentials");
    const user: User = { id: "u_1", email, displayName: "Coach", role: "coach" };
    const token = MOCK_AUTH_TOKEN;
    return { token, user };
  }

  const resp = await api.post("/api/auth/login", { email, password });
  return resp.data;
}

export async function register(email: string, password: string): Promise<{ token: string; user: User }> {
  if (useMocks()) {
    if (!email || !password) throw new Error("Missing credentials");
    if (password.length < 8) throw new Error("Password must be at least 8 characters");
    const user: User = { id: "u_1", email, displayName: "Coach", role: "coach" };
    const token = MOCK_AUTH_TOKEN;
    return { token, user };
  }

  const resp = await api.post("/api/auth/register", { email, password });
  return resp.data;
}

export async function me(): Promise<User> {
  if (useMocks()) {
    const raw = localStorage.getItem("gridiq_user");
    if (!raw) throw new Error("Not authenticated");
    const parsed = JSON.parse(raw);
    return UserSchema.parse(parsed);
  }

  const resp = await api.get("/api/users/me");
  return UserSchema.parse(resp.data);
}

// sample fixtures used when mocks are enabled
const _mockGames: Game[] = [
  {
    id: "g_1",
    season: 2026,
    week: 5,
    homeTeam: "Penn State",
    awayTeam: "Ohio State",
    kickoff: new Date("2026-10-03T19:00:00Z").toISOString(),
  },
  {
    id: "g_2",
    season: 2026,
    week: 6,
    homeTeam: "Michigan",
    awayTeam: "Michigan State",
    kickoff: new Date("2026-10-10T19:00:00Z").toISOString(),
  },
];

const _mockPlays: Play[] = [
  {
    id: "p_1",
    gameId: "g_1",
    offense: "Penn State",
    defense: "Ohio State",
    down: 3,
    yardsToGo: 7,
    yardLine: 45,
    playType: "Pass",
    description: "3rd and 7, shotgun, quick out to WR",
  },
  {
    id: "p_2",
    gameId: "g_1",
    offense: "Penn State",
    defense: "Ohio State",
    down: 1,
    yardsToGo: 10,
    yardLine: 20,
    playType: "Run",
    description: "Inside zone left for 4 yards",
  },
];

export async function listGames(): Promise<Game[]> {
  if (useMocks()) {
    // allow a little artificial latency so the UI shows loading states
    await new Promise((r) => setTimeout(r, 250));
    return _mockGames;
  }

  const resp = await api.get("/api/games");
  return resp.data;
}

export async function listPlays(gameId: string): Promise<Play[]> {
  if (useMocks()) {
    await new Promise((r) => setTimeout(r, 250));
    return _mockPlays.filter((p) => p.gameId === gameId);
  }

  const resp = await api.get(`/api/games/${gameId}/plays`);
  return resp.data;
}

const NFLVERSE_SCHEDULE_TIMEOUT_MS = 60_000;
const NFLVERSE_PBP_TIMEOUT_MS = 120_000;

export async function fetchNflverseSchedule(
  season: number,
  opts?: { week?: number; gameType?: string },
): Promise<NflverseScheduleGame[]> {
  const resp = await api.get("/api/games/nflverse/schedule", {
    timeout: NFLVERSE_SCHEDULE_TIMEOUT_MS,
    params: {
      season,
      ...(opts?.week != null ? { week: opts.week } : {}),
      ...(opts?.gameType != null ? { game_type: opts.gameType } : {}),
    },
  });
  return resp.data.games as NflverseScheduleGame[];
}

export async function fetchNflverseGamePlays(gameId: string): Promise<NflversePlay[]> {
  const resp = await api.get(`/api/games/nflverse/games/${encodeURIComponent(gameId)}/plays`, {
    timeout: NFLVERSE_PBP_TIMEOUT_MS,
  });
  return resp.data.plays as NflversePlay[];
}

export async function fetchNflverseGameSummary(gameId: string): Promise<NflverseGameSummary> {
  const resp = await api.get(`/api/games/nflverse/games/${encodeURIComponent(gameId)}/summary`, {
    timeout: NFLVERSE_PBP_TIMEOUT_MS,
  });
  const d = resp.data;
  return {
    gameId: d.gameId as string,
    homeTeam: d.homeTeam as string,
    awayTeam: d.awayTeam as string,
    homeScore: d.homeScore ?? null,
    awayScore: d.awayScore ?? null,
    quarterlyScores: d.quarterlyScores ?? [],
    highlights: d.highlights ?? [],
    topRusherByTeam: d.topRusherByTeam ?? { home: null, away: null },
    topReceiverByTeam: d.topReceiverByTeam ?? { home: null, away: null },
    topPasserByTeam: d.topPasserByTeam ?? { home: null, away: null },
    fieldGoalsByTeam: d.fieldGoalsByTeam ?? {
      home: { made: 0, missed: 0, attempted: 0 },
      away: { made: 0, missed: 0, attempted: 0 },
    },
    fumblesByTeam: d.fumblesByTeam ?? {
      home: { playsWithFumble: 0, lost: 0 },
      away: { playsWithFumble: 0, lost: 0 },
    },
  };
}


export async function listThreadMessages(threadId: string): Promise<ChatMessage[]> {
  if (useMocks()) {
    const raw = sessionStorage.getItem(getThreadKey(threadId));
    return raw ? z.array(ChatMessageSchema).parse(JSON.parse(raw)) : [];
  }

  try {
    const resp = await api.get(`/api/chat/conversations/${threadId}`);
    const conversation = resp.data as { messages: any[] };

    return (conversation.messages || []).map((m) =>
      ChatMessageSchema.parse({
        id: m.id,
        threadId,
        role: m.role,
        content: m.content,
        createdAt: new Date(m.created_at).toISOString(),
        citations: m.citations,
      }),
    );
  } catch (e) {
    // Treat missing conversation as an empty thread so stale local ids don't break chat.
    if (axios.isAxiosError(e) && e.response?.status === 404) return [];
    throw e;
  }
}

export async function sendMessage(threadId: string | null, content: string): Promise<{ conversationId: string }> {
  if (useMocks()) {
    const conversationId = threadId ?? `conv_${crypto.randomUUID()}`;
    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      threadId: conversationId,
      role: "user",
      content,
      createdAt: new Date().toISOString(),
    };
    const reply: ChatMessage = {
      id: crypto.randomUUID(),
      threadId: conversationId,
      role: "assistant",
      content:
        "Mock response: backend AI is disabled in local mocks. Disable mocks in Settings to use the real API.",
      createdAt: new Date().toISOString(),
    };
    const current = await listThreadMessages(conversationId);
    const next = [...current, msg, reply];
    sessionStorage.setItem(getThreadKey(conversationId), JSON.stringify(next));
    return { conversationId };
  }

  // Gemini first calls often exceed the default 15s axios timeout.
  const resp = await api.post(
    `/api/chat/chat`,
    {
      conversation_id: threadId ?? undefined,
      message: content,
    },
    { timeout: 120_000 },
  );
  return { conversationId: resp.data.conversation_id as string };
}

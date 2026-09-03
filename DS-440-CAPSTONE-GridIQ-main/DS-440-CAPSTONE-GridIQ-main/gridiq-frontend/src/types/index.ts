export type Role = "coach" | "player" | "analyst" | "admin";

export type User = {
  id: string;
  email: string;
  displayName: string;
  role: Role;
};

export type ChatMessage = {
  id: string;
  threadId: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string; // ISO
  citations?: Array<{ title: string; url?: string; snippet?: string }>;
};

export type Game = {
  id: string;
  season: number;
  week: number;
  homeTeam: string;
  awayTeam: string;
  kickoff: string; // ISO
};

export type Play = {
  id: string;
  gameId: string;
  offense: string;
  defense: string;
  down: number;
  yardsToGo: number;
  yardLine: number; // 0..100
  playType: string;
  description: string;
};

/** nflverse schedule row (camelCase from API). */
export type NflverseScheduleGame = {
  gameId: string;
  season: number;
  gameType: string;
  week: number;
  gameday: string | null;
  weekday: string | null;
  gametime: string | null;
  awayTeam: string;
  homeTeam: string;
  awayScore: number | null;
  homeScore: number | null;
  stadium: string | null;
};

/** nflverse play-by-play row (camelCase from API). */
export type NflversePlay = {
  id: string;
  gameId: string;
  quarter: number | null;
  down: number | null;
  yardsToGo: number | null;
  playType: string | null;
  description: string | null;
  offense: string | null;
  defense: string | null;
  epa: number | null;
  yardsGained: number | null;
};

export type NflversePlayerStatTriple = {
  name: string;
  yards: number;
  carries?: number;
  receptions?: number;
  touchdowns?: number;
  interceptions?: number;
};

export type NflverseFgTotals = {
  made: number;
  missed: number;
  attempted: number;
};

export type NflverseFumbleTotals = {
  playsWithFumble: number;
  lost: number;
};

export type NflverseQuarterScore = {
  quarter: number;
  homePoints: number;
  awayPoints: number;
  homeCumulative: number;
  awayCumulative: number;
};

export type NflverseScoringHighlight = {
  quarter: number | null;
  playType: string | null;
  team: string | null;
  player: string | null;
  description: string | null;
};

/** Aggregated game summary from `/nflverse/games/{id}/summary`. */
export type NflverseGameSummary = {
  gameId: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number | null;
  awayScore: number | null;
  quarterlyScores: NflverseQuarterScore[];
  highlights: NflverseScoringHighlight[];
  topRusherByTeam: { home: NflversePlayerStatTriple | null; away: NflversePlayerStatTriple | null };
  topReceiverByTeam: { home: NflversePlayerStatTriple | null; away: NflversePlayerStatTriple | null };
  topPasserByTeam: { home: NflversePlayerStatTriple | null; away: NflversePlayerStatTriple | null };
  fieldGoalsByTeam: { home: NflverseFgTotals; away: NflverseFgTotals };
  fumblesByTeam: { home: NflverseFumbleTotals; away: NflverseFumbleTotals };
};

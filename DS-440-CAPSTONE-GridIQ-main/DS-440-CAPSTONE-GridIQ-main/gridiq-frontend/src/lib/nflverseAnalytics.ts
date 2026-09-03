import type { NflversePlay, NflverseScheduleGame } from "../types";

export type TeamSeasonAgg = {
  team: string;
  gamesPlayed: number;
  wins: number;
  pf: number;
  pa: number;
  avgPf: number;
  avgPa: number;
};

export function aggregateTeamSeason(games: NflverseScheduleGame[]): {
  teams: TeamSeasonAgg[];
  leagueAvgCombined: number | null;
  completedWithScore: number;
} {
  const byTeam = new Map<string, { gp: number; w: number; pf: number; pa: number }>();

  const add = (team: string, pf: number, pa: number, win: boolean) => {
    const cur = byTeam.get(team) ?? { gp: 0, w: 0, pf: 0, pa: 0 };
    cur.gp += 1;
    cur.pf += pf;
    cur.pa += pa;
    if (win) cur.w += 1;
    byTeam.set(team, cur);
  };

  let combinedSum = 0;
  let combinedN = 0;

  for (const g of games) {
    if (g.awayScore == null || g.homeScore == null) continue;
    const as = Number(g.awayScore);
    const hs = Number(g.homeScore);
    combinedSum += as + hs;
    combinedN += 1;
    add(g.awayTeam, as, hs, as > hs);
    add(g.homeTeam, hs, as, hs > as);
  }

  const teams: TeamSeasonAgg[] = [...byTeam.entries()].map(([team, x]) => ({
    team,
    gamesPlayed: x.gp,
    wins: x.w,
    pf: x.pf,
    pa: x.pa,
    avgPf: x.gp ? x.pf / x.gp : 0,
    avgPa: x.gp ? x.pa / x.gp : 0,
  }));
  teams.sort((a, b) => b.avgPf - a.avgPf);

  return {
    teams,
    leagueAvgCombined: combinedN ? combinedSum / combinedN : null,
    completedWithScore: combinedN,
  };
}

export function teamPointsByWeek(
  games: NflverseScheduleGame[],
  team: string,
): { week: number; points: number }[] {
  return games
    .filter(
      (g) => (g.awayTeam === team || g.homeTeam === team) && g.awayScore != null && g.homeScore != null,
    )
    .map((g) => ({
      week: g.week,
      points: g.homeTeam === team ? Number(g.homeScore) : Number(g.awayScore),
    }))
    .sort((a, b) => a.week - b.week);
}

export function computeEpaByQuarter(
  plays: NflversePlay[],
  away: string,
  home: string,
): { quarter: string; awayEpa: number; homeEpa: number }[] {
  const byQ = new Map<number, { away: number; home: number }>();
  for (const p of plays) {
    if (p.quarter == null || p.epa == null || !p.offense) continue;
    const row = byQ.get(p.quarter) ?? { away: 0, home: 0 };
    if (p.offense === away) row.away += p.epa;
    else if (p.offense === home) row.home += p.epa;
    byQ.set(p.quarter, row);
  }
  return [...byQ.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([q, v]) => ({
      quarter: `Q${q}`,
      awayEpa: Math.round(v.away * 1000) / 1000,
      homeEpa: Math.round(v.home * 1000) / 1000,
    }));
}

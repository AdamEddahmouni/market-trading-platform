import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { NflversePlay, NflverseScheduleGame } from "../types";
import { aggregateTeamSeason, computeEpaByQuarter, teamPointsByWeek } from "../lib/nflverseAnalytics";

const CR = {
  turf: "#1b5e3a",
  gold: "#d4a817",
  grid: "#cbd5e1",
};

type Props = {
  scheduleGames: NflverseScheduleGame[];
  playsPerWeek: [number, number][];
  chartTeam: string;
  onChartTeamChange: (team: string) => void;
  /** When a game is selected, matchup EPA uses loaded plays (sample capped on API). */
  plays: NflversePlay[];
  matchupAway: string | null;
  matchupHome: string | null;
};

export function DashboardCharts({
  scheduleGames,
  playsPerWeek,
  chartTeam,
  onChartTeamChange,
  plays,
  matchupAway,
  matchupHome,
}: Props) {
  const { teams, leagueAvgCombined, completedWithScore } = useMemo(
    () => aggregateTeamSeason(scheduleGames),
    [scheduleGames],
  );

  const topOffenses = useMemo(() => {
    return teams.filter((t) => t.gamesPlayed >= 2).slice(0, 12);
  }, [teams]);

  const weekLineData = useMemo(() => {
    if (!chartTeam) return [];
    return teamPointsByWeek(scheduleGames, chartTeam);
  }, [scheduleGames, chartTeam]);

  const epaQuarterData = useMemo(() => {
    if (!matchupAway || !matchupHome || !plays.length) return [];
    return computeEpaByQuarter(plays, matchupAway, matchupHome);
  }, [plays, matchupAway, matchupHome]);

  const gamesPerWeekChart = useMemo(
    () => playsPerWeek.map(([w, c]) => ({ week: `W${w}`, games: c })),
    [playsPerWeek],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-800">Stats & charts</h2>
        {leagueAvgCombined != null ? (
          <p className="text-xs text-slate-600">
            League avg combined score:{" "}
            <span className="font-semibold tabular-nums">{leagueAvgCombined.toFixed(1)}</span> pts
            <span className="text-slate-500"> · {completedWithScore} finished games in view</span>
          </p>
        ) : (
          <p className="text-xs text-slate-500">No completed scores for this filter yet.</p>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-medium text-slate-600">League — points per game (offense)</div>
          <div className="h-56 w-full rounded-xl border border-white/60 bg-white/50 p-2">
            {topOffenses.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topOffenses} layout="vertical" margin={{ left: 8, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CR.grid} />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="team" width={40} tick={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(value) =>
                      typeof value === "number" ? [`${value.toFixed(1)}`, "PPG"] : [String(value), "PPG"]
                    }
                  />
                  <Bar dataKey="avgPf" name="PPG" fill={CR.turf} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-500">No team data.</div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs font-medium text-slate-600">Schedule density — games per week</div>
          <div className="h-56 w-full rounded-xl border border-white/60 bg-white/50 p-2">
            {gamesPerWeekChart.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={gamesPerWeekChart} margin={{ bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CR.grid} />
                  <XAxis dataKey="week" tick={{ fontSize: 9 }} interval={0} angle={-35} textAnchor="end" height={48} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="games" fill={CR.gold} name="Games" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-600">Team — points by week</span>
            <select
              className="rounded-lg border border-slate-300/80 bg-white/90 px-2 py-1 text-xs"
              value={chartTeam}
              onChange={(e) => onChartTeamChange(e.target.value)}
            >
              {!teams.length ? (
                <option value="">
                  —
                </option>
              ) : null}
              {teams.map((t) => (
                <option key={t.team} value={t.team}>
                  {t.team}
                </option>
              ))}
            </select>
          </div>
          <div className="h-56 w-full rounded-xl border border-white/60 bg-white/50 p-2">
            {weekLineData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={weekLineData} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CR.grid} />
                  <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="points" stroke={CR.turf} strokeWidth={2} dot={false} name="Points" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-500">
                Pick a team with finished games.
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs font-medium text-slate-600">
            Matchup — total EPA by quarter (loaded play sample)
          </div>
          <div className="h-56 w-full rounded-xl border border-white/60 bg-white/50 p-2">
            {epaQuarterData.length && matchupAway && matchupHome ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={epaQuarterData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CR.grid} />
                  <XAxis dataKey="quarter" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="awayEpa" name={matchupAway} fill={CR.turf} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="homeEpa" name={matchupHome} fill={CR.gold} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center px-4 text-center text-xs text-slate-500">
                Select a game and load plays. EPA sums reflect the first chunk of plays returned by the API.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

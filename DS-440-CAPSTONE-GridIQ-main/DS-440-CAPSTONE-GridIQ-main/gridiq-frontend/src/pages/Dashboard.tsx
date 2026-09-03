import { Card } from "../ui/primitives/Card";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../lib/api/endpoints";
import { aggregateTeamSeason } from "../lib/nflverseAnalytics";
import type { NflverseGameSummary } from "../types";
import { DashboardCharts } from "./DashboardCharts";

const fieldSelect =
  "rounded-lg border border-slate-300/80 bg-white/90 p-2 text-sm text-slate-900 shadow-sm";

function fmtScore(v: number | null | undefined, fallback: number | null | undefined): string {
  if (v != null && !Number.isNaN(Number(v))) return String(Number(v));
  if (fallback != null && !Number.isNaN(Number(fallback))) return String(Number(fallback));
  return "—";
}

const SEASON_CHOICES = [2025];

function StatColumn({
  label,
  side,
  s,
}: {
  label: string;
  side: "home" | "away";
  s: NflverseGameSummary;
}) {
  const rush = s.topRusherByTeam[side];
  const rec = s.topReceiverByTeam[side];
  const pass = s.topPasserByTeam[side];
  const fg = s.fieldGoalsByTeam[side];
  const fum = s.fumblesByTeam[side];

  const line = (title: string, body: string) => (
    <div className="mt-2 text-xs">
      <div className="font-medium text-gray-600">{title}</div>
      <div className="text-gray-900">{body}</div>
    </div>
  );

  const rusherTxt = rush
    ? `${rush.name} — ${rush.yards} yd, ${rush.carries ?? 0} att`
    : "—";
  const recTxt = rec
    ? `${rec.name} — ${rec.yards} yd, ${rec.receptions ?? 0} rec`
    : "—";
  const passTxt = pass
    ? `${pass.name} — ${pass.yards} yd, ${pass.touchdowns ?? 0} TD, ${pass.interceptions ?? 0} INT`
    : "—";
  const fgTxt = `${fg.made}/${fg.attempted} made (${fg.missed} missed/blocked)`;
  const fumTxt = `${fum.playsWithFumble} fumble plays, ${fum.lost} lost`;

  return (
    <div className="rounded-lg border border-white/60 bg-white/70 p-3 shadow-sm">
      <div className="border-b border-slate-200/80 pb-2 text-xs font-semibold text-slate-800">{label}</div>
      {line("Top rusher", rusherTxt)}
      {line("Top WR (yards / catches)", recTxt)}
      {line("Passing (yards · TD · INT)", passTxt)}
      {line("Field goals", fgTxt)}
      {line("Fumbles", fumTxt)}
    </div>
  );
}

export default function Dashboard() {
  const [season, setSeason] = useState(2025);
  const [weekFilter, setWeekFilter] = useState<number | "">("");
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [chartTeam, setChartTeam] = useState("");

  const {
    data: scheduleGames = [],
    isLoading: loadingSchedule,
    isError: scheduleError,
    error: scheduleErr,
  } = useQuery({
    queryKey: ["nflverse-schedule", season, weekFilter],
    queryFn: () =>
      api.fetchNflverseSchedule(season, {
        week: weekFilter === "" ? undefined : weekFilter,
        gameType: "REG",
      }),
  });

  const {
    data: plays = [],
    isLoading: loadingPlays,
    isError: playsError,
    error: playsErr,
  } = useQuery({
    queryKey: ["nflverse-plays", selectedGameId],
    queryFn: () => (selectedGameId ? api.fetchNflverseGamePlays(selectedGameId) : Promise.resolve([])),
    enabled: !!selectedGameId,
  });

  const {
    data: gameSummary,
    isLoading: loadingSummary,
    isError: summaryError,
    error: summaryErr,
  } = useQuery({
    queryKey: ["nflverse-summary", selectedGameId],
    queryFn: () => api.fetchNflverseGameSummary(selectedGameId as string),
    enabled: !!selectedGameId,
  });

  const gamesByWeek = useMemo(() => {
    const map = new Map<number, typeof scheduleGames>();
    for (const g of scheduleGames) {
      const w = g.week;
      if (!map.has(w)) map.set(w, []);
      map.get(w)!.push(g);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [scheduleGames]);

  const playsPerWeek = useMemo(() => {
    const counts = new Map<number, number>();
    for (const g of scheduleGames) {
      counts.set(g.week, (counts.get(g.week) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => a[0] - b[0]);
  }, [scheduleGames]);

  const selectedGame = useMemo(
    () => scheduleGames.find((g) => g.gameId === selectedGameId) ?? null,
    [scheduleGames, selectedGameId],
  );

  const summaryScores = useMemo(() => {
    if (!gameSummary || !selectedGame) return null;
    return {
      away: fmtScore(gameSummary.awayScore, selectedGame.awayScore),
      home: fmtScore(gameSummary.homeScore, selectedGame.homeScore),
    };
  }, [gameSummary, selectedGame]);

  const teamAgg = useMemo(() => aggregateTeamSeason(scheduleGames), [scheduleGames]);

  useEffect(() => {
    setChartTeam((prev) => {
      const list = teamAgg.teams;
      if (prev && list.some((x) => x.team === prev)) return prev;
      return list[0]?.team ?? "";
    });
  }, [teamAgg]);

  return (
    <div className="space-y-4">
      <div>
        <div className="text-2xl font-semibold tracking-tight text-slate-900">Dashboard</div>
        <p className="mt-1 text-sm text-slate-600">
          NFL schedules, box scores, and play samples via{" "}
          <a className="font-medium underline" href="https://github.com/nflverse" target="_blank" rel="noreferrer">
            nflverse
          </a>{" "}
          (CC BY 4.0). First season load can take a moment while data caches.
        </p>
      </div>

      <Card className="mb-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="dash-season">
              Season
            </label>
            <select
              id="dash-season"
              className={fieldSelect}
              value={season}
              onChange={(e) => {
                setSeason(Number(e.target.value));
                setSelectedGameId(null);
              }}
            >
              {SEASON_CHOICES.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="dash-week">
              Week filter
            </label>
            <select
              id="dash-week"
              className={fieldSelect}
              value={weekFilter === "" ? "" : String(weekFilter)}
              onChange={(e) => {
                const v = e.target.value;
                setWeekFilter(v === "" ? "" : Number(v));
                setSelectedGameId(null);
              }}
            >
              <option value="">All weeks</option>
              {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
                <option key={w} value={w}>
                  Week {w}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium" htmlFor="dash-game">
            Game
          </label>
          <select
            id="dash-game"
            className={fieldSelect}
            value={selectedGameId ?? ""}
            onChange={(e) => setSelectedGameId(e.target.value || null)}
          >
            <option value="">— Select a game —</option>
            {gamesByWeek.map(([wk, games]) => (
              <optgroup key={wk} label={`Week ${wk}`}>
                {games.map((g) => (
                  <option key={g.gameId} value={g.gameId}>
                    {g.awayTeam} @ {g.homeTeam}
                    {g.gameday ? ` · ${g.gameday}` : ""}
                    {g.awayScore != null && g.homeScore != null
                      ? ` (${g.awayScore}–${g.homeScore})`
                      : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {loadingSchedule && <div className="text-xs text-gray-500">Loading schedule…</div>}
          {scheduleError && (
            <div className="text-xs text-red-600">
              {scheduleErr instanceof Error ? scheduleErr.message : "Could not load schedule."}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <DashboardCharts
          scheduleGames={scheduleGames}
          playsPerWeek={playsPerWeek}
          chartTeam={chartTeam}
          onChartTeamChange={setChartTeam}
          plays={plays}
          matchupAway={gameSummary?.awayTeam ?? selectedGame?.awayTeam ?? null}
          matchupHome={gameSummary?.homeTeam ?? selectedGame?.homeTeam ?? null}
        />
      </Card>

      {selectedGameId && selectedGame && (
        <Card className="space-y-4">
          <div>
            <div className="text-sm font-semibold text-slate-800">Game detail</div>
          </div>

          {loadingSummary ? (
            <div className="text-xs text-gray-500">Loading box score and player stats…</div>
          ) : summaryError ? (
            <div className="text-xs text-red-600">
              {summaryErr instanceof Error ? summaryErr.message : "Could not load game summary."}
            </div>
          ) : gameSummary && summaryScores ? (
            <>
              <div className="rounded-xl border border-gray-200 bg-gray-50/80 px-4 py-4">
                <div className="text-center text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                  Scoreboard
                </div>
                <div className="mt-2 flex flex-wrap items-center justify-center gap-3 text-center sm:gap-8">
                  <div>
                    <div className="text-xs text-gray-500">Away</div>
                    <div className="text-lg font-semibold">{gameSummary.awayTeam}</div>
                    <div className="text-3xl font-bold tabular-nums">{summaryScores.away}</div>
                  </div>
                  <div className="text-2xl font-light text-gray-400">@</div>
                  <div>
                    <div className="text-xs font-medium text-blue-700">Home</div>
                    <div className="text-lg font-semibold">{gameSummary.homeTeam}</div>
                    <div className="text-3xl font-bold tabular-nums">{summaryScores.home}</div>
                  </div>
                </div>
              </div>

              {gameSummary.quarterlyScores.length > 0 ? (
                <div>
                  <div className="mb-2 text-xs font-semibold text-gray-700">Scoring by quarter</div>
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full min-w-[280px] text-left text-xs">
                      <thead>
                        <tr className="border-b border-gray-200 bg-gray-50">
                          <th className="px-2 py-2 font-medium">Q</th>
                          <th className="px-2 py-2 font-medium">{gameSummary.awayTeam}</th>
                          <th className="px-2 py-2 font-medium">{gameSummary.homeTeam} (home)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {gameSummary.quarterlyScores.map((q) => (
                          <tr key={q.quarter} className="border-b border-gray-100">
                            <td className="px-2 py-1.5 font-medium">{q.quarter}</td>
                            <td className="px-2 py-1.5 tabular-nums">{q.awayPoints}</td>
                            <td className="px-2 py-1.5 tabular-nums">{q.homePoints}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2">
                <StatColumn
                  label={`${gameSummary.awayTeam} (away)`}
                  side="away"
                  s={gameSummary}
                />
                <StatColumn label={`${gameSummary.homeTeam} (home)`} side="home" s={gameSummary} />
              </div>

              {gameSummary.highlights.length > 0 ? (
                <div>
                  <div className="mb-2 text-xs font-semibold text-gray-700">Scoring highlights</div>
                  <ul className="space-y-2">
                    {gameSummary.highlights.map((h, i) => (
                      <li
                        key={i}
                        className="rounded-lg border border-amber-100 bg-amber-50/60 px-3 py-2 text-xs text-gray-800"
                      >
                        <span className="font-medium">
                          Q{h.quarter ?? "—"}
                          {h.team ? ` · ${h.team}` : ""}
                          {h.playType ? ` · ${h.playType}` : ""}
                        </span>
                        {h.player ? (
                          <span className="ml-1 font-semibold text-amber-950">{h.player}</span>
                        ) : null}
                        {h.description ? (
                          <div className="mt-1 text-gray-600 line-clamp-3">{h.description}</div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </Card>
      )}

      {selectedGameId && (
        <Card>
          <div className="text-sm font-semibold text-slate-800">Play-by-play sample</div>
          {selectedGame && (
            <div className="mt-1 text-xs text-slate-500">
              {selectedGame.awayTeam} @ {selectedGame.homeTeam}
              {selectedGame.stadium ? ` · ${selectedGame.stadium}` : ""}
            </div>
          )}
          {loadingPlays ? (
            <div className="mt-2 text-xs text-slate-500">Loading plays…</div>
          ) : playsError ? (
            <div className="mt-2 text-xs text-red-600">
              {playsErr instanceof Error ? playsErr.message : "Could not load plays."}
            </div>
          ) : plays.length === 0 ? (
            <div className="mt-2 text-sm text-gray-600">No plays returned.</div>
          ) : (
            <ul className="mt-2 max-h-[28rem] space-y-2 overflow-y-auto pr-1">
              {plays.map((p) => (
                <li key={p.id} className="rounded border border-slate-200/80 bg-white/50 p-2">
                  <div className="text-sm font-medium">
                    Q{p.quarter ?? "—"} ·{" "}
                    {p.down != null && p.yardsToGo != null
                      ? `${p.down} & ${p.yardsToGo}`
                      : "—"}
                    {p.playType ? ` · ${p.playType}` : ""}
                  </div>
                  <div className="text-xs text-gray-500">
                    {p.offense ?? "—"} vs {p.defense ?? "—"}
                    {p.epa != null && ` · EPA ${p.epa.toFixed(3)}`}
                    {p.yardsGained != null && ` · ${p.yardsGained} yds`}
                  </div>
                  {p.description && <div className="mt-1 text-xs text-gray-700">{p.description}</div>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

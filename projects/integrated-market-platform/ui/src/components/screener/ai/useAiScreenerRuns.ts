import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAiScreenerRun, fetchAiScreenerRuns, postAiScreener, postStopAiScreenerRun, type AiScreenerRun, type AiScreenerRuns, type AiScreenerScope } from "../../../api/screenerAi";

export const AI_RUNS_KEY = ["screener-ai-screener-runs"] as const;
export const aiRunKey = (runId: string | null) => ["screener-ai-screener-run", runId] as const;

/**
 * The account's AI Screener run as the server reports it. Reading it never starts a run, so a reloaded page
 * re-attaches to whatever is already in progress; only `start` (an operator click) posts.
 */
export function useAiScreenerRuns(enabled: boolean) {
  const client = useQueryClient();
  const runs = useQuery({ queryKey: AI_RUNS_KEY, queryFn: ({ signal }) => fetchAiScreenerRuns(signal), enabled, retry: false,
    // Once a second while the server is working; a slow look otherwise, so a run started elsewhere still appears.
    refetchInterval: (query) => !enabled ? false : query.state.data?.active ? 1_000 : 5_000 });
  const start = useMutation({ mutationFn: (scope: AiScreenerScope) => postAiScreener(scope), onSuccess: (run) => {
    if (run.state !== "RUNNING") client.setQueryData(aiRunKey(run.run_id), run);
    // Shown at once; the next status read replaces it with the server's own account of state and budget.
    client.setQueryData<AiScreenerRuns>(AI_RUNS_KEY, (old) => old && ({ ...old, state: run.state === "RUNNING" ? "RUNNING" : old.state,
      active: run.state === "RUNNING" ? run : null, latest: run.state === "RUNNING" ? old.latest : { ...run, result: null } }));
    void client.invalidateQueries({ queryKey: AI_RUNS_KEY });
  } });
  // Stop asks the server to start no further model call; the run reports STOPPED once the call in flight has finished.
  const stop = useMutation({ mutationFn: (runId: string) => postStopAiScreenerRun(runId), onSettled: () => client.invalidateQueries({ queryKey: AI_RUNS_KEY }) });
  return { runs, start, stop };
}

/** The full result of one finished run, read once. */
export function useAiScreenerRunResult(run: AiScreenerRun | null | undefined) {
  const runId = run?.state === "COMPLETED" ? run.run_id : null;
  return useQuery({ queryKey: aiRunKey(runId), queryFn: ({ signal }) => fetchAiScreenerRun(runId!, signal), enabled: runId !== null,
    staleTime: Infinity, retry: false });
}

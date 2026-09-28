/**
 * URL state for the Screener News view. News is a view inside the active
 * universe (`news=1`); its window, sort, and filters use their own `n*` params so
 * the column-view, sort, and saved-screen params keep their existing meaning.
 */
export const NEWS_PARAM = "news";
export const NEWS_FILTER_PARAMS = ["nsrc", "ncat", "nsent", "ninst"] as const;
export const NEWS_PARAMS = [NEWS_PARAM, "nwin", "nsort", "nbrief", ...NEWS_FILTER_PARAMS] as const;

/** Updates that leave News mode (a column-view tab was chosen). */
export const exitNewsUpdates = (): Record<string, null> => Object.fromEntries(NEWS_PARAMS.map((key) => [key, null]));
/** Updates for a universe switch: News mode, window, and sort stay; filters reset. */
export const resetNewsFilterUpdates = (): Record<string, null> => Object.fromEntries(NEWS_FILTER_PARAMS.map((key) => [key, null]));
export const isNewsMode = (search: string) => new URLSearchParams(search).get(NEWS_PARAM) === "1";

/**
 * URL state for the S12 intelligence views. They are views inside the active
 * universe (`intel=ownership|congress|positioning`), never universes; their
 * window, sort, filters and page use their own `i*` params so column-view, sort,
 * News, and saved-screen params keep their meaning.
 */
export const INTEL_PARAM = "intel";
export const INTEL_VIEWS = ["ownership", "congress", "positioning"] as const;
export type IntelView = (typeof INTEL_VIEWS)[number];
export const INTEL_FILTER_PARAMS = ["ifam", "itype", "iamt", "imem", "ioff"] as const;
export const INTEL_PARAMS = [INTEL_PARAM, "iwin", "isort", ...INTEL_FILTER_PARAMS] as const;
export const INTEL_LABELS: Record<IntelView, string> = { ownership: "Institutional", congress: "Congress", positioning: "Positioning" };

/** Updates that leave an intelligence view (a column view or News was chosen). */
export const exitIntelUpdates = (): Record<string, null> => Object.fromEntries(INTEL_PARAMS.map((key) => [key, null]));
/** Updates for switching between intelligence views or universes: window/sort/filters/page reset. */
export const resetIntelUpdates = (): Record<string, null> =>
  Object.fromEntries(INTEL_PARAMS.filter((key) => key !== INTEL_PARAM).map((key) => [key, null]));

/** The requested view, only when the active universe offers it. */
export function intelView(search: string, available: readonly string[] | undefined): IntelView | null {
  const value = new URLSearchParams(search).get(INTEL_PARAM);
  return value && (INTEL_VIEWS as readonly string[]).includes(value) && (available ?? []).includes(value) ? value as IntelView : null;
}

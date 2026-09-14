import { CHART_COLORS } from "./chartTheme";

/** IMP dark tokens projected onto Vela host `--vela-*` CSS variables (lazy chart path only). */
export const IMP_VELA_HOST_CSS_VARS: Record<string, string> = {
  "--vela-color-bg": "#0c0e12",
  "--vela-color-surface": "#13161c",
  "--vela-color-surface-2": "#1a1f28",
  "--vela-color-border": CHART_COLORS.grid,
  "--vela-color-text": "#e8ecf4",
  "--vela-color-text-muted": CHART_COLORS.text,
  "--vela-color-accent": "#ff6a00",
};

export function applyImpVelaHostTokens(container: HTMLElement): void {
  for (const [key, value] of Object.entries(IMP_VELA_HOST_CSS_VARS)) {
    container.style.setProperty(key, value);
  }
}

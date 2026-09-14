/** IMP dark surface tokens projected onto Vela `--vela-*` host chrome. */
export const IMP_VELA_CSS_VARS: Record<string, string> = {
  "--vela-color-bg": "#0c0e12",
  "--vela-color-surface": "#13161c",
  "--vela-color-surface-2": "#1a1f28",
  "--vela-color-border": "#2c323c",
  "--vela-color-text": "#e8ecf4",
  "--vela-color-text-muted": "#9aa3b5",
  "--vela-color-accent": "#ff6a00",
};

export function applyImpHostTokens(container: HTMLElement): void {
  for (const [key, value] of Object.entries(IMP_VELA_CSS_VARS)) {
    container.style.setProperty(key, value);
  }
}

/** Isolated dynamic import boundary — keep off the App entry static graph. */
export async function loadVelaConstructor(): Promise<
  new (
    container: HTMLElement,
    options: Record<string, unknown>,
  ) => ImpVelaChartInstance
> {
  const module = await import("@luxalgo/vela");
  return module.Vela as new (
    container: HTMLElement,
    options: Record<string, unknown>,
  ) => ImpVelaChartInstance;
}

export type ImpVelaChartInstance = {
  ready: () => Promise<void>;
  destroy: () => void;
  resize: () => void;
  setMarket: (next: { bars?: unknown[] }) => Promise<unknown>;
  setTheme: (theme: "dark" | "light") => unknown;
  drawings: {
    supported: boolean;
    add: (type: string, init: Record<string, unknown>) => { id: string };
    remove: (id: string) => void;
  };
};

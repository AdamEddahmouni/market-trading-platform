export type Mode = "DEMO" | "PAPER" | "LIVE";

export type ReadinessTask = () => Promise<void>;
export type ModeReadinessTask = (mode: Mode) => Promise<void>;

export const defaultReadinessTask: ReadinessTask = async () => {
  const response = await fetch("/context", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Platform readiness check failed");
};

export const defaultModeReadinessTask: ModeReadinessTask = async () => undefined;

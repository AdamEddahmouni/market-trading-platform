export type Mode = "DEMO" | "PAPER" | "LIVE";

export type ReadinessTask = () => Promise<void>;

export type ModeReadinessTask = (mode: Mode) => Promise<void>;

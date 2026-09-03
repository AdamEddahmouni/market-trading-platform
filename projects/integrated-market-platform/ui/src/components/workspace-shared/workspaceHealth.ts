export function formatDataHealthLabel(context: {
  data_mode?: string;
  data_provider?: string | null;
} | undefined) {
  if (!context) return "";
  if (context.data_mode === "LIVE_OBSERVATIONAL") {
    return `LIVE · ${context.data_provider ?? "MOOMOO"}`;
  }
  if (context.data_mode === "CAPTURE_REPLAY") {
    return "REPLAY · MOOMOO CAPTURE";
  }
  return context.data_mode?.replace(/_/g, " ") ?? "";
}

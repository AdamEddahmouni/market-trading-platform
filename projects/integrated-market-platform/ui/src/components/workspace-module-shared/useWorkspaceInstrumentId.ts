import { useParams } from "react-router-dom";

export function useWorkspaceInstrumentId(fallback = ""): string {
  const { symbol } = useParams<{ symbol: string }>();
  return symbol?.toUpperCase() ?? fallback;
}

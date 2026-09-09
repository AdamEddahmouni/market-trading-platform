import { useParams } from "react-router-dom";
import { decodeInstrumentRouteParam } from "../../api/instrumentIdentity";

export function useWorkspaceInstrumentId(fallback = ""): string {
  const { symbol } = useParams<{ symbol: string }>();
  if (!symbol) return fallback;
  return decodeInstrumentRouteParam(symbol);
}

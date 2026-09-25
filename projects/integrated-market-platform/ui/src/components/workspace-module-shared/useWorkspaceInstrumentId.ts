import { useParams } from "react-router-dom";
import { decodeInstrumentRouteParam } from "../../api/instrumentIdentity";

export function useWorkspaceInstrumentId(): string {
  const { symbol } = useParams<{ symbol: string }>();
  if (!symbol) return "";
  return decodeInstrumentRouteParam(symbol);
}

import type { SrZone } from "../../api/screener";

export type ClassifiedZone = Pick<SrZone, "lower" | "upper" | "center" | "strength"> & { distance_pct: number };
export type Classification = { support: ClassifiedZone | null; resistance: ClassifiedZone | null; testing: ClassifiedZone | null };
type ZoneInput = Pick<SrZone, "lower" | "upper" | "center" | "strength">;

/**
 * Mirror of backend AUTO_SR_V1 `classify` so the live L1 price can move against
 * the last calculated zones between recalculations. Zones themselves are never
 * computed in the browser. Agreement is tested against a shared fixture.
 */
export function classifyZones(zones: ZoneInput[], price: number | null | undefined, minStrength: number): Classification {
  if (price == null || !Number.isFinite(price) || price <= 0) return { support: null, resistance: null, testing: null };
  const meaningful = zones.filter((zone) => zone.strength >= minStrength);
  const below = meaningful.filter((zone) => zone.upper < price);
  const above = meaningful.filter((zone) => zone.lower > price);
  const testing = meaningful.filter((zone) => zone.lower <= price && price <= zone.upper);
  const support = below.reduce<ZoneInput | null>((best, zone) =>
    !best || zone.upper > best.upper || (zone.upper === best.upper && zone.strength > best.strength) ? zone : best, null);
  const resistance = above.reduce<ZoneInput | null>((best, zone) =>
    !best || zone.lower < best.lower || (zone.lower === best.lower && zone.strength > best.strength) ? zone : best, null);
  const tested = testing.reduce<ZoneInput | null>((best, zone) => !best || zone.strength > best.strength ? zone : best, null);
  const round = (value: number) => Math.round(value * 10_000) / 10_000;
  return {
    support: support && { ...support, distance_pct: round((price - support.upper) / price * 100) },
    resistance: resistance && { ...resistance, distance_pct: round((resistance.lower - price) / price * 100) },
    testing: tested && { ...tested, distance_pct: 0 },
  };
}

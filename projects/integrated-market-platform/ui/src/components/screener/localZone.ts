/** The machine's own time zone. Screener clocks that are not tied to US market hours read in it. */
export const LOCAL_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

/** Short label for a zone: "ET" for US Eastern, otherwise the zone's own abbreviation (e.g. "PDT", "UTC"). */
export function zoneSuffix(zone: string, at: Date = new Date()): string {
  if (zone === "America/New_York") return "ET";
  if (zone === "UTC") return "UTC";
  const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "short" }).formatToParts(at)
    .find((item) => item.type === "timeZoneName");
  return part?.value ?? zone;
}

export const LOCAL_SUFFIX = zoneSuffix(LOCAL_ZONE);

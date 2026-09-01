export type JsonDetailRow = {
  key: string;
  label: string;
  value: string;
  nested?: JsonDetailRow[];
};

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPrimitive(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" || typeof value === "bigint") return String(value);
  if (typeof value === "string") return value.trim() ? value : "—";
  return String(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function flattenJsonDetail(value: unknown, prefix = ""): JsonDetailRow[] {
  if (value === null || value === undefined) {
    return [{ key: prefix || "value", label: humanizeKey(prefix || "value"), value: "—" }];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return [{ key: prefix || "items", label: humanizeKey(prefix || "items"), value: "None" }];
    }
    return value.flatMap((item, index) =>
      flattenJsonDetail(item, prefix ? `${prefix}[${index}]` : `[${index}]`),
    );
  }
  if (!isPlainObject(value)) {
    return [{ key: prefix || "value", label: humanizeKey(prefix || "value"), value: formatPrimitive(value) }];
  }
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return [{ key: prefix || "object", label: humanizeKey(prefix || "object"), value: "Empty" }];
  }
  return entries.map(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (isPlainObject(nested) || Array.isArray(nested)) {
      return {
        key: path,
        label: humanizeKey(key),
        value: Array.isArray(nested) ? `${nested.length} item(s)` : "Object",
        nested: flattenJsonDetail(nested, path),
      };
    }
    return { key: path, label: humanizeKey(key), value: formatPrimitive(nested) };
  });
}

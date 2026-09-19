import { useState } from "react";

type Props = {
  /** The full identifier (UUID/hash/session/account id). */
  value: string;
  /** Visible label prefix, e.g. "Acct". */
  prefix?: string;
  /** Characters kept on each side of the middle truncation. */
  chars?: number;
  className?: string;
};

export function truncateMiddle(value: string, chars = 4): string {
  if (value.length <= chars * 2 + 1) return value;
  return `${value.slice(0, chars)}…${value.slice(-chars)}`;
}

/**
 * Truncate-middle identifier with a copy action; the full value is available
 * via the tooltip and clipboard. Prevents long raw IDs from breaking layout
 * or dominating primary surfaces (L4 values stay reachable).
 */
export function CopyableIdentifier({ value, prefix, chars = 4, className }: Props) {
  const [copied, setCopied] = useState(false);
  const classes = ["imp-ui-copyable-id", className].filter(Boolean).join(" ");
  const truncated = truncateMiddle(value, chars);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (permissions) — the full value remains in the tooltip.
    }
  };

  return (
    <span className={classes} data-testid="imp-ui-copyable-id" title={value}>
      {prefix ? <span className="imp-ui-copyable-id-prefix">{prefix} </span> : null}
      <code className="imp-ui-copyable-id-value">{truncated}</code>
      <button
        type="button"
        className="imp-ui-copyable-id-copy"
        aria-label={`Copy full identifier ${truncated}`}
        onClick={() => void copy()}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

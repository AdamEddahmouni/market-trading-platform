import { cn } from "../../lib/utils";
import type { PropsWithChildren } from "react";

export function Card({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-white/50 bg-stadium-concrete/95 p-4 shadow-panel backdrop-blur-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

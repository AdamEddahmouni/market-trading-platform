import { cn } from "../../lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
};

export function Button({ className, variant = "primary", ...props }: Props) {
  return (
    <button
      className={cn(
        "rounded-xl px-3 py-2 text-sm font-medium transition",
        variant === "primary" &&
          "bg-stadium-turf text-white shadow-sm hover:bg-stadium-turfMuted",
        variant === "ghost" && "bg-transparent text-slate-700 hover:bg-white/50",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className
      )}
      {...props}
    />
  );
}

import { Suspense, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  label?: string;
};

export function LazyBoundary({ children, label = "Loading view…" }: Props) {
  return (
    <Suspense
      fallback={
        <div className="app-loading" role="status">
          {label}
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

import { Suspense, type ReactNode } from "react";
import { LoadingState } from "./shared/LoadingState";

type Props = {
  children: ReactNode;
  label?: string;
};

export function LazyBoundary({ children, label = "Loading view…" }: Props) {
  return <Suspense fallback={<LoadingState label={label} />}>{children}</Suspense>;
}

import { lazy, type ReactElement } from "react";
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LazyBoundary } from "./LazyBoundary";

describe("LazyBoundary", () => {
  it("shows an accessible fallback until the child module resolves", async () => {
    let resolveModule!: (module: { default: () => ReactElement }) => void;
    const LazyView = lazy(
      () =>
        new Promise<{ default: () => ReactElement }>((resolve) => {
          resolveModule = resolve;
        }),
    );

    render(
      <LazyBoundary label="Loading research…">
        <LazyView />
      </LazyBoundary>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Loading research…");

    await act(async () => {
      resolveModule({ default: () => <div>Research ready</div> });
    });

    expect(await screen.findByText("Research ready")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

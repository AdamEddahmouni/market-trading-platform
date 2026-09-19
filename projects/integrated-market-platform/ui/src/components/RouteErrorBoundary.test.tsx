import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

function Boom() {
  throw new Error("synthetic-route-crash");
}

function Safe() {
  return <h1>Safe view</h1>;
}

describe("RouteErrorBoundary", () => {
  it("shows a retryable error instead of an uncaught crash", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <MemoryRouter initialEntries={["/boom"]}>
        <RouteErrorBoundary>
          <Routes>
            <Route path="/boom" element={<Boom />} />
            <Route path="/safe" element={<Safe />} />
          </Routes>
        </RouteErrorBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/crashed while rendering/i);
    expect(screen.getByText("synthetic-route-crash")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("clears the error when Retry is pressed after the child recovers", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("flaky");
      return <p>Recovered</p>;
    }
    render(
      <MemoryRouter>
        <RouteErrorBoundary>
          <Flaky />
        </RouteErrorBoundary>
      </MemoryRouter>,
    );
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByText("Recovered")).toBeInTheDocument();
    spy.mockRestore();
  });
});

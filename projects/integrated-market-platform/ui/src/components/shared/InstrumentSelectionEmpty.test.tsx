import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { InstrumentSelectionEmpty } from "./InstrumentSelectionEmpty";

describe("InstrumentSelectionEmpty", () => {
  it("guides Live users to Explore", () => {
    render(
      <MemoryRouter>
        <InstrumentSelectionEmpty mode="LIVE" laneLabel="Disclosure " />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /select an instrument/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to explore/i })).toHaveAttribute("href", "/explore");
  });
});

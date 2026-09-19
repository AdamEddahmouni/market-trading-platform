import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { InstrumentSelectionEmpty } from "./InstrumentSelectionEmpty";

describe("InstrumentSelectionEmpty", () => {
  it("guides Live users to Radar screeners", () => {
    render(
      <MemoryRouter>
        <InstrumentSelectionEmpty mode="LIVE" laneLabel="Disclosure " />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /select an instrument/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open radar screeners/i })).toHaveAttribute(
      "href",
      "/radar/screeners",
    );
    expect(screen.getByRole("link", { name: "Radar" })).toHaveAttribute("href", "/radar");
  });
});

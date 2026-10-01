import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Clocks that follow the machine's time zone are tested on one fixed zone, whatever machine runs the suite.
vi.stubEnv("TZ", "UTC");

afterEach(() => {
  cleanup();
});

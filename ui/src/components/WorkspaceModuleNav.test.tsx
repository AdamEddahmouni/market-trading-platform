import { describe, expect, it } from "vitest";
import { laneById, workspaceLanePath, WORKSPACE_LANE_REGISTRY } from "./workspace-module-shared/laneRegistry";

describe("laneRegistry", () => {
  it("lists all workspace lanes with stable routes", () => {
    expect(WORKSPACE_LANE_REGISTRY.length).toBe(11);
    expect(laneById("squeeze")?.routeSuffix).toBe("/squeeze");
    expect(workspaceLanePath("BIYA", "order-flow")).toBe("/workspace/BIYA/order-flow");
  });
});

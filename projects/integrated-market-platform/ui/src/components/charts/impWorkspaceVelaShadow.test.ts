import { afterEach, describe, expect, it } from "vitest";
import {
  IMP_WORKSPACE_VELA_SHADOW_QUERY,
  IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY,
  persistWorkspaceVelaShadowEnabled,
  readWorkspaceVelaShadowEnabled,
} from "./impWorkspaceVelaShadow";

describe("impWorkspaceVelaShadow", () => {
  afterEach(() => {
    window.localStorage.removeItem(IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY);
    window.history.replaceState({}, "", "/");
  });

  it("reads query param before localStorage", () => {
    persistWorkspaceVelaShadowEnabled(true);
    window.history.replaceState({}, "", `/?${IMP_WORKSPACE_VELA_SHADOW_QUERY}=0`);
    expect(readWorkspaceVelaShadowEnabled()).toBe(false);
  });

  it("persists enabled flag in localStorage", () => {
    persistWorkspaceVelaShadowEnabled(true);
    expect(window.localStorage.getItem(IMP_WORKSPACE_VELA_SHADOW_STORAGE_KEY)).toBe("true");
    expect(readWorkspaceVelaShadowEnabled()).toBe(true);
  });
});

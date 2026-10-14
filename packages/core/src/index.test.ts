import { describe, expect, it } from "vitest";
import { SCENE_VERSION } from "./index";

describe("core", () => {
  it("exports the scene schema version", () => {
    expect(SCENE_VERSION).toBe(1);
  });
});

import { describe, expect, it } from "vitest";
import { parseScene, solve } from "@newtons-eye/core";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fbdArrows, fmt } from "./fbd";

const examples = join(dirname(fileURLToPath(import.meta.url)), "../../../../examples");

function solved(name: string) {
  const parsed = parseScene(JSON.parse(readFileSync(join(examples, `${name}.scene.json`), "utf8")));
  if (!parsed.ok) throw new Error(JSON.stringify(parsed.errors));
  return solve(parsed.scene);
}

describe("fbdArrows", () => {
  it("static block on a 30 deg incline: weight 49.05 N, normal 42.4785 N, friction 24.525 N, with proportional arrow lengths", () => {
    const { timeline } = solved("incline-static");
    const arrows = fbdArrows(timeline.at(1).forces, "block", 100);
    const by = Object.fromEntries(arrows.map((a) => [a.kind, a]));
    expect(by["gravity"]?.magnitude).toBeCloseTo(49.05, 6);
    expect(by["normal"]?.magnitude).toBeCloseTo(42.4785, 3);
    expect(by["friction"]?.magnitude).toBeCloseTo(24.525, 3);
    // The largest force (weight) is drawn 100 px long; others scale linearly with magnitude.
    expect(Math.hypot(by["gravity"]!.dx, by["gravity"]!.dy)).toBeCloseTo(100, 6);
    expect(Math.hypot(by["normal"]!.dx, by["normal"]!.dy)).toBeCloseTo((100 * 42.4785) / 49.05, 3);
    // Weight points down on screen (+y in SVG).
    expect(by["gravity"]!.dy).toBeGreaterThan(0);
    expect(by["gravity"]!.label).toBe("Weight 49.05 N");
    expect(by["friction"]!.label).toContain("static");
  });

  it("forces on the other body are not included, and a free body shows only its weight", () => {
    const { timeline } = solved("projectile");
    const arrows = fbdArrows(timeline.at(1).forces, "ball", 80);
    expect(arrows).toHaveLength(1);
    expect(arrows[0]?.magnitude).toBeCloseTo(0.5 * 9.81, 9);
    expect(fbdArrows(timeline.at(1).forces, "nobody", 80)).toEqual([]);
  });

  it("Atwood machine: tension on each block equals the solver's 36.7875 N and points up", () => {
    const { timeline } = solved("atwood");
    const a1 = fbdArrows(timeline.at(0.2).forces, "m1", 100).find((a) => a.kind === "tension");
    expect(a1?.magnitude).toBeCloseTo(36.7875, 3);
    expect(a1!.dy).toBeLessThan(0);
  });
});

describe("fmt", () => {
  it("rounds to 4 significant digits and prints tiny values as 0", () => {
    expect(fmt(42.478512)).toBe("42.48");
    expect(fmt(1e-14)).toBe("0");
    expect(fmt(0.0003456789)).toBe("0.0003457");
  });
});

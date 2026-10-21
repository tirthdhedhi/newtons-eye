import { describe, expect, it } from "vitest";
import { parseScene } from "../validate";
import { solve } from "../solver";

const G = 9.81;
const run = (json: unknown) => {
  const r = parseScene(json);
  if (!r.ok) throw new Error(JSON.stringify(r.errors));
  const { answers } = solve(r.scene);
  return {
    byId: Object.fromEntries(answers.map((a) => [a.id, a])),
    warnings: r.warnings.map((w) => `${w.path}: ${w.message}`),
  };
};
const near = (a: unknown, b: number, tol = 1e-6) =>
  expect(Math.abs((a as number) - b)).toBeLessThan(tol);

describe("authoring: optional mass and prescribed acceleration", () => {
  it("a body with no mass defaults to 1 kg and says so; projectile motion does not depend on it", () => {
    const { byId, warnings } = run({
      version: 1.1,
      bodies: [{ id: "ball", velocity: { speed: "10 m/s", angle: "0 deg" } }],
      queries: [{ id: "p", ask: "position", body: "ball", at: 2 }],
    });
    near((byId["p"]?.value as number[])[0], 20);
    near((byId["p"]?.value as number[])[1], -0.5 * G * 4);
    expect(warnings.some((w) => w.includes("bodies[0].mass") && w.includes("1 kg"))).toBe(true);
  });

  it("a car at 20 m/s accelerating at 3 m/s^2 for 8 s: v = 44 m/s, x = 20*8 + 3*64/2 = 256 m", () => {
    const { byId } = run({
      version: 1.1,
      bodies: [{ id: "car", velocity: [20, 0, 0], constantAcceleration: "3 m/s^2" }],
      queries: [
        { id: "v", ask: "velocity", body: "car", at: 8 },
        { id: "x", ask: "position", body: "car", at: 8 },
      ],
    });
    near((byId["v"]?.value as number[])[0], 44);
    near((byId["v"]?.value as number[])[1], 0);
    near((byId["x"]?.value as number[])[0], 256);
    near((byId["x"]?.value as number[])[1], 0);
  });

  it("the mass does not change a prescribed acceleration (5 kg, brakes at 2 m/s^2 from 20 m/s: v(5) = 10, x(5) = 75)", () => {
    const { byId } = run({
      version: 1.1,
      bodies: [
        {
          id: "c",
          mass: "5 kg",
          velocity: { speed: "20 m/s", angle: "0 deg" },
          constantAcceleration: "-2 m/s^2",
        },
      ],
      queries: [
        { id: "v", ask: "velocity", body: "c", at: 5 },
        { id: "x", ask: "position", body: "c", at: 5 },
      ],
    });
    near((byId["v"]?.value as number[])[0], 10);
    near((byId["x"]?.value as number[])[0], 75);
  });

  it("starting at rest it accelerates toward +x; along a 30 degree velocity it follows the direction of motion", () => {
    const rest = run({
      version: 1.1,
      bodies: [{ id: "b", constantAcceleration: "4 m/s^2" }],
      queries: [{ id: "x", ask: "position", body: "b", at: 3 }],
    });
    near((rest.byId["x"]?.value as number[])[0], 0.5 * 4 * 9);
    const angled = run({
      version: 1.1,
      bodies: [
        {
          id: "b",
          velocity: { speed: "10 m/s", angle: "30 deg" },
          constantAcceleration: "2 m/s^2",
        },
      ],
      queries: [{ id: "v", ask: "velocity", body: "b", at: 2 }],
    });
    const v = angled.byId["v"]?.value as number[];
    near(Math.hypot(v[0]!, v[1]!), 10 + 2 * 2);
    near(Math.atan2(v[1]!, v[0]!), Math.PI / 6);
  });

  it("is rejected for a body that also touches a surface", () => {
    const r = parseScene({
      version: 1.1,
      bodies: [{ id: "b", constantAcceleration: "1 m/s^2" }],
      surfaces: [{ id: "floor", kind: "plane" }],
      contacts: [{ body: "b", surface: "floor" }],
      queries: [],
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors[0]?.message).toMatch(/cannot also touch a surface/);
  });
});

describe("authoring: the default shape of a projectile", () => {
  it("a body with a velocity and no shape or placement is a point, so it lands exactly when its centre reaches the ground (4.922 s for 15 m/s up from 45 m)", () => {
    const { byId, warnings } = run({
      version: 1.1,
      bodies: [
        { id: "ball", position: [0, 45, 0], velocity: { speed: "15 m/s", angle: "90 deg" } },
      ],
      surfaces: [{ id: "ground", kind: "plane" }],
      contacts: [{ body: "ball", surface: "ground" }],
      queries: [
        { id: "t", ask: "time", until: { event: "land" }, body: "ball" },
        { id: "h", ask: "max_height", body: "ball" },
      ],
    });
    near(byId["t"]?.value, (15 + Math.sqrt(225 + 2 * G * 45)) / G, 1e-6);
    near(byId["h"]?.value, 45 + 225 / (2 * G), 1e-6);
    expect(warnings.some((w) => w.includes("using a point"))).toBe(true);
  });

  it("a block placed on a surface still gets the default box (it must sit flush)", () => {
    const { warnings } = run({
      version: 1.1,
      bodies: [{ id: "b", mass: "2 kg", placement: { on: "floor", offset: 0 } }],
      surfaces: [{ id: "floor", kind: "plane" }],
      contacts: [{ body: "b", surface: "floor" }],
      queries: [{ id: "x", ask: "position", body: "b", at: 1 }],
    });
    expect(warnings.some((w) => w.includes("using a box"))).toBe(true);
  });
});

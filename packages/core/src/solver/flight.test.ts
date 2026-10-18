import { describe, expect, it } from "vitest";
import { solve } from "./index";
import { G, deg, load } from "./testing";

/** Authoring scene: a point-particle projectile with a ground plane through the origin. */
function flight(opts: {
  y0?: number;
  speed: number;
  angle: number;
  queries: unknown[];
  duration?: number;
}): unknown {
  return {
    version: 1.1,
    ...(opts.duration !== undefined ? { duration: opts.duration } : {}),
    bodies: [
      {
        id: "p",
        mass: "1 kg",
        shape: { kind: "point" },
        position: [0, opts.y0 ?? 0, 0],
        velocity: { speed: `${opts.speed} m/s`, angle: `${opts.angle} deg` },
      },
    ],
    surfaces: [{ id: "ground", kind: "plane" }],
    contacts: [{ body: "p", surface: "ground" }],
    queries: opts.queries,
  };
}

const run = (scene: unknown) => {
  const { answers } = solve(load(scene));
  return Object.fromEntries(answers.map((a) => [a.id, a]));
};
const near = (a: number | number[] | undefined, b: number, tol = 1e-6) =>
  expect(Math.abs((a as number) - b)).toBeLessThan(tol);

describe("flight: time until land, max height, range", () => {
  it("40 m/s at 35 deg from level ground: T = 2 v sin(a)/g, H = (v sin a)^2/2g, R = v^2 sin(2a)/g", () => {
    const a = deg(35);
    const r = run(
      flight({
        speed: 40,
        angle: 35,
        queries: [
          { id: "T", ask: "time", until: { event: "land" }, body: "p" },
          { id: "H", ask: "max_height", body: "p" },
          { id: "R", ask: "range", body: "p" },
        ],
      }),
    );
    near(r.T?.value, (2 * 40 * Math.sin(a)) / G, 1e-5);
    near(r.H?.value, (40 * Math.sin(a)) ** 2 / (2 * G), 1e-5);
    near(r.R?.value, (40 * 40 * Math.sin(2 * a)) / G, 1e-5);
    expect(r.T?.value).toBeCloseTo(4.6775, 3);
    expect(r.R?.value).toBeCloseTo(153.2628, 3);
  });

  it("thrown straight up at 15 m/s from a 45 m building: H above ground = 45 + v^2/2g, above start = v^2/2g, T = 4.922 s, impact v = -33.285 m/s", () => {
    const r = run(
      flight({
        y0: 45,
        speed: 15,
        angle: 90,
        queries: [
          { id: "H", ask: "max_height", body: "p" },
          { id: "Hs", ask: "max_height", body: "p", above: "start" },
          { id: "T", ask: "time", until: { event: "land" }, body: "p" },
          { id: "v", ask: "velocity", body: "p", at: { event: "land" } },
        ],
      }),
    );
    const t = (15 + Math.sqrt(15 * 15 + 2 * G * 45)) / G;
    near(r.H?.value, 45 + 225 / (2 * G), 1e-5);
    near(r.Hs?.value, 225 / (2 * G), 1e-5);
    near(r.T?.value, t, 1e-5);
    near((r.v?.value as number[])[1], 15 - G * t, 1e-5);
  });

  it("thrown horizontally at 12 m/s from an 80 m cliff: T = sqrt(2h/g) = 4.0386 s, range = 48.46 m, impact speed = 41.4 m/s", () => {
    const r = run(
      flight({
        y0: 80,
        speed: 12,
        angle: 0,
        queries: [
          { id: "T", ask: "time", until: { event: "land" }, body: "p" },
          { id: "R", ask: "range", body: "p" },
          { id: "v", ask: "velocity", body: "p", at: { event: "land" } },
        ],
      }),
    );
    const t = Math.sqrt((2 * 80) / G);
    near(r.T?.value, t, 1e-5);
    near(r.R?.value, 12 * t, 1e-5);
    const v = r.v?.value as number[];
    near(Math.hypot(v[0]!, v[1]!), Math.hypot(12, G * t), 1e-5);
    expect(Math.hypot(v[0]!, v[1]!)).toBeCloseTo(41.4, 1);
  });

  it("a body resting on the ground is not launched, and one moving away from it leaves the surface", () => {
    const rest = run({
      version: 1.1,
      bodies: [{ id: "p", mass: "1 kg", shape: { kind: "point" } }],
      surfaces: [{ id: "ground", kind: "plane" }],
      contacts: [{ body: "p", surface: "ground" }],
      queries: [{ id: "p3", ask: "position", body: "p", at: 3 }],
    });
    near((rest.p3?.value as number[])[1], 0, 1e-9);
    const up = run(
      flight({ speed: 10, angle: 90, queries: [{ id: "y", ask: "position", body: "p", at: 1 }] }),
    );
    near((up.y?.value as number[])[1], 10 - 0.5 * G, 1e-6);
  });

  it("without a duration, a query that waits for an event gets a long enough window (60 s)", () => {
    const r = run({
      version: 1.1,
      bodies: [{ id: "b", mass: "2 kg", velocity: { speed: "10 m/s", angle: "0 deg" } }],
      surfaces: [{ id: "floor", kind: "plane", friction: { static: 0.6, kinetic: 0.5 } }],
      contacts: [{ body: "b", surface: "floor" }],
      queries: [
        { id: "t", ask: "time", until: { event: "stop" }, body: "b" },
        { id: "d", ask: "distance", body: "b" },
      ],
    });
    near(r.t?.value, 10 / (0.5 * G), 1e-6);
    near(r.d?.value, 100 / (2 * 0.5 * G), 1e-3);
  });

  it("reports a clear error when the body never lands", () => {
    const r = run(
      flight({
        speed: 10,
        angle: 45,
        duration: 1,
        queries: [{ id: "R", ask: "range", body: "p" }],
      }),
    );
    expect(r.R?.error).toMatch(/never lands/);
  });

  it("rejects land/range/max_height when no surface contact exists", () => {
    const bad = {
      version: 1.1,
      bodies: [{ id: "p", mass: "1 kg", velocity: { speed: "5 m/s", angle: "30 deg" } }],
      queries: [{ id: "R", ask: "range", body: "p" }],
    };
    expect(() => load(bad)).toThrow(/needs a surface contact/);
    expect(() =>
      load({ ...bad, queries: [{ id: "T", ask: "time", until: { event: "land" }, body: "p" }] }),
    ).toThrow(/nothing can land/);
  });
});

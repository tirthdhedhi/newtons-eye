import { describe, expect, it } from "vitest";
import { len } from "../math/vec3";
import { solve } from "./index";
import { G, load } from "./testing";

const near = (a: number, b: number, tol = 1e-6) => expect(Math.abs(a - b)).toBeLessThan(tol);

const springBlock = (opts: {
  muS?: number;
  muK?: number;
  x0?: number;
  duration?: number;
  forces?: unknown[];
}) => ({
  version: 1,
  duration: opts.duration ?? 5,
  bodies: [{ id: "block", mass: 4, position: [opts.x0 ?? 0.5, 0, 0] }],
  surfaces: [
    {
      id: "floor",
      kind: "plane",
      point: [0, 0, 0],
      friction: { static: opts.muS ?? 0, kinetic: opts.muK ?? 0 },
    },
  ],
  contacts: [{ body: "block", surface: "floor" }],
  forces: [
    {
      id: "spring",
      kind: "spring",
      body: "block",
      anchor: { point: [0, 0, 0] },
      k: 100,
      restLength: 0,
    },
    ...(opts.forces ?? []),
  ],
});

describe("M6: springs and RK4", () => {
  it("k = 100 N/m, m = 4 kg, x0 = 0.5 m, frictionless: omega = 5 rad/s, x(t) = 0.5 cos 5t (checked at t = 1.2566 and t = 5)", () => {
    const { timeline } = solve(load(springBlock({})));
    expect(timeline.segments.every((s) => s.motion.kind === "rk4")).toBe(true);
    const period = (2 * Math.PI) / Math.sqrt(100 / 4);
    near(period, 1.257, 1e-3);
    near(timeline.at(period).bodies["block"]!.position[0], 0.5, 1e-6);
    near(timeline.at(5).bodies["block"]!.position[0], 0.5 * Math.cos(25), 1e-6);
    near(timeline.at(5).bodies["block"]!.velocity[0], -2.5 * Math.sin(25), 1e-6);
    near(timeline.at(period / 4).bodies["block"]!.position[0], 0, 1e-6);
    // Spring force at x = 0.5 is k x = 50 N, pointing back to the anchor.
    const spring = timeline.at(0).forces.find((f) => f.kind === "spring")!;
    near(spring.vector[0], -50, 1e-9);
    // Normal force balances the weight all the time.
    near(len(timeline.at(3.3).forces.find((f) => f.kind === "normal")!.vector), 4 * G, 1e-9);
  });

  it("scrubbing an RK4 segment backward gives the same states as forward", () => {
    const { timeline } = solve(load(springBlock({ duration: 3 })));
    const ts = [0.2, 0.9, 1.4, 2.6];
    const fwd = ts.map((t) => timeline.at(t).bodies["block"]!.position[0]);
    const bwd = [...ts]
      .reverse()
      .map((t) => timeline.at(t).bodies["block"]!.position[0])
      .reverse();
    expect(fwd).toEqual(bwd);
  });

  it("with friction (mu_s 0.4, mu_k 0.3) the first half cycle ends at x = -(0.5 - 2 mu_k m g / k) = -0.26456 at t = pi/5", () => {
    const muK = 0.3;
    const shift = (muK * 4 * G) / 100; // 0.11772
    const turn1 = -(0.5 - 2 * shift);
    const { timeline, answers } = solve(
      load({
        ...springBlock({ muS: 0.4, muK, duration: 4 }),
        queries: [{ id: "t", ask: "time", until: { event: "stop" } }],
      }),
    );
    near(answers[0]?.value as number, Math.PI / 5, 1e-3);
    near(timeline.at(Math.PI / 5).bodies["block"]!.position[0], turn1, 1e-4);
    near(turn1, -0.26456, 1e-5);
    // |k x| = 26.5 N > mu_s N = 15.7 N, so it slides back; the second turn is at +0.02912 where k x = 2.9 N < 15.7 N.
    const turn2 = -shift + (Math.abs(turn1) - shift);
    near(turn2, 0.02912, 1e-5);
    const rest = timeline.at(3);
    near(rest.bodies["block"]!.position[0], turn2, 1e-4);
    near(len(rest.bodies["block"]!.velocity), 0, 1e-9);
    expect(rest.contacts[0]?.mode).toBe("static");
    near(len(rest.forces.find((f) => f.kind === "friction")!.vector), 100 * turn2, 1e-2);
    expect(timeline.events.filter((e) => e.kind === "stop")).toHaveLength(2);
  });

  it("static block held by a stretched spring (10 N) starts sliding when a 40 N push switches on at t = 1 s", () => {
    const { timeline, answers } = solve(
      load({
        ...springBlock({
          muS: 0.5,
          muK: 0.4,
          x0: 0.1,
          duration: 2,
          forces: [
            { id: "push", kind: "applied", body: "block", vector: [40, 0, 0], during: [1, null] },
          ],
        }),
        queries: [{ id: "t", ask: "time", until: { event: "slide_start" } }],
      }),
    );
    near(answers[0]?.value as number, 1, 1e-9);
    // Before: static, friction = 10 N, no motion.
    near(timeline.at(0.5).bodies["block"]!.position[0], 0.1, 1e-12);
    near(len(timeline.at(0.5).forces.find((f) => f.kind === "friction")!.vector), 10, 1e-9);
    // Just after: a = (-100*0.1 + 40 - 0.4*4*g)/4 = 3.576
    near(timeline.at(1).bodies["block"]!.acceleration[0], (-10 + 40 - 0.4 * 4 * G) / 4, 1e-6);
  });

  it("a spring between two bodies conserves momentum: equal and opposite forces, centre of mass does not move", () => {
    const { timeline } = solve(
      load({
        version: 1,
        duration: 1,
        environment: { gravity: [0, 0, 0] },
        bodies: [
          { id: "a", mass: 1, position: [0, 0, 0] },
          { id: "b", mass: 3, position: [2, 0, 0] },
        ],
        forces: [
          { id: "s", kind: "spring", body: "a", anchor: { body: "b" }, k: 20, restLength: 1 },
        ],
      }),
    );
    const snap = timeline.at(0.7);
    const a = snap.bodies["a"]!;
    const b = snap.bodies["b"]!;
    near(a.position[0] * 1 + b.position[0] * 3, 6, 1e-9);
    near(a.velocity[0] * 1 + b.velocity[0] * 3, 0, 1e-9);
    // Initial: stretched by 1 m -> 20 N pulls a toward b and b toward a.
    near(timeline.at(0).bodies["a"]!.acceleration[0], 20, 1e-9);
    near(timeline.at(0).bodies["b"]!.acceleration[0], -20 / 3, 1e-9);
  });
});

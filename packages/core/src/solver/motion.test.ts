import { describe, expect, it } from "vitest";
import { len } from "../math/vec3";
import type { Vec3 } from "../math/vec3";
import { solve } from "./index";
import { G, blockOnPlane, deg, load } from "./testing";

const near = (a: number, b: number, tol = 1e-6) => expect(Math.abs(a - b)).toBeLessThan(tol);
const nearVec = (a: Vec3, b: Vec3, tol = 1e-6) => {
  near(a[0], b[0], tol);
  near(a[1], b[1], tol);
  near(a[2], b[2], tol);
};

describe("M3: constant forces, planes, friction", () => {
  it("frictionless 30 deg incline, 5 kg: a = g sin30 = 4.905 down the slope, N = m g cos30 = 42.4785", () => {
    const th = deg(30);
    const { timeline } = solve(load(blockOnPlane({ angle: 30, mass: 5, s: 2 })));
    const snap = timeline.at(0.5);
    const a = snap.bodies["block"]!.acceleration;
    nearVec(a, [-G * Math.sin(th) * Math.cos(th), -G * Math.sin(th) * Math.sin(th), 0]);
    near(len(a), 4.905);
    const normal = snap.forces.find((f) => f.kind === "normal")!;
    near(len(normal.vector), 5 * G * Math.cos(th));
    near(len(normal.vector), 42.4785, 1e-3);
  });

  it("closed form: from rest on the frictionless incline, distance after t is a t^2 / 2", () => {
    const { timeline } = solve(load(blockOnPlane({ angle: 30, mass: 5, s: 2, duration: 2 })));
    const p = timeline.at(0.8).bodies["block"]!.position;
    const slope = 2 - 0.5 * 4.905 * 0.8 ** 2;
    nearVec(p, [slope * Math.cos(deg(30)), slope * Math.sin(deg(30)), 0], 1e-9);
  });

  it("mu_s 0.6 at 30 deg: tan30 = 0.577 < 0.6 so the block sticks, f = m g sin30 = 24.525, a = 0", () => {
    const { timeline } = solve(
      load(blockOnPlane({ angle: 30, mass: 5, muS: 0.6, muK: 0.4, s: 2 })),
    );
    const snap = timeline.at(3);
    expect(len(snap.bodies["block"]!.acceleration)).toBeLessThan(1e-9);
    near(len(snap.bodies["block"]!.velocity), 0, 1e-9);
    const f = snap.forces.find((x) => x.kind === "friction")!;
    near(len(f.vector), 5 * G * Math.sin(deg(30)));
    expect(f.detail).toBe("static");
    expect(snap.contacts[0]?.mode).toBe("static");
  });

  it("40 deg, mu_s 0.5, mu_k 0.4: slides with a = g (sin40 - 0.4 cos40) = 3.2998", () => {
    const th = deg(40);
    const { timeline } = solve(
      load(blockOnPlane({ angle: 40, mass: 5, muS: 0.5, muK: 0.4, s: 3 })),
    );
    const snap = timeline.at(0.5);
    near(len(snap.bodies["block"]!.acceleration), G * (Math.sin(th) - 0.4 * Math.cos(th)));
    near(len(snap.bodies["block"]!.acceleration), 3.2998, 1e-3);
    const f = snap.forces.find((x) => x.kind === "friction")!;
    near(len(f.vector), 0.4 * 5 * G * Math.cos(th));
    expect(f.detail).toBe("kinetic");
    // Friction points up the slope, opposing the downhill motion.
    expect(f.vector[0]).toBeGreaterThan(0);
  });

  it("10 kg pushed with 50 N, mu_s 0.4 (max 39.24 N), mu_k 0.3: slides, a = (50 - 29.43)/10 = 2.057", () => {
    const { timeline } = solve(
      load(
        blockOnPlane({
          mass: 10,
          muS: 0.4,
          muK: 0.3,
          forces: [{ id: "push", kind: "applied", body: "block", vector: [50, 0, 0] }],
        }),
      ),
    );
    near(timeline.at(1).bodies["block"]!.acceleration[0], (50 - 0.3 * 10 * G) / 10);
    near(timeline.at(1).bodies["block"]!.acceleration[0], 2.057, 1e-3);
  });

  it("10 kg pushed with 30 N < 39.24 N: stays put, static friction = 30 N", () => {
    const { timeline } = solve(
      load(
        blockOnPlane({
          mass: 10,
          muS: 0.4,
          muK: 0.3,
          forces: [{ id: "push", kind: "applied", body: "block", vector: [30, 0, 0] }],
        }),
      ),
    );
    const snap = timeline.at(2);
    near(snap.bodies["block"]!.position[0], 0);
    near(len(snap.forces.find((f) => f.kind === "friction")!.vector), 30);
    near(len(snap.forces.find((f) => f.kind === "normal")!.vector), 98.1);
  });

  it("a force given as magnitude and angle above the floor: 100 N at 30 deg on 10 kg, frictionless: a_x = 86.60/10", () => {
    const { timeline } = solve(
      load(
        blockOnPlane({
          mass: 10,
          forces: [
            {
              id: "pull",
              kind: "applied",
              body: "block",
              magnitude: 100,
              directionAngle: deg(30),
              relativeTo: "plane",
            },
          ],
        }),
      ),
    );
    near(timeline.at(1).bodies["block"]!.acceleration[0], (100 * Math.cos(deg(30))) / 10);
    // Normal force is reduced: N = m g - F sin30 = 98.1 - 50
    near(len(timeline.at(1).forces.find((f) => f.kind === "normal")!.vector), 98.1 - 50);
  });

  it("projectile with no contact: v0 = (10, 10, 0), at t = 2: x = 20, y = 20 - 0.5 g 4 = 0.38", () => {
    const scene = load({
      version: 1,
      duration: 3,
      bodies: [{ id: "ball", mass: 1, position: [0, 0, 0], velocity: [10, 10, 0] }],
    });
    const { timeline } = solve(scene);
    nearVec(timeline.at(2).bodies["ball"]!.position, [20, 20 - 0.5 * G * 4, 0], 1e-9);
    nearVec(timeline.at(2).bodies["ball"]!.velocity, [10, 10 - 2 * G, 0], 1e-9);
  });

  it("the Timeline is a pure lookup: reading times backward gives the same states as forward", () => {
    const scene = load(blockOnPlane({ mass: 2, muS: 0.3, muK: 0.2, v0: 6, duration: 6 }));
    const { timeline } = solve(scene);
    const times = [0, 0.3, 0.9, 1.5, 2.2, 3.1, 4.4, 5.9];
    const forward = times.map((t) => timeline.at(t).bodies["block"]!.position);
    const backward = [...times]
      .reverse()
      .map((t) => timeline.at(t).bodies["block"]!.position)
      .reverse();
    expect(forward).toEqual(backward);
  });
});

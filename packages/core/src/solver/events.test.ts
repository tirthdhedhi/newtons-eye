import { describe, expect, it } from "vitest";
import { len } from "../math/vec3";
import { solve } from "./index";
import { G, blockOnPlane, deg, load } from "./testing";

const near = (a: number, b: number, tol = 1e-6) => expect(Math.abs(a - b)).toBeLessThan(tol);

describe("M4: events and segments", () => {
  it("v0 = 10 m/s on a floor, mu_k 0.5: a = -4.905, stops at t = 10/4.905 = 2.0387 s, travels 100/9.81 = 10.194 m", () => {
    const { timeline, answers } = solve(
      load(
        blockOnPlane({
          muS: 0.6,
          muK: 0.5,
          v0: 10,
          duration: 6,
          queries: [
            { id: "t", ask: "time", until: { event: "stop" } },
            { id: "d", ask: "distance", body: "block" },
          ],
        }),
      ),
    );
    near(answers[0]?.value as number, 10 / (0.5 * G), 1e-9);
    near(answers[0]?.value as number, 2.0387, 1e-3);
    near(answers[1]?.value as number, 100 / (2 * 0.5 * G), 1e-3);
    // After the stop the block stays put, held by static friction.
    expect(timeline.at(4).contacts[0]?.mode).toBe("static");
    near(timeline.at(4).bodies["block"]!.position[0], 100 / (2 * 0.5 * G), 1e-9);
    expect(timeline.events.map((e) => e.kind)).toContain("stop");
  });

  it("2 m frictionless 30 deg incline from the top: reaches the edge at t = sqrt(2*2/4.905) = 0.903 s with v = 4.43 m/s", () => {
    const { answers, timeline } = solve(
      load(
        blockOnPlane({
          angle: 30,
          mass: 5,
          s: 2,
          extent: 2,
          duration: 2,
          queries: [
            { id: "t", ask: "time", until: { event: "edge" } },
            { id: "v", ask: "velocity", body: "block", at: { event: "edge" } },
          ],
        }),
      ),
    );
    const t = Math.sqrt((2 * 2) / (G * 0.5));
    near(answers[0]?.value as number, t, 1e-5);
    near(len(answers[1]?.value as [number, number, number]), G * 0.5 * t, 1e-4);
    near(G * 0.5 * t, 4.43, 5e-3);
    // Past the edge the block is in free fall: the plane's normal force is gone.
    const after = timeline.at(1.5);
    expect(after.forces.some((f) => f.kind === "normal")).toBe(false);
    near(after.bodies["block"]!.acceleration[1], -G, 1e-9);
  });

  it("10 kg, 40 N applied during [0, 2] s, mu_k 0.2: accelerates then decelerates and stops at 4.077 s", () => {
    const mk = 0.2;
    const a1 = (40 - mk * 10 * G) / 10; // 2.038
    const v1 = a1 * 2;
    const x1 = 0.5 * a1 * 4;
    const a2 = mk * G; // 1.962 deceleration
    const tStop = 2 + v1 / a2;
    const xEnd = x1 + (v1 * v1) / (2 * a2);
    const { answers, timeline } = solve(
      load(
        blockOnPlane({
          mass: 10,
          muS: 0.3,
          muK: mk,
          duration: 8,
          forces: [
            { id: "push", kind: "applied", body: "block", vector: [40, 0, 0], during: [0, 2] },
          ],
          queries: [
            { id: "t", ask: "time", until: { event: "stop" } },
            { id: "d", ask: "distance", body: "block" },
          ],
        }),
      ),
    );
    near(answers[0]?.value as number, tStop, 1e-6);
    near(answers[1]?.value as number, xEnd, 1e-3);
    near(timeline.at(2).bodies["block"]!.velocity[0], v1, 1e-9);
    near(timeline.at(7).bodies["block"]!.position[0], xEnd, 1e-6);
  });

  it("slides up a 30 deg incline (mu 0.2), stops, then slides back down because tan30 > mu_s", () => {
    const mu = 0.2;
    const th = deg(30);
    const aUp = G * (Math.sin(th) + mu * Math.cos(th)); // 6.604
    const aDown = G * (Math.sin(th) - mu * Math.cos(th)); // 3.206
    const v0 = 5;
    const tStop = v0 / aUp;
    const sTop = (v0 * v0) / (2 * aUp);
    const { timeline } = solve(
      load(blockOnPlane({ angle: 30, muS: mu, muK: mu, v0, duration: 4 })),
    );
    const slope = (t: number) => {
      const p = timeline.at(t).bodies["block"]!.position;
      return p[0] * Math.cos(th) + p[1] * Math.sin(th);
    };
    near(slope(tStop), sTop, 1e-6);
    const t2 = tStop + 0.7;
    near(slope(t2), sTop - 0.5 * aDown * 0.7 ** 2, 1e-6);
    expect(timeline.events.filter((e) => e.kind === "stop")).toHaveLength(1);
  });

  it("a block released at t = 1 s from a frictionless 30 deg slope has moved 0.5 a (t - 1)^2 at t = 2", () => {
    const { timeline } = solve(
      load(
        blockOnPlane({
          angle: 30,
          s: 5,
          duration: 3,
          events: [{ id: "go", at: 1, kind: "release", target: "block" }],
        }),
      ),
    );
    const th = deg(30);
    const slope = (t: number) => {
      const p = timeline.at(t).bodies["block"]!.position;
      return p[0] * Math.cos(th) + p[1] * Math.sin(th);
    };
    near(slope(0.9), 5, 1e-9);
    near(slope(1), 5, 1e-9);
    near(slope(2), 5 - 0.5 * G * 0.5 * 1, 1e-9);
  });

  it("a ball dropped from 2 m onto the floor lands at t = sqrt(2h/g) = 0.639 s with its fall speed cancelled", () => {
    const scene = load({
      version: 1,
      duration: 2,
      bodies: [{ id: "ball", mass: 1, position: [0, 2, 0] }],
      surfaces: [
        { id: "floor", kind: "plane", point: [0, 0, 0], friction: { static: 0.5, kinetic: 0.4 } },
      ],
      contacts: [{ body: "ball", surface: "floor" }],
      queries: [{ id: "t", ask: "time", until: { event: "slide_start" } }],
    });
    const { timeline } = solve(scene);
    const tLand = Math.sqrt((2 * 2) / G);
    const landed = timeline.events.find((e) => e.kind === "land");
    near(landed?.t ?? -1, tLand, 1e-6);
    near(timeline.at(1.5).bodies["ball"]!.position[1], 0, 1e-9);
    near(timeline.at(1.5).bodies["ball"]!.velocity[1], 0, 1e-9);
    near(len(timeline.at(1.5).forces.find((f) => f.kind === "normal")!.vector), G, 1e-9);
  });
});

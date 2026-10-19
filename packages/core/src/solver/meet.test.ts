import { describe, expect, it } from "vitest";
import { parseScene } from "../validate";
import { solve } from "./index";

const G = 9.81;
const run = (json: unknown) => {
  const r = parseScene(json);
  if (!r.ok) throw new Error(JSON.stringify(r.errors));
  const { answers } = solve(r.scene);
  return Object.fromEntries(answers.map((a) => [a.id, a]));
};
const near = (a: unknown, b: number, tol = 1e-5) =>
  expect(Math.abs((a as number) - b)).toBeLessThan(tol);

describe("meet: two bodies reach the same place", () => {
  it("a ball thrown up at 20 m/s from the ground meets one dropped from 40 m at t = 40/20 = 2 s, at 40 - g*4/2 = 20.38 m", () => {
    const r = run({
      version: 1.1,
      bodies: [
        { id: "up", shape: { kind: "point" }, velocity: { speed: "20 m/s", angle: "90 deg" } },
        { id: "down", shape: { kind: "point" }, position: [0, 40, 0] },
      ],
      queries: [
        { id: "t", ask: "time", until: { event: "meet" }, body: "up", with: "down" },
        { id: "yu", ask: "position", body: "up", at: { event: "meet" } },
        { id: "yd", ask: "position", body: "down", at: { event: "meet" } },
      ],
    });
    near(r["t"]?.value, 2);
    near((r["yu"]?.value as number[])[1], 40 - 0.5 * G * 4);
    near((r["yd"]?.value as number[])[1], 40 - 0.5 * G * 4);
  });

  it("a car at 30 m/s passes a police car that starts from rest 3 s later at 5 m/s^2: they meet at t = 3 + (30 + sqrt(1800))/5 = 17.485 s, 524.56 m from the start", () => {
    const r = run({
      version: 1.1,
      bodies: [
        {
          id: "car",
          velocity: { speed: "30 m/s", angle: "0 deg" },
          constantAcceleration: "0 m/s^2",
        },
        { id: "police", constantAcceleration: "5 m/s^2" },
      ],
      events: [{ id: "go", at: "3 s", kind: "release", target: "police" }],
      queries: [
        { id: "t", ask: "time", until: { event: "meet" } },
        { id: "x", ask: "position", body: "police", at: { event: "meet" } },
      ],
    });
    const tau = (30 + Math.sqrt(900 + 900)) / 5;
    near(r["t"]?.value, 3 + tau, 1e-4);
    near((r["x"]?.value as number[])[0], 30 * (3 + tau), 1e-3);
    near(30 * (3 + tau), 524.56, 0.01);
  });

  it("bodies that start together meet again when the chaser catches up: 20 m/s against 2 m/s^2 from rest, at t = 2*20/2 = 20 s, 400 m", () => {
    const r = run({
      version: 1.1,
      bodies: [
        {
          id: "car",
          velocity: { speed: "20 m/s", angle: "0 deg" },
          constantAcceleration: "0 m/s^2",
        },
        { id: "police", constantAcceleration: "2 m/s^2" },
      ],
      queries: [
        { id: "t", ask: "time", until: { event: "meet" } },
        { id: "x", ask: "position", body: "car", at: { event: "meet" } },
      ],
    });
    near(r["t"]?.value, 20, 1e-4);
    near((r["x"]?.value as number[])[0], 400, 1e-2);
  });

  it("is answered for either body and in either order of `body` and `with`", () => {
    const scene = (body: string, withId: string) => ({
      version: 1.1,
      bodies: [
        { id: "a", constantAcceleration: "0 m/s^2", velocity: { speed: "10 m/s", angle: "0 deg" } },
        { id: "b", constantAcceleration: "0 m/s^2", position: [100, 0, 0], velocity: [0, 0, 0] },
      ],
      queries: [{ id: "t", ask: "time", until: { event: "meet" }, body, with: withId }],
    });
    near(run(scene("a", "b"))["t"]?.value, 10);
    near(run(scene("b", "a"))["t"]?.value, 10);
  });

  it("reports a clear error when the bodies never meet within the simulation", () => {
    const r = run({
      version: 1.1,
      bodies: [
        { id: "a", constantAcceleration: "0 m/s^2", velocity: [10, 0, 0] },
        { id: "b", constantAcceleration: "0 m/s^2", position: [100, 0, 0], velocity: [10, 0, 0] },
      ],
      queries: [{ id: "t", ask: "time", until: { event: "meet" } }],
    });
    expect(r["t"]?.error).toMatch(/never happens/);
  });

  it("needs two bodies, and a known `with`", () => {
    const one = parseScene({
      version: 1.1,
      bodies: [{ id: "a" }],
      queries: [{ id: "t", ask: "time", until: { event: "meet" } }],
    });
    expect(one.ok).toBe(false);
    const unknown = parseScene({
      version: 1.1,
      bodies: [{ id: "a" }, { id: "b", position: [1, 0, 0] }],
      queries: [{ id: "t", ask: "time", until: { event: "meet" }, body: "a", with: "zzz" }],
    });
    expect(unknown.ok).toBe(false);
  });
});

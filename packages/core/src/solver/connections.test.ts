import { describe, expect, it } from "vitest";
import { len } from "../math/vec3";
import { solve } from "./index";
import { G, load } from "./testing";

const near = (a: number, b: number, tol = 1e-6) => expect(Math.abs(a - b)).toBeLessThan(tol);

const atwood = () => ({
  version: 1,
  duration: 0.5,
  bodies: [
    { id: "m1", mass: 3, position: [-0.1, 2, 0] },
    { id: "m2", mass: 5, position: [0.1, 1, 0] },
  ],
  connections: [
    {
      id: "rope",
      kind: "pulley_string",
      a: "m1",
      b: "m2",
      pulley: { position: [0, 3, 0], endA: [-0.1, 3, 0], endB: [0.1, 3, 0] },
    },
  ],
  queries: [{ id: "T", ask: "force", force: "tension", connection: "rope", at: 0.1 }],
});

describe("M5: strings and pulleys", () => {
  it("Atwood machine, 3 kg and 5 kg: a = (5-3) g / 8 = 2.4525 m/s^2, T = 2 m1 m2 g / (m1+m2) = 36.7875 N", () => {
    const { timeline, answers } = solve(load(atwood()));
    const snap = timeline.at(0.3);
    near(snap.bodies["m1"]!.acceleration[1], (2 * G) / 8);
    near(snap.bodies["m2"]!.acceleration[1], -(2 * G) / 8);
    near(snap.bodies["m1"]!.acceleration[1], 2.4525, 1e-4);
    near(answers[0]?.value as number, (2 * 3 * 5 * G) / 8);
    near(answers[0]?.value as number, 36.7875, 1e-4);
    // Positions follow y = y0 +- a t^2 / 2 and the string length is conserved.
    near(snap.bodies["m1"]!.position[1], 2 + 0.5 * 2.4525 * 0.09, 1e-9);
    near(snap.bodies["m2"]!.position[1], 1 - 0.5 * 2.4525 * 0.09, 1e-9);
  });

  it("equal masses on the pulley string stay at rest with T = m g", () => {
    const sc = atwood();
    sc.bodies[1]!.mass = 3;
    const { timeline } = solve(load(sc));
    near(len(timeline.at(0.4).bodies["m1"]!.acceleration), 0, 1e-9);
    near(timeline.at(0.4).bodies["m1"]!.position[1], 2, 1e-9);
  });

  const table = (hangHeight: number) => ({
    version: 1,
    duration: 3,
    bodies: [
      { id: "cart", mass: 4, position: [-2, 1, 0] },
      { id: "hang", mass: 6, position: [0, hangHeight, 0] },
    ],
    surfaces: [
      { id: "table", kind: "plane", point: [0, 1, 0], friction: { static: 0.3, kinetic: 0.2 } },
      { id: "floor", kind: "plane", point: [0, 0, 0], friction: { static: 0.3, kinetic: 0.2 } },
    ],
    contacts: [
      { body: "cart", surface: "table" },
      { body: "hang", surface: "floor" },
    ],
    connections: [
      { id: "rope", kind: "pulley_string", a: "cart", b: "hang", pulley: { position: [0, 1, 0] } },
    ],
  });

  it("4 kg block on a table (mu_k 0.2) pulled by a 6 kg hanging block: a = (6g - 0.2*4g)/10 = 5.1012, T = 28.2528 N", () => {
    const sc = { ...table(0.5), duration: 0.4 };
    // keep the hanging block clear of the floor: contact only on the cart
    const scene = load({ ...sc, contacts: [{ body: "cart", surface: "table" }] });
    const { timeline } = solve(scene);
    const snap = timeline.at(0.2);
    const a = (6 * G - 0.2 * 4 * G) / 10;
    near(snap.bodies["cart"]!.acceleration[0], a);
    near(snap.bodies["cart"]!.acceleration[0], 5.1012, 1e-4);
    near(snap.bodies["hang"]!.acceleration[1], -a);
    const T = 4 * (a + 0.2 * G);
    near(len(snap.forces.find((f) => f.kind === "tension" && f.body === "hang")!.vector), T);
    near(T, 28.2528, 1e-4);
    // The hanging weight (58.86 N) beats static friction (0.3*39.24 = 11.77 N), so it slides.
    expect(snap.contacts[0]?.mode).toBe("sliding");
  });

  it("a light hanging block (1 kg, 9.81 N) cannot overcome static friction (0.3*39.24 = 11.77 N): nothing moves, T = m g", () => {
    const sc = table(0.5);
    sc.bodies[1]!.mass = 1;
    const { timeline } = solve(load({ ...sc, contacts: [{ body: "cart", surface: "table" }] }));
    const snap = timeline.at(2);
    near(len(snap.bodies["cart"]!.acceleration), 0, 1e-9);
    near(snap.bodies["cart"]!.position[0], -2, 1e-12);
    near(len(snap.forces.find((f) => f.kind === "tension" && f.body === "hang")!.vector), G, 1e-9);
    near(len(snap.forces.find((f) => f.kind === "friction")!.vector), G, 1e-9);
  });

  it("the hanging block lands after sqrt(2 h / a) = 0.4428 s from h = 0.5 m, then the string goes slack and the cart coasts to a stop under friction", () => {
    const { timeline, answers } = solve(
      load({
        ...table(0.5),
        queries: [
          { id: "slack", ask: "time", until: { event: "slack" } },
          { id: "stop", ask: "time", until: { event: "stop" }, body: "cart" },
        ],
      }),
    );
    const a = (6 * G - 0.2 * 4 * G) / 10;
    const tLand = Math.sqrt((2 * 0.5) / a);
    const vLand = a * tLand;
    const land = timeline.events.find((e) => e.kind === "land");
    near(land?.t ?? -1, tLand, 1e-6);
    // After landing the string is slack (no tension) and the cart decelerates at mu_k g.
    const snap = timeline.at(tLand + 0.3);
    expect(snap.strings[0]?.mode).toBe("slack");
    expect(snap.forces.some((f) => f.kind === "tension")).toBe(false);
    near(snap.bodies["hang"]!.position[1], 0, 1e-9);
    near(snap.bodies["cart"]!.acceleration[0], -0.2 * G, 1e-9);
    near(snap.bodies["cart"]!.velocity[0], vLand - 0.2 * G * 0.3, 1e-6);
    near(answers[1]?.value as number, tLand + vLand / (0.2 * G), 1e-5);
  });

  it("a direct string between two bodies pulled by a 20 N force: a = F/(m1+m2) = 2, T on the trailing block = m1 a", () => {
    const scene = load({
      version: 1,
      duration: 1,
      bodies: [
        { id: "front", mass: 6, position: [1, 0, 0] },
        { id: "back", mass: 4, position: [0, 0, 0] },
      ],
      surfaces: [{ id: "floor", kind: "plane", point: [0, 0, 0] }],
      contacts: [
        { body: "front", surface: "floor" },
        { body: "back", surface: "floor" },
      ],
      forces: [{ id: "pull", kind: "applied", body: "front", vector: [20, 0, 0] }],
      connections: [{ id: "cord", kind: "string", a: "front", b: "back" }],
      queries: [{ id: "T", ask: "force", force: "tension", connection: "cord", at: 0.5 }],
    });
    const { timeline, answers } = solve(scene);
    near(timeline.at(0.5).bodies["front"]!.acceleration[0], 2);
    near(timeline.at(0.5).bodies["back"]!.acceleration[0], 2);
    near(answers[0]?.value as number, 4 * 2);
  });

  it("a cut string frees the bodies: after cutting at 0.2 s both fall at g", () => {
    const sc = atwood();
    const scene = load({
      ...sc,
      duration: 0.6,
      events: [{ id: "snip", at: 0.2, kind: "cut_string", target: "rope" }],
    });
    const { timeline } = solve(scene);
    near(timeline.at(0.4).bodies["m1"]!.acceleration[1], -G, 1e-9);
    near(timeline.at(0.4).bodies["m2"]!.acceleration[1], -G, 1e-9);
  });
});

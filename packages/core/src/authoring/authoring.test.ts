import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseScene } from "../validate";
import { solve } from "../solver";

const dir = join(dirname(fileURLToPath(import.meta.url)), "../../../../examples");
const readJson = (f: string): unknown => JSON.parse(readFileSync(join(dir, f), "utf8"));

interface Expected {
  tolerance: number;
  answers: Record<string, { value: number | number[]; unit: string }>;
}

/** Examples written only with authoring sugar (no coordinates). */
const EXPRESSIBLE = [
  "floor-push",
  "incline-frictionless",
  "incline-sliding",
  "incline-static",
  "projectile",
  "projectile-flight",
  "building-throw",
  "sliding-stop",
  "spring-block",
];

describe("authoring examples: the sugar resolves to scenes that match the expected answers", () => {
  it.each(EXPRESSIBLE)("%s", (name) => {
    const parsed = parseScene(readJson(`${name}.authoring.json`));
    if (!parsed.ok) throw new Error(JSON.stringify(parsed.errors));
    const expected = readJson(`${name}.expected.json`) as Expected;
    const { answers } = solve(parsed.scene);
    expect(answers.length).toBeGreaterThan(0);
    for (const ans of answers) {
      const want = expected.answers[ans.id];
      expect(want, `expected answer for ${ans.id}`).toBeDefined();
      expect(ans.error, `${ans.id}: ${ans.error}`).toBeUndefined();
      expect(ans.unit).toBe(want?.unit);
      const got = [ans.value].flat() as number[];
      const exp = [want!.value].flat();
      expect(got.length, ans.id).toBe(exp.length);
      exp.forEach((c, i) =>
        expect(Math.abs(got[i]! - c), `${ans.id}[${i}]`).toBeLessThan(expected.tolerance),
      );
    }
  });
});

const base = (over: Record<string, unknown>) => ({
  version: 1.1,
  bodies: [{ id: "b", mass: 1 }],
  ...over,
});

function mustParse(json: unknown) {
  const r = parseScene(json);
  if (!r.ok) throw new Error(JSON.stringify(r.errors));
  return r;
}

describe("authoring resolution", () => {
  it("places a body flush at the top of a ramp exactly like the hand-written canonical scene", () => {
    const authored = mustParse(readJson("incline-sliding.authoring.json")).scene.bodies[0]!;
    const canonical = mustParse(readJson("incline-sliding.scene.json")).scene.bodies[0]!;
    authored.position.forEach((c, i) => expect(c).toBeCloseTo(canonical.position[i]!, 6));
    authored.orientation!.forEach((c, i) => expect(c).toBeCloseTo(canonical.orientation![i]!, 6));
  });

  it("reports every default and inference as a warning", () => {
    const { warnings } = mustParse(readJson("incline-sliding.authoring.json"));
    const text = warnings.map((w) => `${w.path}: ${w.message}`).join("\n");
    expect(text).toContain("has no shape");
    expect(text).toContain('placed at the top of "ramp"');
    expect(text).toContain("no duration given: simulating 2 s");
  });

  it("leaves canonical scenes untouched and warning-free of authoring notes", () => {
    const r = mustParse(readJson("incline-sliding.scene.json"));
    expect(r.scene.duration).toBe(2);
    expect(r.warnings).toEqual([]);
  });

  it("defaults the duration to the last referenced time + 1 s, at least 2 s", () => {
    const q = (at: number) => [{ id: "p", ask: "position", body: "b", at }];
    expect(mustParse(base({ queries: q(0.5) })).scene.duration).toBe(2);
    expect(mustParse(base({ queries: q(6) })).scene.duration).toBe(7);
    expect(mustParse(base({ duration: "9 s" })).scene.duration).toBe(9);
    const viaEvent = base({
      events: [{ id: "e", at: 4, kind: "release", target: "b" }],
      queries: [{ id: "p", ask: "position", body: "b", at: { event: "e" } }],
    });
    expect(mustParse(viaEvent).scene.duration).toBe(5);
  });

  it("resolves speed + along a plane in the up- or down-slope direction", () => {
    const scene = (direction: string) =>
      base({
        bodies: [{ id: "b", mass: 1, velocity: { speed: 2, along: "r", direction } }],
        surfaces: [{ id: "r", kind: "plane", angle: "30 deg" }],
      });
    const up = mustParse(scene("up")).scene.bodies[0]!.velocity!;
    const down = mustParse(scene("down")).scene.bodies[0]!.velocity!;
    expect(up[0]).toBeCloseTo(2 * Math.cos(Math.PI / 6), 9);
    expect(up[1]).toBeCloseTo(2 * Math.sin(Math.PI / 6), 9);
    expect(down[0]).toBeCloseTo(-up[0], 9);
  });

  it("puts a spring anchor at the natural-length point and starts the body stretched", () => {
    const r = mustParse(
      base({
        bodies: [{ id: "b", mass: 1, placement: { on: "f", offset: 1 } }],
        surfaces: [{ id: "f", kind: "plane" }],
        contacts: [{ body: "b", surface: "f" }],
        forces: [
          {
            id: "s",
            kind: "spring",
            body: "b",
            anchor: { fixed: true, stretch: 0.5 },
            k: 10,
            restLength: 0.2,
          },
        ],
      }),
    );
    expect(r.scene.bodies[0]!.position[0]).toBeCloseTo(1.5, 9);
    const f = r.scene.forces[0]!;
    expect(f.kind === "spring" && "point" in f.anchor && f.anchor.point[0]).toBeCloseTo(0.8, 9);
  });

  it("builds a table + hanging mass from edge_of and hangingFrom, matching the hand-written scene", () => {
    // The table's own position is still a coordinate here: see the table-hanging gap in docs/SCHEMA.md.
    const r = mustParse({
      version: 1.1,
      bodies: [
        { id: "cart", mass: 4, placement: { on: "table", at: 1 } },
        { id: "hang", mass: 6, placement: { hangingFrom: "rope", above: "floor", gap: 0.5 } },
      ],
      surfaces: [
        {
          id: "table",
          kind: "plane",
          point: [-3, 1, 0],
          extent: { length: 3 },
          friction: { static: 0.3, kinetic: 0.2 },
        },
        { id: "floor", kind: "plane", friction: { static: 0.3, kinetic: 0.2 } },
      ],
      contacts: [
        { body: "cart", surface: "table" },
        { body: "hang", surface: "floor" },
      ],
      connections: [
        {
          id: "rope",
          kind: "pulley_string",
          a: "cart",
          b: "hang",
          pulley: { position: { at: "edge_of", surface: "table" } },
        },
      ],
    });
    const [cart, hang] = r.scene.bodies;
    expect(cart!.position).toEqual([-2, 1.1, 0]);
    expect(hang!.position[0]).toBeCloseTo(0, 9);
    expect(hang!.position[1]).toBeCloseTo(0.6, 9);
    const c = r.scene.connections[0]!;
    expect(c.kind === "pulley_string" && c.pulley.position).toEqual([0, 1.1, 0]);
  });

  it("rejects what it cannot resolve, with the path of the offending field", () => {
    const bad = (over: Record<string, unknown>, path: string, message: RegExp) => {
      const r = parseScene(base(over));
      expect(r.ok).toBe(false);
      expect(r.ok ? [] : r.errors).toContainEqual({
        path,
        message: expect.stringMatching(message),
      });
    };
    bad(
      { bodies: [{ id: "b", mass: 1, placement: { on: "nope" } }] },
      "bodies[0].placement.on",
      /unknown surface/,
    );
    bad(
      {
        bodies: [{ id: "b", mass: 1, placement: { on: "f", at: "top" } }],
        surfaces: [{ id: "f", kind: "plane" }],
      },
      "bodies[0].placement.at",
      /no extent/,
    );
    bad(
      {
        bodies: [{ id: "b", mass: 1, position: [0, 0, 0], placement: { on: "f" } }],
        surfaces: [{ id: "f", kind: "plane" }],
      },
      "bodies[0].placement",
      /not both/,
    );
    bad(
      {
        bodies: [
          { id: "b", mass: 1 },
          { id: "c", mass: 1 },
        ],
        connections: [{ id: "r", kind: "pulley_string", a: "b", b: "c", pulley: {} }],
      },
      "connections[0].pulley.position",
      /no pulley position/,
    );
  });

  it("still rejects solver-computed keys in authoring scenes", () => {
    const r = parseScene(base({ bodies: [{ id: "b", mass: 1, acceleration: [0, 0, 0] }] }));
    expect(r.ok).toBe(false);
  });
});

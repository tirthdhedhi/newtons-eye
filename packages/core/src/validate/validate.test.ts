import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseScene } from "./index";

const examplesDir = join(dirname(fileURLToPath(import.meta.url)), "../../../../examples");
const readJson = (name: string): unknown =>
  JSON.parse(readFileSync(join(examplesDir, name), "utf8"));

const minimal = () => ({
  version: 1,
  bodies: [{ id: "b", mass: "2 g", position: [0, 0, 0] }],
});

function errorsOf(json: unknown): string {
  const r = parseScene(json);
  return r.ok ? "" : r.errors.map((e) => `${e.path}: ${e.message}`).join("\n");
}

describe("parseScene: examples", () => {
  const sceneFiles = readdirSync(examplesDir).filter((f) => f.endsWith(".scene.json"));

  it("finds at least one example", () => {
    expect(sceneFiles.length).toBeGreaterThan(0);
  });

  it.each(sceneFiles)("%s parses and converts to SI", (file) => {
    const r = parseScene(readJson(file));
    expect(r.ok).toBe(true);
  });

  it.each(sceneFiles)("%s has an expected-answers file covering every query", (file) => {
    const scene = readJson(file) as { queries: { id: string }[] };
    const expected = readJson(file.replace(".scene.json", ".expected.json")) as {
      answers: Record<string, unknown>;
    };
    expect(Object.keys(expected.answers).sort()).toEqual(scene.queries.map((q) => q.id).sort());
  });

  it("converts the incline example: 30 deg -> 0.5236 rad, 5 kg stays 5", () => {
    const r = parseScene(readJson("incline-frictionless.scene.json"));
    if (!r.ok) throw new Error(JSON.stringify(r.errors));
    expect(r.scene.surfaces[0]?.angle).toBeCloseTo(0.5236, 4);
    expect(r.scene.bodies[0]?.mass).toBe(5);
  });
});

describe("parseScene: defaults and units", () => {
  it('converts "2 g" to 0.002 kg and fills default gravity', () => {
    const r = parseScene(minimal());
    if (!r.ok) throw new Error(JSON.stringify(r.errors));
    expect(r.scene.bodies[0]?.mass).toBeCloseTo(0.002, 12);
    expect(r.scene.environment.gravity).toEqual([0, -9.81, 0]);
  });
});

describe("parseScene: derived quantities are rejected", () => {
  it.each(["normal", "tension", "acceleration", "answer"])("rejects a given '%s'", (key) => {
    const scene = minimal();
    (scene.bodies[0] as Record<string, unknown>)[key] = 5;
    const msg = errorsOf(scene);
    expect(msg).toContain(`"${key}"`);
    expect(msg).toContain("computed by the solver");
  });

  it("rejects unknown keys in general", () => {
    expect(errorsOf({ ...minimal(), foo: 1 })).not.toBe("");
  });
});

describe("parseScene: reference and range errors", () => {
  it("names the missing id for an unresolved reference", () => {
    const scene = { ...minimal(), contacts: [{ body: "ghost", surface: "floor" }] };
    const msg = errorsOf(scene);
    expect(msg).toContain('contacts[0].body: unknown body "ghost"');
    expect(msg).toContain('contacts[0].surface: unknown surface "floor"');
  });

  it("rejects duplicate ids", () => {
    const scene = {
      version: 1,
      bodies: [
        { id: "b", mass: 1, position: [0, 0, 0] },
        { id: "b", mass: 1, position: [1, 0, 0] },
      ],
    };
    expect(errorsOf(scene)).toContain('duplicate id "b"');
  });

  it("rejects zero mass unless the body is fixed", () => {
    const zero = { version: 1, bodies: [{ id: "b", mass: 0, position: [0, 0, 0] }] };
    expect(errorsOf(zero)).toContain("mass must be > 0");
    const fixed = { version: 1, bodies: [{ id: "b", mass: 0, position: [0, 0, 0], fixed: true }] };
    expect(parseScene(fixed).ok).toBe(true);
  });

  it("reports a wrong-dimension unit with its path", () => {
    const scene = { version: 1, bodies: [{ id: "b", mass: "3 m", position: [0, 0, 0] }] };
    expect(errorsOf(scene)).toContain("bodies[0].mass");
  });

  it("rejects an 'edge' time query when no surface has an extent", () => {
    const scene = { ...minimal(), queries: [{ id: "t", ask: "time", until: { event: "edge" } }] };
    expect(errorsOf(scene)).toContain('no surface has an "extent"');
  });

  it("warns when kinetic friction exceeds static friction", () => {
    const scene = {
      ...minimal(),
      surfaces: [
        { id: "s", kind: "plane", point: [0, 0, 0], friction: { static: 0.2, kinetic: 0.5 } },
      ],
    };
    const r = parseScene(scene);
    expect(r.ok).toBe(true);
    expect(r.warnings.map((w) => w.message).join()).toContain("kinetic friction exceeds static");
  });
});

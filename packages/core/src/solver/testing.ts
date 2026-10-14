import { parseScene } from "../validate";
import type { Scene } from "../schema";
import type { Vec3 } from "../math/vec3";
import { len, sub } from "../math/vec3";

/** Parse scene JSON for tests; throws with the readable issues if invalid. */
export function load(json: unknown): Scene {
  const r = parseScene(json);
  if (!r.ok) throw new Error(r.errors.map((e) => `${e.path}: ${e.message}`).join("; "));
  return r.scene;
}

export const G = 9.81;
export const deg = (d: number): number => (d * Math.PI) / 180;
export const dist = (a: Vec3, b: Vec3): number => len(sub(a, b));

/** A point mass on a plane through the origin, tilted `angle` degrees about z. */
export function blockOnPlane(opts: {
  angle?: number;
  mass?: number;
  muS?: number;
  muK?: number;
  /** Start distance up the slope. */
  s?: number;
  /** Initial speed up the slope (negative = down). */
  v0?: number;
  forces?: unknown[];
  events?: unknown[];
  extent?: number;
  duration?: number;
  queries?: unknown[];
}): unknown {
  const a = deg(opts.angle ?? 0);
  const s = opts.s ?? 0;
  const v0 = opts.v0 ?? 0;
  return {
    version: 1,
    duration: opts.duration ?? 5,
    bodies: [
      {
        id: "block",
        mass: opts.mass ?? 1,
        position: [s * Math.cos(a), s * Math.sin(a), 0],
        velocity: [v0 * Math.cos(a), v0 * Math.sin(a), 0],
      },
    ],
    surfaces: [
      {
        id: "plane",
        kind: "plane",
        point: [0, 0, 0],
        angle: a,
        friction: { static: opts.muS ?? 0, kinetic: opts.muK ?? 0 },
        ...(opts.extent !== undefined ? { extent: { length: opts.extent } } : {}),
      },
    ],
    contacts: [{ body: "block", surface: "plane" }],
    forces: opts.forces ?? [],
    events: opts.events ?? [],
    queries: opts.queries ?? [],
  };
}

import { dot, len, matCol, quatToMat, rotateAbout, scale, sub, unit } from "../math/vec3";
import type { Mat3, Quat, Vec3 } from "../math/vec3";
import type { Scene } from "../schema";
import type { Id, State } from "./types";

export const EPS_DIST = 1e-4; // contact distance counted as touching
export const EPS_LEN = 1e-9; // string slack/taut tolerance
export const EPS_EDGE = 1e-6;
export const EPS_V = 1e-9; // speed counted as zero
export const EPS_F = 1e-9; // force tolerance

export interface PlaneModel {
  id: Id;
  P: Vec3;
  /** Unit normal. */
  n: Vec3;
  /** Up-slope tangent. */
  u: Vec3;
  /** In-plane tangent along the rotation axis. */
  w: Vec3;
  extent?: { length: number; width?: number };
}

export interface ContactModel {
  body: number;
  plane: number;
  muS: number;
  muK: number;
  /** Distance from body center to the body's surface along the plane normal. */
  support: number;
}

export interface StringModel {
  index: number;
  id: Id;
  kind: "direct" | "pulley";
  a: number;
  b: number;
  length: number;
  cutAt: number;
  PA: Vec3;
  PB: Vec3;
}

export interface Model {
  scene: Scene;
  ids: Id[];
  index: Map<Id, number>;
  mass: number[];
  fixed: boolean[];
  /** Time a body is released, or undefined if never held. */
  releaseAt: (number | undefined)[];
  rot: Mat3[];
  g: Vec3;
  planes: PlaneModel[];
  planeIndex: Map<Id, number>;
  contacts: ContactModel[];
  strings: StringModel[];
  /** Times at which the force set or constraint set changes. */
  breakpoints: number[];
}

export function planeBasis(angle: number, axis: Vec3): { n: Vec3; u: Vec3; w: Vec3 } {
  const w = unit(axis);
  const u = rotateAbout([1, 0, 0], w, angle);
  const n = rotateAbout([0, 1, 0], w, angle);
  return { n, u, w };
}

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

export function buildModel(scene: Scene): Model {
  const ids = scene.bodies.map((b) => b.id);
  const index = new Map(ids.map((id, i) => [id, i]));
  const rot = scene.bodies.map((b) => quatToMat((b.orientation ?? [0, 0, 0, 1]) as Quat));
  const planes: PlaneModel[] = scene.surfaces.map((s) => {
    const { n, u, w } = planeBasis(s.angle, s.axis);
    return { id: s.id, P: s.point, n, u, w, ...(s.extent ? { extent: s.extent } : {}) };
  });
  const planeIndex = new Map(planes.map((p, i) => [p.id, i]));

  const releaseAt = scene.bodies.map((b) => {
    const times = scene.events
      .filter((e) => e.kind === "release" && e.target === b.id)
      .map((e) => e.at);
    return times.length ? Math.min(...times) : undefined;
  });

  const contacts: ContactModel[] = scene.contacts.map((c) => {
    const bi = index.get(c.body) ?? 0;
    const pi = planeIndex.get(c.surface) ?? 0;
    const surf = get(scene.surfaces, pi);
    const fr = c.friction ?? surf.friction;
    const body = get(scene.bodies, bi);
    const n = get(planes, pi).n;
    const R = get(rot, bi);
    let support = 0;
    if (body.shape.kind === "sphere") support = body.shape.radius;
    else if (body.shape.kind === "box") {
      const size = body.shape.size;
      support =
        (Math.abs(dot(n, matCol(R, 0))) * size[0] +
          Math.abs(dot(n, matCol(R, 1))) * size[1] +
          Math.abs(dot(n, matCol(R, 2))) * size[2]) /
        2;
    }
    return { body: bi, plane: pi, muS: fr.static, muK: fr.kinetic, support };
  });

  const x0 = scene.bodies.map((b) => b.position);
  const strings: StringModel[] = scene.connections.map((c, index_) => {
    const a = index.get(c.a) ?? 0;
    const b = index.get(c.b) ?? 0;
    const xa = get(x0, a);
    const xb = get(x0, b);
    const cut = scene.events
      .filter((e) => e.kind === "cut_string" && e.target === c.id)
      .map((e) => e.at);
    const cutAt = cut.length ? Math.min(...cut) : Infinity;
    if (c.kind === "string") {
      return {
        index: index_,
        id: c.id,
        kind: "direct",
        a,
        b,
        length: c.length ?? len(sub(xa, xb)),
        cutAt,
        PA: xa,
        PB: xb,
      };
    }
    const PA = c.pulley.endA ?? c.pulley.position;
    const PB = c.pulley.endB ?? c.pulley.position;
    return {
      index: index_,
      id: c.id,
      kind: "pulley",
      a,
      b,
      length: c.length ?? len(sub(xa, PA)) + len(sub(xb, PB)),
      cutAt,
      PA,
      PB,
    };
  });

  const bp = new Set<number>();
  for (const e of scene.events) bp.add(e.at);
  for (const f of scene.forces) {
    if (f.kind === "applied" && f.during) {
      bp.add(f.during[0]);
      if (f.during[1] !== null) bp.add(f.during[1]);
    }
  }
  const breakpoints = [...bp].filter((t) => t > 0 && t < scene.duration).sort((p, q) => p - q);

  return {
    scene,
    ids,
    index,
    mass: scene.bodies.map((b) => b.mass),
    fixed: scene.bodies.map((b) => b.fixed === true),
    releaseAt,
    rot,
    g: scene.environment.gravity,
    planes,
    planeIndex,
    contacts,
    strings,
    breakpoints,
  };
}

export function initialState(m: Model): State {
  return {
    x: m.scene.bodies.map((b) => [...b.position] as Vec3),
    v: m.scene.bodies.map((b) => [...(b.velocity ?? [0, 0, 0])] as Vec3),
  };
}

export const isHeld = (m: Model, i: number, t: number): boolean => {
  const r = m.releaseAt[i];
  return r !== undefined && t < r;
};

/** A body whose motion is prescribed (fixed, or held until its release). */
export const isPinned = (m: Model, i: number, t: number): boolean =>
  m.fixed[i] === true || isHeld(m, i, t);

export function signedDistance(m: Model, c: ContactModel, s: State): number {
  const plane = get(m.planes, c.plane);
  return dot(plane.n, sub(get(s.x, c.body), plane.P)) - c.support;
}

/** How far outside the plane's finite extent a body center is (<= 0 means inside). */
export function outsideExtent(m: Model, c: ContactModel, s: State): number {
  const plane = get(m.planes, c.plane);
  if (!plane.extent) return -Infinity;
  const d = sub(get(s.x, c.body), plane.P);
  const sCoord = dot(plane.u, d);
  let out = Math.max(-sCoord, sCoord - plane.extent.length);
  if (plane.extent.width !== undefined)
    out = Math.max(out, Math.abs(dot(plane.w, d)) - plane.extent.width / 2);
  return out;
}

/** Tangential velocity of a body relative to its (static) contact plane. */
export function tangentialVelocity(m: Model, c: ContactModel, s: State): Vec3 {
  const n = get(m.planes, c.plane).n;
  const v = get(s.v, c.body);
  return sub(v, scale(n, dot(v, n)));
}

export interface StringGeometry {
  /** Current string length measure minus the string's length (>= 0 when taut). */
  gap: number;
  /** Unit direction from the far end/pulley toward each body (see solveInstant). */
  ua: Vec3;
  ub: Vec3;
  da: number;
  db: number;
  /** Rate of change of the length measure. */
  rate: number;
}

export function stringGeometry(str: StringModel, s: State): StringGeometry {
  const xa = get(s.x, str.a);
  const xb = get(s.x, str.b);
  const va = get(s.v, str.a);
  const vb = get(s.v, str.b);
  if (str.kind === "direct") {
    const d = sub(xa, xb);
    const L = len(d) || 1e-300;
    const u = scale(d, 1 / L);
    return { gap: L - str.length, ua: u, ub: u, da: L, db: L, rate: dot(u, sub(va, vb)) };
  }
  const ra = sub(xa, str.PA);
  const rb = sub(xb, str.PB);
  const da = len(ra) || 1e-300;
  const db = len(rb) || 1e-300;
  const ua = scale(ra, 1 / da);
  const ub = scale(rb, 1 / db);
  return { gap: da + db - str.length, ua, ub, da, db, rate: dot(ua, va) + dot(ub, vb) };
}

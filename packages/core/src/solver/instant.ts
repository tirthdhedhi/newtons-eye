import { linsolve } from "../math/linsolve";
import { add, axpy, dot, len, matVec, scale, sub, unit } from "../math/vec3";
import type { Vec3 } from "../math/vec3";
import type { Force } from "../schema";
import { EPS_V, isPinned, stringGeometry, tangentialVelocity } from "./model";
import type { Model } from "./model";
import type { ForceRecord, Regimes, State } from "./types";

export interface Instant {
  ok: boolean;
  acc: Vec3[];
  /** Normal force magnitude per contact (0 if inactive). */
  N: number[];
  /** Static friction force on the body per contact. */
  fs: Vec3[];
  /** Direction used for kinetic friction on the body per contact (zero if not sliding). */
  fkDir: Vec3[];
  /** Tension per connection (0 if not taut). */
  T: number[];
  forces: ForceRecord[];
}

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

function forceActive(f: Force, t: number): boolean {
  if (f.kind === "applied" && f.during) {
    const [on, off] = f.during;
    return t >= on && (off === null || t < off);
  }
  return true;
}

/** The vector of an applied force at time t (set_force events replace it). */
function appliedVector(m: Model, f: Force, t: number): Vec3 {
  if (f.kind !== "applied") return [0, 0, 0];
  let base: Vec3;
  if ("vector" in f) {
    base = f.vector;
    const ev = m.scene.events
      .filter((e) => e.kind === "set_force" && e.target === f.id && e.at <= t)
      .sort((p, q) => q.at - p.at)[0];
    if (ev && ev.kind === "set_force") base = ev.vector;
    const bi = m.index.get(f.body) ?? 0;
    if (f.frame === "body") return matVec(get(m.rot, bi), base);
    if (f.frame === "surface") {
      const p = get(m.planes, m.planeIndex.get(f.surface ?? "") ?? 0);
      return add(add(scale(p.u, base[0]), scale(p.n, base[1])), scale(p.w, base[2]));
    }
    return base;
  }
  const p = get(m.planes, m.planeIndex.get(f.relativeTo) ?? 0);
  return add(
    scale(p.u, f.magnitude * Math.cos(f.directionAngle)),
    scale(p.n, f.magnitude * Math.sin(f.directionAngle)),
  );
}

function pointOf(
  m: Model,
  bi: number,
  s: State,
  at?: { frame: "body" | "world"; offset?: Vec3 },
): Vec3 {
  const x = get(s.x, bi);
  if (!at?.offset) return x;
  return at.frame === "body" ? add(x, matVec(get(m.rot, bi), at.offset)) : add(x, at.offset);
}

/**
 * Accelerations and constraint forces for one regime assignment at one state.
 * Builds a single linear system: body force balances, contact constraints, string constraints.
 */
export function solveInstant(
  m: Model,
  reg: Regimes,
  s: State,
  t: number,
  wantForces: boolean,
): Instant {
  const nb = m.ids.length;
  const movCol: number[] = new Array<number>(nb).fill(-1);
  let nm = 0;
  for (let i = 0; i < nb; i++) if (!isPinned(m, i, t)) movCol[i] = 3 * nm++;

  // Known forces on every body (gravity, applied, springs).
  const known: Vec3[] = m.ids.map((_, i) => scale(m.g, get(m.mass, i)));
  const records: ForceRecord[] = [];
  const push = (r: ForceRecord) => {
    if (wantForces) records.push(r);
  };
  m.ids.forEach((id, i) => {
    push({
      id: `gravity:${id}`,
      kind: "gravity",
      body: id,
      vector: scale(m.g, get(m.mass, i)),
      point: get(s.x, i),
    });
  });
  for (const f of m.scene.forces) {
    if (!forceActive(f, t)) continue;
    const bi = m.index.get(f.body) ?? 0;
    if (f.kind === "applied") {
      const F = appliedVector(m, f, t);
      known[bi] = add(get(known, bi), F);
      push({ id: f.id, kind: "applied", body: f.body, vector: F, point: pointOf(m, bi, s, f.at) });
    } else {
      const pBody = pointOf(m, bi, s, f.at);
      let pAnchor: Vec3;
      let ai = -1;
      if ("body" in f.anchor) {
        ai = m.index.get(f.anchor.body) ?? 0;
        pAnchor = pointOf(m, ai, s, f.anchorAt);
      } else pAnchor = f.anchor.point;
      const d = sub(pBody, pAnchor);
      const L = len(d);
      const F: Vec3 = L < 1e-12 ? [0, 0, 0] : scale(d, (-f.k * (L - f.restLength)) / L);
      known[bi] = add(get(known, bi), F);
      push({ id: f.id, kind: "spring", body: f.body, vector: F, point: pBody });
      if (ai >= 0) {
        known[ai] = sub(get(known, ai), F);
        push({
          id: `${f.id}:anchor`,
          kind: "spring",
          body: f.anchor && "body" in f.anchor ? f.anchor.body : f.body,
          vector: scale(F, -1),
          point: pAnchor,
        });
      }
    }
  }

  // Unknown columns after the accelerations.
  let col = 3 * nm;
  const nCol: number[] = [];
  const fCol: number[] = [];
  const fkDir: Vec3[] = [];
  m.contacts.forEach((c, ci) => {
    const mode = get(reg.contacts, ci);
    const active = mode !== "inactive" && !isPinned(m, c.body, t);
    nCol[ci] = active ? col++ : -1;
    fCol[ci] = active && mode === "static" ? col : -1;
    if (active && mode === "static") col += 2;
    let d: Vec3 = [0, 0, 0];
    if (active && mode === "sliding") {
      const vt = tangentialVelocity(m, c, s);
      d = len(vt) > EPS_V ? scale(unit(vt), -1) : (reg.slideDir[ci] ?? [0, 0, 0]);
    }
    fkDir[ci] = d;
  });
  const tCol: number[] = [];
  m.strings.forEach((st, j) => {
    const taut = get(reg.strings, j) === "taut" && t < st.cutAt;
    tCol[j] = taut ? col++ : -1;
  });
  const n = col;
  const A: number[][] = Array.from({ length: n }, () => new Array<number>(n).fill(0));
  const b: number[] = new Array<number>(n).fill(0);
  let row = 0;

  // Body force balances.
  const rowOfBody: number[] = new Array<number>(nb).fill(-1);
  for (let i = 0; i < nb; i++) {
    const mc = get(movCol, i);
    if (mc < 0) continue;
    rowOfBody[i] = row;
    for (let k = 0; k < 3; k++) {
      const r = get(A, row + k);
      r[mc + k] = get(m.mass, i);
      b[row + k] = get(known, i)[k as 0 | 1 | 2];
    }
    row += 3;
  }
  const addToBody = (bi: number, colIdx: number, vec: Vec3, sign: number) => {
    const r0 = get(rowOfBody, bi);
    if (r0 < 0) return;
    for (let k = 0; k < 3; k++) {
      const r = get(A, r0 + k);
      r[colIdx] = (r[colIdx] ?? 0) - sign * vec[k as 0 | 1 | 2];
    }
  };

  // Contact constraints.
  m.contacts.forEach((c, ci) => {
    const nc = get(nCol, ci);
    if (nc < 0) return;
    const plane = get(m.planes, c.plane);
    addToBody(c.body, nc, plane.n, 1);
    if (get(fkDir, ci)[0] !== 0 || get(fkDir, ci)[1] !== 0 || get(fkDir, ci)[2] !== 0) {
      addToBody(c.body, nc, scale(get(fkDir, ci), c.muK), 1);
    }
    const mc = get(movCol, c.body);
    const setRow = (dir: Vec3) => {
      const r = get(A, row);
      for (let k = 0; k < 3; k++) r[mc + k] = dir[k as 0 | 1 | 2];
      row++;
    };
    setRow(plane.n);
    const fc = get(fCol, ci);
    if (fc >= 0) {
      addToBody(c.body, fc, plane.u, 1);
      addToBody(c.body, fc + 1, plane.w, 1);
      setRow(plane.u);
      setRow(plane.w);
    }
  });

  // String constraints.
  m.strings.forEach((st, j) => {
    const tc = get(tCol, j);
    if (tc < 0) return;
    const geo = stringGeometry(st, s);
    const va = get(s.v, st.a);
    const vb = get(s.v, st.b);
    const ca = get(movCol, st.a);
    const cb = get(movCol, st.b);
    const r = get(A, row);
    let curv: number;
    if (st.kind === "direct") {
      const w = sub(va, vb);
      curv = (dot(w, w) - dot(geo.ua, w) ** 2) / geo.da;
      for (let k = 0; k < 3; k++) {
        if (ca >= 0) r[ca + k] = geo.ua[k as 0 | 1 | 2];
        if (cb >= 0) r[cb + k] = -geo.ua[k as 0 | 1 | 2];
      }
      addToBody(st.a, tc, geo.ua, -1);
      addToBody(st.b, tc, geo.ua, 1);
    } else {
      curv =
        (dot(va, va) - dot(geo.ua, va) ** 2) / geo.da +
        (dot(vb, vb) - dot(geo.ub, vb) ** 2) / geo.db;
      for (let k = 0; k < 3; k++) {
        if (ca >= 0) r[ca + k] = geo.ua[k as 0 | 1 | 2];
        if (cb >= 0) r[cb + k] = geo.ub[k as 0 | 1 | 2];
      }
      addToBody(st.a, tc, geo.ua, -1);
      addToBody(st.b, tc, geo.ub, -1);
    }
    b[row] = -curv;
    row++;
  });

  const empty: Instant = {
    ok: true,
    acc: m.ids.map(() => [0, 0, 0] as Vec3),
    N: m.contacts.map(() => 0),
    fs: m.contacts.map(() => [0, 0, 0] as Vec3),
    fkDir,
    T: m.strings.map(() => 0),
    forces: records,
  };
  if (n === 0) return empty;
  const x = linsolve(A, b);
  if (!x) return { ...empty, ok: false };

  const acc: Vec3[] = m.ids.map((_, i) => {
    const mc = get(movCol, i);
    return mc < 0 ? ([0, 0, 0] as Vec3) : ([get(x, mc), get(x, mc + 1), get(x, mc + 2)] as Vec3);
  });
  const N = m.contacts.map((_, ci) => (get(nCol, ci) >= 0 ? get(x, get(nCol, ci)) : 0));
  const fs = m.contacts.map((c, ci) => {
    const fc = get(fCol, ci);
    if (fc < 0) return [0, 0, 0] as Vec3;
    const plane = get(m.planes, c.plane);
    return add(scale(plane.u, get(x, fc)), scale(plane.w, get(x, fc + 1)));
  });
  const T = m.strings.map((_, j) => (get(tCol, j) >= 0 ? get(x, get(tCol, j)) : 0));

  if (wantForces) {
    m.contacts.forEach((c, ci) => {
      if (get(nCol, ci) < 0) return;
      const plane = get(m.planes, c.plane);
      const body = get(m.ids, c.body);
      const pt = axpy(get(s.x, c.body), plane.n, -c.support);
      records.push({
        id: `normal:${body}`,
        kind: "normal",
        body,
        vector: scale(plane.n, get(N, ci)),
        point: pt,
      });
      if (get(fCol, ci) >= 0) {
        records.push({
          id: `friction:${body}`,
          kind: "friction",
          body,
          vector: get(fs, ci),
          point: pt,
          detail: "static",
        });
      } else if (len(get(fkDir, ci)) > 0) {
        records.push({
          id: `friction:${body}`,
          kind: "friction",
          body,
          vector: scale(get(fkDir, ci), c.muK * get(N, ci)),
          point: pt,
          detail: "kinetic",
        });
      }
    });
    m.strings.forEach((st, j) => {
      if (get(tCol, j) < 0) return;
      const geo = stringGeometry(st, s);
      const Tj = get(T, j);
      const fa = st.kind === "direct" ? scale(geo.ua, -Tj) : scale(geo.ua, -Tj);
      const fb = st.kind === "direct" ? scale(geo.ua, Tj) : scale(geo.ub, -Tj);
      records.push({
        id: `${st.id}:a`,
        kind: "tension",
        body: get(m.ids, st.a),
        vector: fa,
        point: get(s.x, st.a),
      });
      records.push({
        id: `${st.id}:b`,
        kind: "tension",
        body: get(m.ids, st.b),
        vector: fb,
        point: get(s.x, st.b),
      });
    });
  }

  return { ok: true, acc, N, fs, fkDir, T, forces: records };
}

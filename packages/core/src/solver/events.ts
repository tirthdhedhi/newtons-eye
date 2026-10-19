import { dot, len, scale, sub, unit } from "../math/vec3";
import { solveInstant } from "./instant";
import {
  EPS_DIST,
  EPS_EDGE,
  EPS_F,
  EPS_LEN,
  EPS_V,
  isPinned,
  outsideExtent,
  signedDistance,
  stringGeometry,
  tangentialVelocity,
} from "./model";
import type { Model } from "./model";
import type { EventKind, Motion, Regimes, State } from "./types";

/** A condition that becomes true at some time inside a segment. */
export interface Candidate {
  kind: EventKind;
  contact?: number;
  string?: number;
  /** For `meet`: indices of the two bodies. */
  pair?: [number, number];
  /** Latches to true once the opposite condition has been seen (avoids re-firing at t0). */
  armed: boolean;
  arm(t: number, s: State): boolean;
  test(t: number, s: State): boolean;
}

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

export function buildCandidates(
  m: Model,
  reg: Regimes,
  start: State,
  t0: number,
  detached: boolean[],
  isRk4: boolean,
): Candidate[] {
  const out: Candidate[] = [];
  m.contacts.forEach((c, ci) => {
    if (get(detached, ci) || isPinned(m, c.body, t0)) return;
    const mode = get(reg.contacts, ci);
    if (mode === "inactive") {
      // Landing: the body is above the plane and comes down onto it, inside the extent.
      out.push({
        kind: "land",
        contact: ci,
        armed: signedDistance(m, c, start) > EPS_DIST,
        arm: (_t, s) => signedDistance(m, c, s) > EPS_DIST,
        test: (_t, s) => signedDistance(m, c, s) <= 0 && outsideExtent(m, c, s) <= EPS_EDGE,
      });
      return;
    }
    if (mode === "sliding") {
      const vt0 = tangentialVelocity(m, c, start);
      const moving = len(vt0) > EPS_V;
      const sd = get(reg.slideDir, ci);
      const d0 = moving ? unit(vt0) : sd ? scale(sd, -1) : null;
      if (d0) {
        out.push({
          kind: "stop",
          contact: ci,
          armed: moving,
          arm: (_t, s) => dot(tangentialVelocity(m, c, s), d0) > 1e-6,
          test: (_t, s) => dot(tangentialVelocity(m, c, s), d0) <= EPS_V,
        });
      }
    }
    // Leaving the finite extent.
    if (get(m.planes, c.plane).extent) {
      out.push({
        kind: "edge",
        contact: ci,
        armed: true,
        arm: () => true,
        test: (_t, s) => outsideExtent(m, c, s) > EPS_EDGE,
      });
    }
    if (isRk4) {
      out.push({
        kind: "lift",
        contact: ci,
        armed: true,
        arm: () => true,
        test: (t, s) => get(solveInstant(m, reg, s, t, false).N, ci) < -EPS_F,
      });
      if (mode === "static") {
        out.push({
          kind: "slide_start",
          contact: ci,
          armed: true,
          arm: () => true,
          test: (t, s) => {
            const inst = solveInstant(m, reg, s, t, false);
            return len(get(inst.fs, ci)) > c.muS * get(inst.N, ci) + 1e-9;
          },
        });
      }
    }
  });
  // Two bodies meet when their separation along the initial line between them reaches zero.
  for (let i = 0; i < m.ids.length; i++) {
    for (let j = i + 1; j < m.ids.length; j++) {
      const rel0 = sub(get(start.x, i), get(start.x, j));
      if (len(rel0) < EPS_DIST) continue;
      const e = unit(rel0);
      const along = (s: State) => dot(sub(get(s.x, i), get(s.x, j)), e);
      out.push({
        kind: "meet",
        pair: [i, j],
        armed: along(start) > EPS_DIST,
        arm: (_t, s) => along(s) > EPS_DIST,
        test: (_t, s) => along(s) <= 0,
      });
    }
  }
  m.strings.forEach((st, j) => {
    const mode = get(reg.strings, j);
    if (mode === "cut") return;
    if (mode === "slack") {
      out.push({
        kind: "taut",
        string: j,
        armed: stringGeometry(st, start).gap < -EPS_LEN,
        arm: (_t, s) => stringGeometry(st, s).gap < -EPS_LEN,
        test: (_t, s) => stringGeometry(st, s).gap >= -EPS_LEN,
      });
    } else if (isRk4) {
      out.push({
        kind: "slack",
        string: j,
        armed: true,
        arm: () => true,
        test: (t, s) => get(solveInstant(m, reg, s, t, false).T, j) < -EPS_F,
      });
    }
  });
  return out;
}

export interface Found {
  t: number;
  candidate: Candidate;
}

const CHUNK = 0.25;
const SAMPLE = 0.0025;

/**
 * Earliest time in (t0, tEnd] at which any candidate becomes true.
 * Scans in small steps, then bisects the step that contains the crossing.
 */
export function findEarliest(
  motion: Motion,
  cands: Candidate[],
  t0: number,
  tEnd: number,
): Found | null {
  if (cands.length === 0) return null;
  let prev = t0;
  let prevState = motion.stateAt(t0);
  for (const c of cands) if (!c.armed) c.armed = c.arm(t0, prevState);
  for (let chunk = t0; chunk < tEnd; chunk += CHUNK) {
    const chunkEnd = Math.min(tEnd, chunk + CHUNK);
    const n = Math.max(1, Math.ceil((chunkEnd - chunk) / SAMPLE));
    for (let i = 1; i <= n; i++) {
      const t = chunk + ((chunkEnd - chunk) * i) / n;
      const s = motion.stateAt(t);
      let best: Candidate | null = null;
      for (const c of cands) {
        if (c.armed && c.test(t, s)) {
          best = c;
          break;
        }
      }
      if (best) {
        // Bisect for the earliest time any armed candidate fires inside (prev, t].
        let lo = prev;
        let hi = t;
        let who: Candidate = best;
        for (let it = 0; it < 60 && hi - lo > 1e-13; it++) {
          const mid = 0.5 * (lo + hi);
          const sm = motion.stateAt(mid);
          const hit = cands.find((c) => c.armed && c.test(mid, sm));
          if (hit) {
            hi = mid;
            who = hit;
          } else lo = mid;
        }
        return { t: hi, candidate: who };
      }
      for (const c of cands) if (!c.armed) c.armed = c.arm(t, s);
      prev = t;
      prevState = s;
    }
  }
  void prevState;
  return null;
}

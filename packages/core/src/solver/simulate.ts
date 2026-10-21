import { dot, len, scale, sub } from "../math/vec3";
import type { Quat, Vec3 } from "../math/vec3";
import { buildCandidates, findEarliest } from "./events";
import type { Found } from "./events";
import { solveInstant } from "./instant";
import { buildModel, initialState, isPinned, tangentialVelocity } from "./model";
import type { Model } from "./model";
import { analyticMotion, rk4Motion } from "./motion";
import { enforceStrings, selectRegimes } from "./regimes";
import type { Scene } from "../schema";
import type { Motion, Regimes, Segment, Snapshot, SolvedEvent, State } from "./types";

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

export interface Timeline {
  duration: number;
  segments: Segment[];
  events: SolvedEvent[];
  model: Model;
  /** State and forces at any time. Pure lookup: scrubbing backward works. */
  at(t: number): Snapshot;
  /** Positions and velocities only (cheaper than at). */
  stateAt(t: number): State;
}

const MAX_SEGMENTS = 400;
const cloneState = (s: State): State => ({
  x: s.x.map((v) => [...v] as Vec3),
  v: s.v.map((v) => [...v] as Vec3),
});

const needsRk4 = (m: Model): boolean => m.scene.forces.some((f) => f.kind === "spring");

/** True when re-solving at several states inside the segment gives the same accelerations. */
function accelerationIsConstant(
  m: Model,
  reg: Regimes,
  motion: Motion,
  t0: number,
  t1: number,
  acc0: Vec3[],
): boolean {
  for (const f of [0.25, 0.5, 0.75, 0.99]) {
    const t = t0 + (t1 - t0) * f;
    const inst = solveInstant(m, reg, motion.stateAt(t), Math.min(t, t1 - 1e-12), false);
    if (!inst.ok) return false;
    for (let i = 0; i < acc0.length; i++) {
      const a = get(inst.acc, i);
      const b = get(acc0, i);
      if (len(sub(a, b)) > 1e-7 * (1 + len(b))) return false;
    }
  }
  return true;
}

export function simulate(scene: Scene): Timeline {
  const m = buildModel(scene);
  const duration = scene.duration;
  const detached: boolean[] = m.contacts.map(() => false);
  const segments: Segment[] = [];
  const events: SolvedEvent[] = [];

  let t = 0;
  let state = initialState(m);
  const note = (e: SolvedEvent) => events.push(e);

  const prepare = (tt: number) => {
    for (const id of enforceStrings(m, state, tt, detached)) {
      note({ t: tt, kind: "taut", connection: id, description: `string ${id} snaps taut` });
    }
    return selectRegimes(m, state, tt, detached);
  };
  let { regimes, instant } = prepare(t);

  while (t < duration - 1e-12 && segments.length < MAX_SEGMENTS) {
    const nextBp = m.breakpoints.find((b) => b > t + 1e-12) ?? Infinity;
    const tEnd = Math.min(duration, nextBp);
    const useRk4 = needsRk4(m);

    let motion: Motion;
    let found: Found | null;
    const tryAnalytic = (): { motion: Motion; found: Found | null } | null => {
      const mo = analyticMotion(t, state, instant.acc);
      const cands = buildCandidates(m, regimes, state, t, detached, false);
      const f = findEarliest(mo, cands, t, tEnd);
      const tc = f ? f.t : tEnd;
      if (tc - t > 1e-12 && !accelerationIsConstant(m, regimes, mo, t, tc, instant.acc))
        return null;
      return { motion: mo, found: f };
    };
    const analytic = useRk4 ? null : tryAnalytic();
    if (analytic) {
      motion = analytic.motion;
      found = analytic.found;
    } else {
      motion = rk4Motion(m, regimes, t, state);
      found = findEarliest(motion, buildCandidates(m, regimes, state, t, detached, true), t, tEnd);
    }

    const t1 = found ? found.t : tEnd;
    segments.push({ t0: t, t1, regimes, motion });
    state = cloneState(motion.stateAt(t1));
    t = t1;
    if (t >= duration - 1e-12) break;

    if (found) {
      const c = found.candidate;
      const ci = c.contact;
      const body = ci !== undefined ? get(m.ids, get(m.contacts, ci).body) : undefined;
      switch (c.kind) {
        case "stop": {
          const con = get(m.contacts, ci ?? 0);
          const vt = tangentialVelocity(m, con, state);
          state.v[con.body] = sub(get(state.v, con.body), vt);
          note({ t, kind: "stop", body, description: `${body} comes to rest on the surface` });
          break;
        }
        case "edge":
          detached[ci ?? 0] = true;
          note({ t, kind: "edge", body, description: `${body} reaches the edge of the surface` });
          break;
        case "land": {
          const con = get(m.contacts, ci ?? 0);
          const n = get(m.planes, con.plane).n;
          const v = get(state.v, con.body);
          state.v[con.body] = sub(v, scale(n, Math.min(0, dot(v, n))));
          note({ t, kind: "land", body, description: `${body} lands on the surface` });
          break;
        }
        case "lift":
          note({ t, kind: "lift", body, description: `${body} leaves the surface` });
          break;
        case "meet": {
          const [a, b] = c.pair ?? [0, 0];
          const ida = get(m.ids, a);
          const idb = get(m.ids, b);
          note({ t, kind: "meet", body: ida, other: idb, description: `${ida} meets ${idb}` });
          break;
        }
        case "slide_start":
          note({ t, kind: "slide_start", body, description: `${body} starts to slide` });
          break;
        case "slack":
        case "taut": {
          const st = get(m.strings, c.string ?? 0);
          note({
            t,
            kind: c.kind,
            connection: st.id,
            description:
              c.kind === "slack" ? `string ${st.id} goes slack` : `string ${st.id} becomes taut`,
          });
          break;
        }
        default:
          break;
      }
    } else {
      // Reached a scheduled change in forces or constraints.
      for (const e of scene.events) {
        if (Math.abs(e.at - t) < 1e-12) {
          const target = e.target;
          note({
            t,
            kind: e.kind,
            ref: e.id,
            ...(e.kind === "release"
              ? { body: target }
              : e.kind === "cut_string"
                ? { connection: target }
                : {}),
            description: `${e.kind.replace("_", " ")} ${target}`,
          });
        }
      }
      for (const f of scene.forces) {
        if (f.kind === "applied" && f.during) {
          if (Math.abs(f.during[0] - t) < 1e-12)
            note({
              t,
              kind: "force_on",
              ref: f.id,
              body: f.body,
              description: `force ${f.id} switches on`,
            });
          if (f.during[1] !== null && Math.abs(f.during[1] - t) < 1e-12)
            note({
              t,
              kind: "force_off",
              ref: f.id,
              body: f.body,
              description: `force ${f.id} switches off`,
            });
        }
      }
    }
    const before = regimes;
    ({ regimes, instant } = prepare(t));
    m.strings.forEach((st, j) => {
      if (get(before.strings, j) === "taut" && get(regimes.strings, j) === "slack") {
        if (
          !events.some(
            (e) => e.kind === "slack" && e.connection === st.id && Math.abs(e.t - t) < 1e-9,
          )
        ) {
          note({ t, kind: "slack", connection: st.id, description: `string ${st.id} goes slack` });
        }
      }
    });
    m.contacts.forEach((c, ci) => {
      if (get(before.contacts, ci) !== "static" || get(regimes.contacts, ci) !== "sliding") return;
      const body = get(m.ids, c.body);
      if (
        !events.some((e) => e.kind === "slide_start" && e.body === body && Math.abs(e.t - t) < 1e-9)
      ) {
        note({ t, kind: "slide_start", body, description: `${body} starts to slide` });
      }
    });
  }

  const last = segments[segments.length - 1];
  const end = last ? last.t1 : 0;

  const at = (query: number): Snapshot => {
    const tq = Math.min(Math.max(query, 0), end);
    let lo = 0;
    let hi = segments.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (get(segments, mid).t0 <= tq) lo = mid;
      else hi = mid - 1;
    }
    const seg = get(segments, lo);
    const s = seg.motion.stateAt(Math.min(tq, seg.t1));
    const inst = solveInstant(m, seg.regimes, s, tq, true);
    const bodies: Snapshot["bodies"] = {};
    m.ids.forEach((id, i) => {
      const b = get(scene.bodies, i);
      bodies[id] = {
        position: get(s.x, i),
        velocity: isPinned(m, i, tq) ? [0, 0, 0] : get(s.v, i),
        acceleration: get(inst.acc, i),
        orientation: (b.orientation ?? [0, 0, 0, 1]) as Quat,
        angularVelocity: (b.angularVelocity ?? [0, 0, 0]) as Vec3,
      };
    });
    return {
      t: tq,
      bodies,
      forces: inst.forces,
      contacts: m.contacts.map((c, ci) => ({
        body: get(m.ids, c.body),
        surface: get(m.planes, c.plane).id,
        mode: get(seg.regimes.contacts, ci),
      })),
      strings: m.strings.map((st, j) => ({
        id: st.id,
        mode: tq >= st.cutAt ? "cut" : get(seg.regimes.strings, j),
      })),
    };
  };

  const stateAt = (query: number): State => {
    const tq = Math.min(Math.max(query, 0), end);
    let lo = 0;
    let hi = segments.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (get(segments, mid).t0 <= tq) lo = mid;
      else hi = mid - 1;
    }
    const seg = get(segments, lo);
    return seg.motion.stateAt(Math.min(tq, seg.t1));
  };

  return { duration: end, segments, events, model: m, at, stateAt };
}

import { add, len, scale, sub } from "../math/vec3";
import type { Vec3 } from "../math/vec3";
import type { Query } from "../schema";
import { solveInstant } from "./instant";
import type { Timeline } from "./simulate";
import type { Regimes } from "./types";

export interface Answer {
  id: string;
  ask: string;
  /** Scalar, or a world-frame vector. Undefined when the query could not be answered. */
  value?: number | Vec3;
  unit: string;
  error?: string;
}

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

const UNITS: Record<string, string> = {
  acceleration: "m/s^2",
  velocity: "m/s",
  position: "m",
  relative_velocity: "m/s",
  distance: "m",
  work: "J",
  max_height: "m",
  range: "m",
  min_mu_s: "",
  time: "s",
};

function resolveTime(
  tl: Timeline,
  at: number | { event: string } | undefined,
  bodyId?: string,
): number | null {
  if (at === undefined) return 0;
  if (typeof at === "number") return at;
  const ref = at.event;
  const user = tl.model.scene.events.find((e) => e.id === ref);
  if (user) return user.at;
  const ev = tl.events.find(
    (e) => e.kind === ref && (bodyId === undefined || e.body === undefined || e.body === bodyId),
  );
  if (!ev) return null;
  // A query "at the landing" means the instant before the impact, not the body at rest after it.
  return ev.kind === "land" ? ev.t - 1e-9 : ev.t;
}

export function evaluateQuery(tl: Timeline, q: Query): Answer {
  const m = tl.model;
  const unit = q.ask === "force" ? "N" : (UNITS[q.ask] ?? "");
  const fail = (error: string): Answer => ({ id: q.id, ask: q.ask, unit, error });
  const bodyIdx = "body" in q && q.body ? m.index.get(q.body) : undefined;

  if (q.ask === "time") {
    const kind = q.until.event;
    const ev = tl.events.find(
      (e) => e.kind === kind && (q.body === undefined || e.body === undefined || e.body === q.body),
    );
    return ev
      ? { id: q.id, ask: q.ask, value: ev.t, unit }
      : fail(`"${kind}" never happens within ${tl.duration} s`);
  }

  if (q.ask === "force") {
    const t = resolveTime(tl, q.at, q.body);
    if (t === null) return fail("event never happens");
    const snap = tl.at(t);
    const recs = snap.forces.filter((f) => (q.body ? f.body === q.body : true));
    if (q.force === "net") {
      const net = recs.reduce<Vec3>((acc, f) => add(acc, f.vector), [0, 0, 0]);
      return { id: q.id, ask: q.ask, value: net, unit };
    }
    if (q.force === "tension") {
      const mine = snap.forces.filter(
        (f) => f.kind === "tension" && f.id.startsWith(`${q.connection}:`),
      );
      const mag = mine.length ? len(get(mine, 0).vector) : 0;
      return { id: q.id, ask: q.ask, value: mag, unit };
    }
    const kind = q.force === "normal" ? "normal" : "friction";
    const sum = recs
      .filter((f) => f.kind === kind)
      .reduce<Vec3>((acc, f) => add(acc, f.vector), [0, 0, 0]);
    return { id: q.id, ask: q.ask, value: len(sum), unit };
  }

  if (
    q.ask === "acceleration" ||
    q.ask === "velocity" ||
    q.ask === "position" ||
    q.ask === "relative_velocity"
  ) {
    const t = resolveTime(tl, q.at, q.body);
    if (t === null) return fail("event never happens");
    const snap = tl.at(t);
    const b = snap.bodies[q.body];
    if (!b) return fail(`unknown body ${q.body}`);
    const frame = q.frame ? m.scene.frames.find((f) => f.id === q.frame) : undefined;
    let fPos: Vec3 = [0, 0, 0];
    let fVel: Vec3 = [0, 0, 0];
    let fAcc: Vec3 = [0, 0, 0];
    if (frame) {
      const own = frame.velocity ?? [0, 0, 0];
      if (typeof frame.origin === "string") {
        const ob = snap.bodies[frame.origin];
        if (ob) {
          fPos = ob.position;
          fVel = add(ob.velocity, own);
          fAcc = ob.acceleration;
        }
      } else {
        fPos = add(frame.origin, scale(own, t));
        fVel = own;
      }
    }
    const value =
      q.ask === "acceleration"
        ? sub(b.acceleration, fAcc)
        : q.ask === "position"
          ? sub(b.position, fPos)
          : sub(b.velocity, fVel);
    return { id: q.id, ask: q.ask, value, unit };
  }

  if (q.ask === "max_height" || q.ask === "range") {
    const i = bodyIdx ?? 0;
    const bodyId = q.body;
    const land = tl.events.find(
      (e) => e.kind === "land" && (e.body === undefined || e.body === bodyId),
    );
    const ci = m.contacts.findIndex((c) => c.body === i);
    if (q.ask === "range") {
      if (!land) return fail('the body never lands ("land" never happens within the simulation)');
      const p0 = get(tl.stateAt(0).x, i);
      const p1 = get(tl.stateAt(land.t).x, i);
      return { id: q.id, ask: q.ask, value: Math.hypot(p1[0] - p0[0], p1[2] - p0[2]), unit };
    }
    const end = land ? land.t : tl.duration;
    const n = Math.min(40000, Math.max(1, Math.ceil(end / 0.0005)));
    let top = -Infinity;
    for (let k = 0; k <= n; k++) top = Math.max(top, get(tl.stateAt((end * k) / n).x, i)[1]);
    const p0 = get(tl.stateAt(0).x, i);
    let ref = p0[1];
    if (q.above !== "start") {
      if (ci < 0) return fail("max height above the ground needs a surface contact");
      const pl = get(m.planes, get(m.contacts, ci).plane);
      ref = pl.P[1] + get(m.contacts, ci).support;
    }
    return { id: q.id, ask: q.ask, value: top - ref, unit };
  }

  if (q.ask === "distance" || q.ask === "work") {
    const from = typeof q.from === "number" ? q.from : 0;
    const to = typeof q.to === "number" ? q.to : tl.duration;
    const i = bodyIdx ?? 0;
    if (q.ask === "work") {
      const ke = (t: number) => 0.5 * get(m.mass, i) * len(get(tl.stateAt(t).v, i)) ** 2;
      return { id: q.id, ask: q.ask, value: ke(to) - ke(from), unit };
    }
    const n = Math.min(20000, Math.max(1, Math.ceil((to - from) / 0.001)));
    let total = 0;
    let prev = get(tl.stateAt(from).x, i);
    for (let k = 1; k <= n; k++) {
      const cur = get(tl.stateAt(from + ((to - from) * k) / n).x, i);
      total += len(sub(cur, prev));
      prev = cur;
    }
    return { id: q.id, ask: q.ask, value: total, unit };
  }

  // min_mu_s: smallest static coefficient that keeps the body at rest at t = 0.
  const i = bodyIdx ?? 0;
  const ci = m.contacts.findIndex((c) => c.body === i);
  if (ci < 0) return fail("body has no surface contact");
  const reg: Regimes = {
    contacts: m.contacts.map((_, k) => (k === ci ? "static" : "inactive")),
    slideDir: m.contacts.map(() => null),
    strings: m.strings.map(() => "slack"),
  };
  const inst = solveInstant(m, reg, tl.stateAt(0), 0, false);
  const N = get(inst.N, ci);
  if (!inst.ok || N <= 0) return fail("no normal force while at rest");
  return { id: q.id, ask: q.ask, value: len(get(inst.fs, ci)) / N, unit };
}

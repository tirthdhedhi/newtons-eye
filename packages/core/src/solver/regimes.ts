import { add, dot, len, scale, unit } from "../math/vec3";
import type { Vec3 } from "../math/vec3";
import { solveInstant } from "./instant";
import type { Instant } from "./instant";
import {
  EPS_DIST,
  EPS_F,
  EPS_LEN,
  EPS_V,
  isPinned,
  signedDistance,
  stringGeometry,
  tangentialVelocity,
} from "./model";
import type { Model } from "./model";
import type { Regimes, State } from "./types";

function get<T>(a: readonly T[], i: number): T {
  const v = a[i];
  if (v === undefined) throw new Error(`index ${i} out of range`);
  return v;
}

/**
 * Strings that are exactly taut and being stretched exchange an impulse that
 * removes the relative speed along the string (inelastic snap). Mutates `s`.
 */
export function enforceStrings(m: Model, s: State, t: number, detached: boolean[]): string[] {
  const snapped: string[] = [];
  for (let pass = 0; pass < 4; pass++) {
    let changed = false;
    for (const st of m.strings) {
      if (t >= st.cutAt) continue;
      const geo = stringGeometry(st, s);
      if (geo.gap < -EPS_LEN || geo.rate <= EPS_V) continue;
      const ia = isPinned(m, st.a, t) ? 0 : 1 / get(m.mass, st.a);
      const ib = isPinned(m, st.b, t) ? 0 : 1 / get(m.mass, st.b);
      if (ia + ib === 0) continue;
      const J = geo.rate / (ia + ib);
      if (st.kind === "direct") {
        s.v[st.a] = add(get(s.v, st.a), scale(geo.ua, -J * ia));
        s.v[st.b] = add(get(s.v, st.b), scale(geo.ua, J * ib));
      } else {
        s.v[st.a] = add(get(s.v, st.a), scale(geo.ua, -J * ia));
        s.v[st.b] = add(get(s.v, st.b), scale(geo.ub, -J * ib));
      }
      snapped.push(st.id);
      changed = true;
    }
    if (!changed) break;
  }
  void detached;
  return snapped;
}

/**
 * Pick the regime of every contact and string at state `s`, time `t`.
 * Sticking is tested first; friction that would exceed mu_s * N starts a slide.
 */
export function selectRegimes(
  m: Model,
  s: State,
  t: number,
  detached: boolean[],
): { regimes: Regimes; instant: Instant } {
  const contacts = m.contacts.map((c, ci): Regimes["contacts"][number] => {
    if (get(detached, ci) || isPinned(m, c.body, t)) return "inactive";
    if (signedDistance(m, c, s) > EPS_DIST) return "inactive";
    // Touching but already moving away from the surface (a launch): it leaves, it is not held.
    const away = dot(get(s.v, c.body), get(m.planes, c.plane).n) > EPS_V;
    return away ? "inactive" : "static";
  });
  const slideDir: (Vec3 | null)[] = m.contacts.map(() => null);
  const strings = m.strings.map((st): Regimes["strings"][number] => {
    if (t >= st.cutAt) return "cut";
    const geo = stringGeometry(st, s);
    if (geo.gap < -EPS_LEN) return "slack";
    return geo.rate < -EPS_V ? "slack" : "taut";
  });
  // Contacts already moving along the surface start out sliding.
  m.contacts.forEach((c, ci) => {
    if (get(contacts, ci) === "static" && len(tangentialVelocity(m, c, s)) > EPS_V)
      contacts[ci] = "sliding";
  });

  const lifted = new Set<number>();
  let reg: Regimes = { contacts, slideDir, strings };
  let inst = solveInstant(m, reg, s, t, false);
  for (let iter = 0; iter < 24; iter++) {
    let changed = false;
    m.contacts.forEach((c, ci) => {
      const mode = get(reg.contacts, ci);
      if (mode === "inactive") return;
      const N = get(inst.N, ci);
      if (N < -EPS_F) {
        reg.contacts[ci] = "inactive";
        lifted.add(ci);
        changed = true;
        return;
      }
      if (mode === "static") {
        const f = len(get(inst.fs, ci));
        if (f > c.muS * N + 1e-9) {
          reg.contacts[ci] = "sliding";
          reg.slideDir[ci] = unit(get(inst.fs, ci));
          changed = true;
        }
      } else if (len(tangentialVelocity(m, c, s)) <= EPS_V) {
        // Sliding from rest: friction must oppose the impending motion, so the
        // tangential acceleration has to point against it. Otherwise it sticks.
        const d = get(reg.slideDir, ci);
        const plane = get(m.planes, c.plane);
        const a = get(inst.acc, c.body);
        const at = add(a, scale(plane.n, -dot(a, plane.n)));
        if (d && dot(at, d) > 1e-9) {
          reg.contacts[ci] = "static";
          reg.slideDir[ci] = null;
          changed = true;
        }
      }
    });
    m.strings.forEach((_st, j) => {
      if (get(reg.strings, j) === "taut" && get(inst.T, j) < -EPS_F) {
        reg.strings[j] = "slack";
        changed = true;
      }
    });
    if (!changed) break;
    reg = { contacts: [...reg.contacts], slideDir: [...reg.slideDir], strings: [...reg.strings] };
    inst = solveInstant(m, reg, s, t, false);
  }
  return { regimes: reg, instant: inst };
}

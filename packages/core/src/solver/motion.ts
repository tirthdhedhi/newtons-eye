import { rk4Step } from "../math/rk4";
import { axpy } from "../math/vec3";
import type { Vec3 } from "../math/vec3";
import { solveInstant } from "./instant";
import { isPinned } from "./model";
import type { Model } from "./model";
import type { Motion, Regimes, State } from "./types";

const copyState = (s: State): State => ({
  x: s.x.map((v) => [...v] as Vec3),
  v: s.v.map((v) => [...v] as Vec3),
});

/** Closed-form constant-acceleration motion: x = x0 + v0 t + a t^2 / 2. */
export function analyticMotion(t0: number, start: State, acc: Vec3[]): Motion {
  const s0 = copyState(start);
  return {
    kind: "analytic",
    stateAt(t: number): State {
      const tau = t - t0;
      return {
        x: s0.x.map((x, i) =>
          axpy(axpy(x, s0.v[i] ?? [0, 0, 0], tau), acc[i] ?? [0, 0, 0], 0.5 * tau * tau),
        ),
        v: s0.v.map((v, i) => axpy(v, acc[i] ?? [0, 0, 0], tau)),
      };
    },
  };
}

const RK4_STEP = 1e-3;

/**
 * RK4 motion for segments whose forces change with position or velocity.
 * Steps are stored lazily, so stateAt works for any t inside the segment, in any order.
 */
export function rk4Motion(m: Model, regimes: Regimes, t0: number, start: State): Motion {
  const nb = m.ids.length;
  const pack = (s: State): Float64Array => {
    const y = new Float64Array(6 * nb);
    for (let i = 0; i < nb; i++) {
      for (let k = 0; k < 3; k++) {
        y[3 * i + k] = (s.x[i] ?? [0, 0, 0])[k as 0 | 1 | 2];
        y[3 * nb + 3 * i + k] = (s.v[i] ?? [0, 0, 0])[k as 0 | 1 | 2];
      }
    }
    return y;
  };
  const unpack = (y: Float64Array): State => {
    const x: Vec3[] = [];
    const v: Vec3[] = [];
    for (let i = 0; i < nb; i++) {
      x.push([y[3 * i] ?? 0, y[3 * i + 1] ?? 0, y[3 * i + 2] ?? 0]);
      v.push([y[3 * nb + 3 * i] ?? 0, y[3 * nb + 3 * i + 1] ?? 0, y[3 * nb + 3 * i + 2] ?? 0]);
    }
    return { x, v };
  };
  const deriv = (t: number, y: Float64Array): Float64Array => {
    const s = unpack(y);
    const inst = solveInstant(m, regimes, s, t, false);
    const d = new Float64Array(6 * nb);
    for (let i = 0; i < nb; i++) {
      const pinned = isPinned(m, i, t);
      const a = inst.acc[i] ?? [0, 0, 0];
      const v = s.v[i] ?? [0, 0, 0];
      for (let k = 0; k < 3; k++) {
        d[3 * i + k] = pinned ? 0 : v[k as 0 | 1 | 2];
        d[3 * nb + 3 * i + k] = pinned ? 0 : a[k as 0 | 1 | 2];
      }
    }
    return d;
  };
  const samples: Float64Array[] = [pack(start)];
  const ensure = (n: number) => {
    while (samples.length <= n) {
      const k = samples.length - 1;
      samples.push(rk4Step(deriv, t0 + k * RK4_STEP, samples[k] as Float64Array, RK4_STEP));
    }
  };
  return {
    kind: "rk4",
    stateAt(t: number): State {
      const tau = Math.max(0, t - t0);
      const k = Math.floor(tau / RK4_STEP);
      ensure(k);
      const rem = tau - k * RK4_STEP;
      const base = samples[k] as Float64Array;
      return unpack(rem < 1e-15 ? base : rk4Step(deriv, t0 + k * RK4_STEP, base, rem));
    },
  };
}

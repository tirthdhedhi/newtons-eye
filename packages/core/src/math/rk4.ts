/** One classical Runge-Kutta 4 step of y' = f(t, y). */
export function rk4Step(
  f: (t: number, y: Float64Array) => Float64Array,
  t: number,
  y: Float64Array,
  h: number,
): Float64Array {
  const n = y.length;
  const tmp = new Float64Array(n);
  const k1 = f(t, y);
  for (let i = 0; i < n; i++) tmp[i] = (y[i] ?? 0) + 0.5 * h * (k1[i] ?? 0);
  const k2 = f(t + 0.5 * h, tmp);
  for (let i = 0; i < n; i++) tmp[i] = (y[i] ?? 0) + 0.5 * h * (k2[i] ?? 0);
  const k3 = f(t + 0.5 * h, tmp);
  for (let i = 0; i < n; i++) tmp[i] = (y[i] ?? 0) + h * (k3[i] ?? 0);
  const k4 = f(t + h, tmp);
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    out[i] =
      (y[i] ?? 0) + (h / 6) * ((k1[i] ?? 0) + 2 * (k2[i] ?? 0) + 2 * (k3[i] ?? 0) + (k4[i] ?? 0));
  }
  return out;
}

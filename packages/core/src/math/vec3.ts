export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number];
/** Row-major 3x3 matrix. */
export type Mat3 = [Vec3, Vec3, Vec3];

export const ZERO: Vec3 = [0, 0, 0];

export const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const scale = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s];
export const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
export const len = (a: Vec3): number => Math.sqrt(dot(a, a));
/** Unit vector, or zero for a (near) zero input. */
export const unit = (a: Vec3): Vec3 => {
  const l = len(a);
  return l < 1e-300 ? [0, 0, 0] : scale(a, 1 / l);
};
/** a + b * s */
export const axpy = (a: Vec3, b: Vec3, s: number): Vec3 => [
  a[0] + b[0] * s,
  a[1] + b[1] * s,
  a[2] + b[2] * s,
];

/** Rodrigues rotation of v about a unit axis by angle (radians). */
export function rotateAbout(v: Vec3, axis: Vec3, angle: number): Vec3 {
  const k = unit(axis);
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return add(add(scale(v, c), scale(cross(k, v), s)), scale(k, dot(k, v) * (1 - c)));
}

export function quatToMat(q: Quat): Mat3 {
  const n = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
  const x = q[0] / n;
  const y = q[1] / n;
  const z = q[2] / n;
  const w = q[3] / n;
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
  ];
}

export const matVec = (m: Mat3, v: Vec3): Vec3 => [dot(m[0], v), dot(m[1], v), dot(m[2], v)];
/** Column j of a row-major matrix (the image of basis vector j). */
export const matCol = (m: Mat3, j: 0 | 1 | 2): Vec3 => [m[0][j], m[1][j], m[2][j]];

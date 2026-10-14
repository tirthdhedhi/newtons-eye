import type { ForceKind, ForceRecord } from "@newtons-eye/core";

export interface FbdArrow {
  id: string;
  kind: ForceKind;
  label: string;
  /** Full 3D magnitude in newtons. */
  magnitude: number;
  /** Arrow tip relative to the body center, in SVG pixels (y grows downward). */
  dx: number;
  dy: number;
}

export const KIND_LABEL: Record<ForceKind, string> = {
  gravity: "Weight",
  normal: "Normal",
  friction: "Friction",
  tension: "Tension",
  applied: "Applied",
  spring: "Spring",
};

export const fmt = (n: number, digits = 4): string => {
  if (!Number.isFinite(n)) return "-";
  if (Math.abs(n) < 5 * 10 ** -(digits + 2)) return "0";
  return Number(n.toPrecision(digits)).toString();
};

/**
 * Free body diagram arrows for one body. Arrow lengths are proportional to the
 * force magnitude; the largest force is drawn `maxLength` pixels long.
 * Forces are projected onto the x-y plane (x right, y up).
 */
export function fbdArrows(forces: ForceRecord[], bodyId: string, maxLength: number): FbdArrow[] {
  const mine = forces.filter((f) => f.body === bodyId);
  const mags = mine.map((f) => Math.hypot(f.vector[0], f.vector[1], f.vector[2]));
  const biggest = Math.max(0, ...mags);
  if (biggest < 1e-9) return [];
  const k = maxLength / biggest;
  const out: FbdArrow[] = [];
  mine.forEach((f, i) => {
    const magnitude = mags[i] ?? 0;
    if (magnitude < 1e-9) return;
    const detail = f.detail ? ` (${f.detail})` : "";
    out.push({
      id: f.id,
      kind: f.kind,
      label: `${KIND_LABEL[f.kind]}${detail} ${fmt(magnitude)} N`,
      magnitude,
      dx: f.vector[0] * k,
      dy: -f.vector[1] * k,
    });
  });
  return out;
}

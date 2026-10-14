export type Dimension =
  | "length"
  | "mass"
  | "angle"
  | "time"
  | "speed"
  | "acceleration"
  | "force"
  | "stiffness"
  | "dimensionless";

type UnitTable = Record<string, number>;

/** Factor to multiply by to get the SI value (rad, m, kg, s, m/s, m/s^2, N, N/m). */
const UNITS: Record<Dimension, UnitTable> = {
  length: { m: 1, km: 1000, cm: 0.01, mm: 0.001, in: 0.0254, ft: 0.3048 },
  mass: { kg: 1, g: 0.001, lb: 0.45359237 },
  angle: { rad: 1, deg: Math.PI / 180, "°": Math.PI / 180 },
  time: { s: 1, ms: 0.001, min: 60 },
  speed: { "m/s": 1, "km/h": 1 / 3.6, mph: 0.44704 },
  acceleration: { "m/s^2": 1, "m/s²": 1 },
  force: { N: 1, kN: 1000 },
  stiffness: { "N/m": 1, "N/cm": 100 },
  dimensionless: {},
};

const NUMBER_THEN_UNIT = /^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*?)\s*$/;

export type UnitResult = { ok: true; value: number } | { ok: false; message: string };

/**
 * Convert a number (already SI) or a string like "30 deg" / "5 kg" to SI.
 * A string with no unit is taken as SI.
 */
export function toSI(input: number | string, dimension: Dimension): UnitResult {
  if (typeof input === "number") {
    return Number.isFinite(input)
      ? { ok: true, value: input }
      : { ok: false, message: "number must be finite" };
  }
  const match = NUMBER_THEN_UNIT.exec(input);
  if (!match) return { ok: false, message: `cannot read a number from "${input}"` };
  const value = Number(match[1]);
  const unit = match[2] ?? "";
  if (unit === "") return { ok: true, value };
  const factor = UNITS[dimension][unit];
  if (factor === undefined) {
    const known = Object.keys(UNITS[dimension]).join(", ") || "none (dimensionless)";
    return { ok: false, message: `unit "${unit}" is not valid for ${dimension} (use: ${known})` };
  }
  return { ok: true, value: value * factor };
}

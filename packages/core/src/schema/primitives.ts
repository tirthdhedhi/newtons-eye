import { z } from "zod";
import { toSI } from "../units";
import type { Dimension } from "../units";

export const Id = z.string().min(1);

/** A number in SI, or a string with a unit ("30 deg"). Output is always SI. */
export const qty = (dimension: Dimension) =>
  z.union([z.number(), z.string()]).transform((input, ctx) => {
    const r = toSI(input, dimension);
    if (!r.ok) {
      ctx.issues.push({ code: "custom", message: r.message, input });
      return z.NEVER;
    }
    return r.value;
  });

export const vec3 = (dimension: Dimension) => {
  const q = qty(dimension);
  return z.tuple([q, q, q]);
};

export const Vec3 = vec3("dimensionless");

/** Quaternion [x, y, z, w]. */
export const Quat = z.tuple([z.number(), z.number(), z.number(), z.number()]);

export const Friction = z.strictObject({
  static: z.number().min(0),
  kinetic: z.number().min(0),
});

export type Id = z.output<typeof Id>;
export type Friction = z.output<typeof Friction>;

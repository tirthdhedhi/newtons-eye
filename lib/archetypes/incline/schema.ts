import { z } from "zod";
import { QuantitySchema } from "@/lib/schemas/common";

/**
 * Input for a block on an incline with friction.
 *
 * TODO(incline): finalize with the parser + solver owners, then document in docs/SCHEMA.md.
 * TODO(incline): decide how to represent applied forces (push/pull at an angle).
 * TODO(incline): decide direction conventions (up-slope positive?).
 */
export const inclineInputSchema = z.object({
  archetype: z.literal("incline"),
  mass: QuantitySchema.optional(),
  angle: QuantitySchema.optional(),
  muStatic: QuantitySchema.optional(),
  muKinetic: QuantitySchema.optional(),
  initialVelocity: QuantitySchema.optional(),
  gravity: QuantitySchema.optional(),
});
export type InclineInput = z.infer<typeof inclineInputSchema>;

/**
 * Shared contracts between the parser, the solver, and the renderer.
 *
 * Rule of the codebase: the LLM parser only *extracts* quantities from text.
 * Every number in a SolveResult is produced by a deterministic solver.
 * See docs/SCHEMA.md for the full contract.
 */
import { z } from "zod";

/** Every archetype id the app knows about. Add new ids here and in lib/archetypes/registry.ts. */
export const ARCHETYPE_IDS = ["incline"] as const;
export const ArchetypeIdSchema = z.enum(ARCHETYPE_IDS);
export type ArchetypeId = z.infer<typeof ArchetypeIdSchema>;

/** Character offsets into the original problem text, [start, end). */
export const SourceSpanSchema = z
  .object({
    start: z.number().int().nonnegative(),
    end: z.number().int().nonnegative(),
    text: z.string(),
  })
  .refine((span) => span.end >= span.start, { message: "span end must be >= start" });
export type SourceSpan = z.infer<typeof SourceSpanSchema>;

/**
 * A physical quantity normalized to SI, keeping what the student actually wrote.
 * `value`/`unit` are SI (e.g. 0.5 rad, 9.81 m/s^2). `original` is as written
 * (e.g. 30 "deg"). `source` points back into the problem text; it is null for
 * derived or assumed quantities (e.g. g = 9.81 m/s^2 when not stated).
 */
export const QuantitySchema = z.object({
  value: z.number().finite(),
  unit: z.string(),
  original: z
    .object({
      value: z.number().finite(),
      unit: z.string(),
    })
    .nullable(),
  source: SourceSpanSchema.nullable(),
  provenance: z.enum(["given", "assumed", "derived"]),
});
export type Quantity = z.infer<typeof QuantitySchema>;

/**
 * Which physical regime the solver decided applies (e.g. "static" vs "kinetic"
 * for an incline). Ids are archetype-specific; `reason` is shown to students.
 */
export const RegimeSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  reason: z.string(),
});
export type Regime = z.infer<typeof RegimeSchema>;

/** One solution step. The renderer syncs the diagram to `highlight` primitive ids. */
export const StepSchema = z.object({
  id: z.string().min(1),
  title: z.string(),
  explanation: z.string(),
  /** Optional KaTeX source for the equation shown in this step. */
  latex: z.string().optional(),
  /** Named quantity produced by this step, if any. */
  result: z.object({ name: z.string(), quantity: QuantitySchema }).optional(),
  /** Scene primitive ids to emphasize while this step is active. */
  highlight: z.array(z.string()),
});
export type Step = z.infer<typeof StepSchema>;

/** Output of the LLM parser. `input` is validated again by the archetype's own schema. */
export const ParseResultSchema = z.discriminatedUnion("status", [
  z.object({
    status: z.literal("ok"),
    archetype: ArchetypeIdSchema,
    input: z.unknown(),
    /** What the problem asks for, as keys the archetype solver understands. */
    unknowns: z.array(z.string()).min(1),
  }),
  z.object({
    status: z.literal("ambiguous"),
    archetype: ArchetypeIdSchema.nullable(),
    questions: z.array(z.string()).min(1),
  }),
  z.object({
    status: z.literal("unsupported"),
    reason: z.string(),
  }),
  z.object({
    status: z.literal("error"),
    message: z.string(),
  }),
]);
export type ParseResult = z.infer<typeof ParseResultSchema>;

/** Output of a deterministic archetype solver. */
export const SolveResultSchema = z.discriminatedUnion("status", [
  z.object({
    status: z.literal("ok"),
    archetype: ArchetypeIdSchema,
    regime: RegimeSchema,
    answers: z.record(z.string(), QuantitySchema),
    steps: z.array(StepSchema).min(1),
  }),
  z.object({
    status: z.literal("no_solution"),
    archetype: ArchetypeIdSchema,
    reason: z.string(),
  }),
  z.object({
    status: z.literal("error"),
    message: z.string(),
  }),
]);
export type SolveResult = z.infer<typeof SolveResultSchema>;
export type SolveResultOk = Extract<SolveResult, { status: "ok" }>;

/**
 * One entry in an archetype's golden.json: a real problem, the parse we expect,
 * and the verified answers. Used by tests and by `pnpm eval:parser`.
 */
export const GoldenCaseSchema = z.object({
  id: z.string().min(1),
  problemText: z.string().min(1),
  /** Expected parser output `input`; validated by the archetype schema. */
  expectedInput: z.unknown(),
  expected: z.object({
    regime: z.string().min(1),
    answers: z.record(
      z.string(),
      z.object({
        value: z.number().finite(),
        unit: z.string(),
        /** Relative tolerance, e.g. 0.01 for 1%. */
        relTol: z.number().positive(),
      }),
    ),
  }),
  source: z.string().optional(),
});
export type GoldenCase = z.infer<typeof GoldenCaseSchema>;

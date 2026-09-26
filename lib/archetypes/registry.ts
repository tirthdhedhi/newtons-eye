import type { ComponentType } from "react";
import type { z } from "zod";
import type { ArchetypeId, GoldenCase, SolveResult, SolveResultOk } from "@/lib/schemas/common";
import inclineGolden from "./incline/golden.json";
import { inclineInputSchema, type InclineInput } from "./incline/schema";
import { solve as solveIncline } from "./incline/solver";
import InclineTemplate from "./incline/template";

/** Props every archetype template receives from the page. */
export interface ArchetypeTemplateProps<TInput> {
  input: TInput;
  solution: SolveResultOk;
  activeStep: number;
}

/** The contract every archetype module must satisfy. */
export interface ArchetypeModule<TInput> {
  id: ArchetypeId;
  /** Validates the parser's `input` for this archetype. */
  schema: z.ZodType<TInput>;
  /** Pure, deterministic solver. */
  solve: (input: TInput) => SolveResult;
  /** Renders the step-synced diagram. */
  Template: ComponentType<ArchetypeTemplateProps<TInput>>;
  /** Verified problems used for regression tests and parser evals. */
  golden: readonly GoldenCase[];
}

/** Maps each archetype id to its input type. Adding an id to ARCHETYPE_IDS forces an entry here. */
interface ArchetypeInputs {
  incline: InclineInput;
}

type Registry = { [K in ArchetypeId]: ArchetypeModule<ArchetypeInputs[K]> };

export const archetypes: Registry = {
  incline: {
    id: "incline",
    schema: inclineInputSchema,
    solve: solveIncline,
    Template: InclineTemplate,
    golden: inclineGolden,
  },
};

export function getArchetype<K extends ArchetypeId>(id: K): Registry[K] {
  return archetypes[id];
}

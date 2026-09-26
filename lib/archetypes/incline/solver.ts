import type { SolveResult } from "@/lib/schemas/common";
import type { InclineInput } from "./schema";

/**
 * Deterministic solver for a block on an incline with friction.
 * Must be pure: same input, same output, no network, no LLM.
 */
export function solve(_input: InclineInput): SolveResult {
  throw new Error("incline solve: not implemented");
}

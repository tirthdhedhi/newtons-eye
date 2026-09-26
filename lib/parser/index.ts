import type { ParseResult } from "@/lib/schemas/common";

/**
 * Convert raw problem text into a structured ParseResult using the LLM.
 * Must be called server-side only (it will need lib/env.ts for the API key).
 */
export async function parseProblem(_text: string): Promise<ParseResult> {
  throw new Error("parseProblem: not implemented");
}

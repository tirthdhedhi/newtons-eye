import "server-only";
import { z } from "zod";

const serverEnvSchema = z.object({
  ANTHROPIC_API_KEY: z.string().min(1, "ANTHROPIC_API_KEY is required (see .env.example)"),
  ANTHROPIC_MODEL: z.string().min(1, "ANTHROPIC_MODEL is required (see .env.example)"),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;

let cached: ServerEnv | undefined;

/**
 * Validated server environment. Throws a readable error listing every missing
 * or invalid variable. Importing this file from a client component fails the build.
 */
export function getServerEnv(): ServerEnv {
  if (cached) return cached;
  const result = serverEnvSchema.safeParse(process.env);
  if (!result.success) {
    const issues = result.error.issues
      .map((issue) => `  - ${issue.path.join(".")}: ${issue.message}`)
      .join("\n");
    throw new Error(`Invalid server environment:\n${issues}`);
  }
  cached = result.data;
  return cached;
}

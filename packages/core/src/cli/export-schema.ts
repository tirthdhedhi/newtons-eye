import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { AUTHORING_VERSION, AuthoringScene } from "../authoring/schema";

/** `pnpm schema:export`: write schema/authoring.schema.json (JSON Schema for the authoring form). */
const root = join(dirname(fileURLToPath(import.meta.url)), "../../../..");
const out = join(root, "schema", "authoring.schema.json");

const schema = {
  ...z.toJSONSchema(AuthoringScene, { io: "input", unrepresentable: "any" }),
  title: "Newton's Eye authoring scene",
  description:
    "Schema v1.1: a physics scene written only with quantities from a word problem. " +
    "parseScene resolves it into the canonical SI scene (version 1).",
  "x-schemaVersion": String(AUTHORING_VERSION),
};

mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, `${JSON.stringify(schema, null, 2)}\n`);
console.log(`wrote ${out}`);

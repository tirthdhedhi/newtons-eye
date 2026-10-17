import { readFileSync } from "node:fs";
import { parseScene } from "../validate";
import { solve } from "../solver";

/** `pnpm solve <file>`: print { queryId: value } for a canonical or authoring scene. */
function main(argv: string[]): number {
  const file = argv[0];
  if (!file) {
    console.error("usage: pnpm solve <scene.json>");
    return 64;
  }

  let json: unknown;
  try {
    json = JSON.parse(readFileSync(file, "utf8"));
  } catch (e) {
    console.error(
      JSON.stringify(
        { issues: [{ path: "", message: `cannot read ${file}: ${String(e)}` }] },
        null,
        2,
      ),
    );
    return 1;
  }

  const parsed = parseScene(json);
  if (!parsed.ok) {
    console.error(JSON.stringify({ issues: parsed.errors }, null, 2));
    return 1;
  }
  for (const w of parsed.warnings) console.error(`warning: ${w.path}: ${w.message}`);

  const { answers } = solve(parsed.scene);
  const values: Record<string, number | number[] | null> = {};
  for (const a of answers) values[a.id] = a.error === undefined ? (a.value ?? null) : null;
  console.log(JSON.stringify(values, null, 2));

  const failed = answers.filter((a) => a.error !== undefined);
  for (const a of failed) console.error(`error: ${a.id}: ${a.error}`);
  return failed.length > 0 ? 2 : 0;
}

process.exitCode = main(process.argv.slice(2));

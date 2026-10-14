import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseScene } from "./validate";
import { solve } from "./solver";

const dir = join(dirname(fileURLToPath(import.meta.url)), "../../../examples");
const readJson = (f: string): unknown => JSON.parse(readFileSync(join(dir, f), "utf8"));

interface Expected {
  tolerance: number;
  answers: Record<string, { value: number | number[]; unit: string }>;
}

describe("examples: the solver reproduces every hand-computed expected answer", () => {
  const files = readdirSync(dir).filter((f) => f.endsWith(".scene.json"));
  it.each(files)("%s", (file) => {
    const parsed = parseScene(readJson(file));
    if (!parsed.ok) throw new Error(JSON.stringify(parsed.errors));
    const expected = readJson(file.replace(".scene.json", ".expected.json")) as Expected;
    const { answers } = solve(parsed.scene);
    for (const ans of answers) {
      const want = expected.answers[ans.id];
      expect(want, `expected answer for ${ans.id}`).toBeDefined();
      expect(ans.error, `${ans.id}: ${ans.error}`).toBeUndefined();
      expect(ans.unit).toBe(want?.unit);
      const got = ans.value;
      const exp = want?.value;
      if (Array.isArray(exp)) {
        expect(Array.isArray(got), `${ans.id} should be a vector`).toBe(true);
        exp.forEach((c, i) =>
          expect(Math.abs((got as number[])[i]! - c), `${ans.id}[${i}]`).toBeLessThan(
            expected.tolerance,
          ),
        );
      } else {
        expect(Math.abs((got as number) - (exp as number)), ans.id).toBeLessThan(
          expected.tolerance,
        );
      }
    }
  });
});

const scenes = import.meta.glob("../../../../examples/*.scene.json", {
  eager: true,
  import: "default",
});
const expecteds = import.meta.glob("../../../../examples/*.expected.json", {
  eager: true,
  import: "default",
});

export interface ExpectedFile {
  tolerance: number;
  answers: Record<string, { value: number | number[]; unit: string; note?: string }>;
}

export interface Example {
  name: string;
  title: string;
  json: unknown;
  expected?: ExpectedFile;
}

const nameOf = (path: string): string =>
  path
    .split("/")
    .pop()
    ?.replace(/\.(scene|expected)\.json$/, "") ?? path;

export const EXAMPLES: Example[] = Object.entries(scenes)
  .map(([path, json]) => {
    const name = nameOf(path);
    const exp = Object.entries(expecteds).find(([p]) => nameOf(p) === name)?.[1] as
      ExpectedFile | undefined;
    const title = (json as { title?: string }).title ?? name;
    return { name, title, json, ...(exp ? { expected: exp } : {}) };
  })
  .sort((a, b) => a.name.localeCompare(b.name));

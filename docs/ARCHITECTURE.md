# Architecture

## Pipeline

```
problem text
    │
    ▼
┌─────────────────┐   POST /api/parse   lib/parser
│  LLM parser     │   text -> ParseResult (Zod-validated JSON)
└─────────────────┘   extracts quantities + source spans, picks an archetype
    │ ParseResult{status:"ok", archetype, input}
    ▼
┌─────────────────┐   POST /api/solve   lib/archetypes/<id>/solver.ts
│  Solver         │   input -> SolveResult (regime, answers, steps)
└─────────────────┘   pure TypeScript, deterministic
    │ SolveResult{status:"ok", steps}
    ▼
┌─────────────────┐   lib/archetypes/<id>/template.tsx + components/engine
│  Renderer       │   builds a Scene + Timeline, syncs the diagram to the active step
└─────────────────┘
```

All three stages talk only through the Zod schemas in `lib/schemas/common.ts`. That is what lets
parser, solver, and renderer work proceed in parallel.

## The rule: the LLM never computes

The LLM's only job is **extraction**: turning prose into a `ParseResult` whose quantities carry
their original value, unit, and source span in the problem text. It must not do arithmetic,
choose a regime, or produce answers.

Every number a student sees in an answer or step comes from a solver in
`lib/archetypes/<id>/solver.ts`. Solvers are pure functions: no network, no LLM, no randomness.
This is why answers can be verified, and it is why `golden.json` exists.

If the parser is unsure, it returns `status: "ambiguous"` with clarifying questions rather
than guessing.

## Units

Quantities are normalized to SI in `Quantity.value` / `Quantity.unit`. `Quantity.original`
keeps what the student wrote so the UI can echo it back. Conversions happen in code (mathjs),
not in the LLM.

## Renderer

`components/engine` is renderer-agnostic. `Scene` holds `Primitive`s in SI coordinates with an
optional `z`, so a 2D SVG renderer and a future 3D renderer can share archetype templates. Each
`Step.highlight` lists primitive ids; the `Timeline` turns steps into per-primitive `Emphasis`.

## Adding an archetype

1. Open a "New archetype proposal" issue with at least three real problems and verified answers.
2. Add the id to `ARCHETYPE_IDS` in `lib/schemas/common.ts`.
3. Create `lib/archetypes/<id>/` with:
   - `schema.ts`: Zod schema for the input (`archetype: z.literal("<id>")` plus quantities)
   - `solver.ts`: `solve(input) => SolveResult`, pure and deterministic
   - `template.tsx`: component taking `ArchetypeTemplateProps<Input>`
   - `golden.json`: verified cases (format in `lib/archetypes/incline/README.md`)
   - `README.md`: scope and conventions
4. Register it in `lib/archetypes/registry.ts` (add to `ArchetypeInputs` and `archetypes`).
   TypeScript fails the build until every id has a complete module.
5. Teach the parser about it in `lib/parser/systemPrompt.ts`.
6. Run `pnpm test`; the golden-data test validates your cases against both schemas.

Archetypes must not import from each other. Shared helpers go in `lib/`.

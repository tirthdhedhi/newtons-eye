# Schema contract

> Placeholder. The source of truth is `lib/schemas/common.ts`; this document explains intent
> and conventions once they are agreed.

## To document

- [ ] `Quantity`: SI normalization, `original`, `source` span offsets (UTF-16 code units?), `provenance`
- [ ] `ParseResult` statuses and when the parser should return `ambiguous` vs `unsupported`
- [ ] `SolveResult` statuses and when a solver returns `no_solution`
- [ ] `Step`: explanation format (plain text vs Markdown), `latex`, `highlight` ids
- [ ] `Regime` ids per archetype
- [ ] Per-archetype input schemas (start with `incline`)
- [ ] Sign and axis conventions shared by solvers and the renderer
- [ ] Versioning: how we change a schema without breaking golden data

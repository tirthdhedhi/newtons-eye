# Contributing

## Branches

Branch off `main` and use a prefix:

- `feat/` for new functionality, e.g. `feat/incline-solver`
- `fix/` for bug fixes, e.g. `fix/angle-unit-conversion`
- `chore/` for tooling, deps, and docs, e.g. `chore/bump-next`

Never push directly to `main` and never force-push shared branches.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org):

```
feat(incline): detect static vs kinetic regime
fix(parser): keep source span for values written with unicode degree sign
chore: bump zod
test(incline): add golden cases from ch. 5
docs: document Step.highlight
```

Keep commits small and focused on one logical change.

## Pull requests

- **All PRs need one approving review and green CI** before merging.
- Fill in the PR template (What, Why, How tested, Screenshots if UI).
- Keep PRs small. Split parser, solver, and renderer work into separate PRs when possible.
- Solver changes must include golden cases with independently verified answers.

## Running checks locally

```bash
pnpm lint          # ESLint, fails on warnings
pnpm typecheck     # tsc --noEmit
pnpm format:check  # Prettier (run `pnpm format` to fix)
pnpm test          # Vitest once
pnpm test:watch    # Vitest in watch mode
```

CI runs lint, typecheck, format:check, and test on every push and pull request.

## Code rules

- No `any`. Use `unknown` and narrow with Zod.
- The LLM never computes answers. Only solvers in `lib/archetypes/*/solver.ts` produce numbers.
- Solvers are pure: no network, no randomness, no LLM calls.
- Never commit secrets. Put them in `.env.local` (gitignored).

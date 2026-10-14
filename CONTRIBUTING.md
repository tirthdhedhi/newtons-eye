# Contributing

## Branches

Branch off `main` and use a prefix:

- `feat/` for new functionality, e.g. `feat/friction-solver`
- `fix/` for bug fixes, e.g. `fix/angle-unit-conversion`
- `chore/` for tooling, deps, and docs, e.g. `chore/bump-vite`

Never push directly to `main` and never force-push shared branches.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org):

```
feat(solver): detect static vs kinetic regime
fix(units): parse values written with the unicode degree sign
chore: bump zod
test(solver): add hand-computed incline cases
docs: document Step.highlight
```

Keep commits small and focused on one logical change.

## Pull requests

- **All PRs need one approving review and green CI** before merging.
- Fill in the PR template (What, Why, How tested, Screenshots if UI).
- Keep PRs small. Split core (schema/solver) and web (viewer/UI) work into separate PRs when possible.
- Solver changes must include Vitest tests against hand-computed answers.

## Running checks locally

```bash
pnpm lint          # ESLint, fails on warnings
pnpm typecheck     # tsc --noEmit
pnpm format:check  # Prettier (run `pnpm format` to fix)
pnpm test          # Vitest once
pnpm test:watch    # Vitest in watch mode
```

CI runs lint, typecheck, format:check, test, and build on every push and pull request.

## Code rules

- No `any`. Use `unknown` and narrow with Zod.
- `packages/core` is pure: no React/Three imports, no network, no randomness.
- Scene JSON holds only givens; the solver computes every derived number.
- Never commit secrets.

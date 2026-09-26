# Newton's Eye

Students paste a real physics homework problem and get a verified answer with an interactive,
step-synced free-body diagram. An LLM turns the problem text into structured data, a
deterministic TypeScript solver computes the answer, and a custom React renderer draws each
step. The LLM never computes answers.

## Tech stack

- [Next.js](https://nextjs.org) 16 (App Router) + React 19 + TypeScript (strict, `noUncheckedIndexedAccess`)
- Tailwind CSS 4
- Zod for every contract between parser, solver, and renderer
- Anthropic SDK (parser only), mathjs (solver), framer-motion + KaTeX (renderer)
- Vitest, ESLint, Prettier, pnpm, GitHub Actions

## Setup

Requires Node 24 (see `.nvmrc`) and pnpm (pinned in `package.json`; `corepack enable` installs it).

```bash
git clone https://github.com/tirthdhedhi/newtons-eye.git
cd newtons-eye
corepack enable
pnpm install
cp .env.example .env.local   # then fill in ANTHROPIC_API_KEY and ANTHROPIC_MODEL
pnpm dev
```

Open http://localhost:3000.

## Scripts

| Script              | What it does                                          |
| ------------------- | ----------------------------------------------------- |
| `pnpm dev`          | Start the dev server                                  |
| `pnpm build`        | Production build                                      |
| `pnpm start`        | Serve the production build                            |
| `pnpm lint`         | ESLint (fails on warnings)                            |
| `pnpm typecheck`    | `tsc --noEmit`                                        |
| `pnpm test`         | Run Vitest once                                       |
| `pnpm test:watch`   | Run Vitest in watch mode                              |
| `pnpm format`       | Format everything with Prettier                       |
| `pnpm format:check` | Check formatting (used in CI)                         |
| `pnpm eval:parser`  | Parser eval against golden data (not yet implemented) |

## Folder overview

```
app/                  Next.js routes: landing page, /api/parse, /api/solve
lib/schemas/          Shared Zod contracts (Quantity, Step, ParseResult, SolveResult)
lib/parser/           LLM parser: problem text -> ParseResult
lib/archetypes/       One self-contained folder per problem type + registry.ts
components/engine/    Renderer-agnostic scene types, timeline, primitives
components/ui/        Shared UI components
tests/                Vitest tests
docs/                 Architecture and schema docs
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pipeline works and how to add an
archetype, and [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## License

[MIT](LICENSE)

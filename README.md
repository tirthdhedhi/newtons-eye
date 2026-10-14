# Newton's Eye

A client-only web app: a physics scene written as JSON is solved by a pure TypeScript solver and shown as an
interactive 3D simulation with a free body diagram, graphs, and a worked answer.

## Layout

- `packages/core`: schema, units, validator, solver (no React/Three)
- `apps/web`: React + three.js viewer (Vite)
- `examples/`: hand-written scene JSONs with expected answers

## Setup

Requires Node 24 (`.nvmrc`) and pnpm (`corepack enable`).

```bash
pnpm install
pnpm dev
```

## Scripts

`pnpm dev`, `pnpm build`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm format`, `pnpm format:check`.

See [CLAUDE.md](CLAUDE.md) for the physics rules and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

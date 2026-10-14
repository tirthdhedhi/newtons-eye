# Newton's Eye

Newton's Eye is a client-side physics simulator. It reads a scene described as JSON, solves it with a pure TypeScript physics engine, and presents the result as an interactive 3D simulation with playback controls, force arrows, a free-body diagram, and worked answers.

## Project structure

- `apps/web` — React, Three.js, and Vite user interface
- `packages/core` — schemas, units, validation, and the physics solver
- `examples` — sample scenes and their expected answers
- `docs` — architecture and scene-schema documentation

## Prerequisites

- [Node.js 24](https://nodejs.org/) (the required version is also recorded in `.nvmrc`)
- [Corepack](https://nodejs.org/api/corepack.html), included with the supported Node version

Check your Node version:

```bash
node --version
```

If you use `nvm`, run `nvm use` from the repository root. Enable Corepack so it can provide the pnpm version pinned in `package.json`:

```bash
corepack enable
```

## Install and run

From the repository root:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Open [http://localhost:5173](http://localhost:5173) in a browser. Vite prints the exact URL in the terminal if it needs to use a different port.

In the app, select one of the included example scenes or edit the JSON directly. Select **Solve** (or press <kbd>Ctrl</kbd>/<kbd>Cmd</kbd>+<kbd>Enter</kbd>) to apply changes, then use the playback controls and timeline to inspect the solution.

Stop the development server with <kbd>Ctrl</kbd>+<kbd>C</kbd>.

## Production build

Create an optimized build in `apps/web/dist`:

```bash
pnpm build
```

Preview that build locally:

```bash
pnpm --filter @newtons-eye/web exec vite preview
```

Vite will print the preview URL in the terminal.

## Quality checks

Run these before opening a pull request:

```bash
pnpm test
pnpm typecheck
pnpm lint
pnpm format:check
pnpm build
```

Use `pnpm test:watch` while developing, or `pnpm format` to apply the repository's formatting rules.

## Troubleshooting

- If `pnpm` is not found, run `corepack enable`, close and reopen the terminal, and try again.
- If the Node version is unsupported, install Node 24 or run `nvm install && nvm use`.
- If port 5173 is busy, use the alternate URL printed by Vite.
- If dependencies are out of sync after switching branches, rerun `pnpm install --frozen-lockfile`.

For implementation details, see [the architecture guide](docs/ARCHITECTURE.md). For the JSON format, see [the scene schema](docs/SCHEMA.md). Contributor workflow and repository rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

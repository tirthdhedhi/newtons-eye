# Physics simulator (web app)

Goal: a web app where a scene described as JSON is solved and shown as an
interactive 3D simulation with a free body diagram, graphs, and a worked answer.
Later, a fine-tuned small LLM will turn word problems into this JSON. That
parser is OUT OF SCOPE for now; the JSON is hand-written.

## Existing repo rule

This repo already exists and was cloned from GitHub. Before changing anything,
inventory it. Then:

- Anything that overlaps with this plan (same folder, same purpose, same
  config such as package.json, tsconfig, vite config, README, CLAUDE.md,
  existing schema or solver or viewer code) is REPLACED by the plan's version.
  Do not merge it, preserve it, or ask about it.
- Files that do not overlap are left untouched.
- If you cannot tell whether something overlaps, ask me one short question.
- Report at the end of each milestone what was replaced, kept, and deleted.

## Stack

TypeScript (strict), pnpm workspaces, Vite, React, three + @react-three/fiber +
@react-three/drei, Zod, Vitest. Client-only: no backend.

## Layout

- packages/core: schema, units, validator, solver. NO React/Three imports. Pure functions.
- apps/web: React UI + Three.js viewer. Imports core.
- examples/: hand-written scene JSONs, each with an expected-answers file.

## Physics rules (do not violate)

- The scene JSON contains ONLY givens. Normal force, tension, friction, and
  the answer are always computed by the solver, never written in the JSON.
- Use analytic closed-form motion for constant-acceleration segments. Use
  RK4 only for segments with non-constant forces. Do not use a physics engine.
- Solve per segment, then find events (stops, edge reached, string slack,
  start of sliding) and start a new segment. Output a Timeline whose
  at(t) returns state and forces for any t (scrubbing backward must work).
- Friction: test sticking first (a = 0, required static friction vs mu_s*N),
  otherwise slide with kinetic friction opposing motion.
- Multi-body connections (strings, pulleys): assemble and solve one linear
  system for accelerations and constraint forces.
- Internal units are SI. Coordinates are right-handed, Y up. Vectors are [x,y,z].
- Bodies are rigid bodies (position, orientation, mass, inertia, angular
  velocity) and forces have an application point, even though v1 only
  uses particles, so rotation can be added later without schema changes.
- Every solver behavior needs a Vitest test against a hand-computed answer.

## Workflow

- Work one milestone at a time. Run tests and typecheck before saying done.
- Small commits with clear messages. Ask before adding dependencies.

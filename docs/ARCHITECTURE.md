# Architecture

Scene JSON (givens only) -> `parseScene` (Zod + semantic validation, everything converted to SI)
-> `solve` -> `Timeline` + answers -> web viewer.

## Solver (`packages/core/src/solver`)

- `model.ts`: SI scene -> indexed model (planes with basis `u` up-slope, `n` normal, `w` axis; contacts; strings).
- `instant.ts`: for one regime assignment at one state, builds **one linear system** (body force balances,
  contact constraints, string constraints) and solves accelerations, normal forces, static friction and tensions.
- `regimes.ts`: chooses regimes. Sticking is tested first (a = 0, required friction vs mu_s N); otherwise the
  contact slides with kinetic friction opposing motion (or opposing the impending motion when starting from rest).
  A string goes slack if its tension would be negative. A contact lifts if its normal force would be negative.
- `motion.ts`: closed-form constant-acceleration motion, or RK4 (h = 1 ms) when forces change with position
  (springs) or when the analytic acceleration is not constant inside the segment.
- `events.ts`: earliest event in a segment: stop, edge, land, lift, slack, taut, slide start. Scheduled changes
  (force windows, release, cut string, set force) are segment breakpoints.
- `simulate.ts`: loop of segments. `Timeline.at(t)` is a pure lookup, so scrubbing backward works.
- `queries.ts`: answers scene queries from the timeline.

Known v1 limits: particles only (orientation is carried, never integrated), one surface contact per body,
ideal massless pulleys, inelastic landing, no body-body collisions. Statically indeterminate setups (two
bodies held by static friction with a taut string between them) split the load with T = 0.

## Web (`apps/web`)

React + react-three-fiber viewer, force arrows scaled to the largest force in the run, a free body diagram
(SVG, x-y projection), an answers table that compares against `examples/*.expected.json`, and a playback
slider. `?example=<name>&t=<seconds>` opens an example at a time.

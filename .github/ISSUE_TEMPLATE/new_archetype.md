---
name: New archetype proposal
about: Propose a new problem type (e.g. projectile, pulley, connected blocks)
title: "feat(archetype): "
labels: archetype
---

## Archetype name

<!-- Short id used in the registry, e.g. `projectile`. -->

## Scope

<!-- Which problems are in scope, and which are explicitly out of scope for v1? -->

## Example problems

<!-- At least 3 real homework problems with verified answers. These become golden.json. -->

1.
2.
3.

## Inputs

<!-- Quantities the parser must extract (with SI units). -->

## Outputs and regimes

<!-- What the solver computes, and any regimes it must detect (e.g. static vs kinetic). -->

## Diagram

<!-- Bodies, surfaces, and vectors to draw. A sketch is welcome. -->

## Checklist (see docs/ARCHITECTURE.md, "Adding an archetype")

- [ ] schema.ts
- [ ] solver.ts (pure, deterministic)
- [ ] template.tsx
- [ ] golden.json with verified answers
- [ ] Registered in lib/archetypes/registry.ts and ARCHETYPE_IDS

# Scene schema (v1)

Source of truth: `packages/core/src/schema`. Scene JSON holds only givens.

- Numbers are SI, or strings with a unit (`"30 deg"`, `"5 kg"`, `"72 km/h"`); parsing converts to SI (`packages/core/src/units`).
- Y up, right-handed, vectors are `[x, y, z]`. Plain angle numbers are radians.
- Top level: `version`, `title`, `duration`, `environment`, `frames`, `bodies`, `surfaces`, `contacts`, `forces`,
  `connections`, `events`, `queries`.
- Planes: `angle` is measured from horizontal about `axis` (default z), so the slope rises along +x. `extent`
  (length along the slope, optional width) makes a finite surface with an edge.
- Contacts bind a body to one plane; friction comes from the surface unless the contact overrides it.
- Forces: `applied` (a vector, or magnitude + `directionAngle` above the surface) with an optional `during`
  window, and `spring` (to a point or another body).
- Connections: `string` and `pulley_string` (ideal pulley; `endA`/`endB` are where the string leaves it).
- Events: `release` (a body is held until then), `cut_string`, `set_force`.
- Queries: acceleration, velocity, position, force (normal, friction, tension, net), time (until stop, edge,
  slack, slide_start), distance, work, min_mu_s, relative_velocity.
- Keys the solver computes (`normal`, `tension`, `acceleration`, `answer`, ...) are rejected anywhere in the JSON.
- `parseScene(json)` returns the SI scene or a list of `{ path, message }` issues, plus warnings.
- `examples/<name>.scene.json` pairs with `<name>.expected.json` (hand-computed values per query id).

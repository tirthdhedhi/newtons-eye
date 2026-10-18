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
  land, slack, slide_start), distance, work, min_mu_s, relative_velocity, max_height, range.
  - `time` `until: { event: "land" }`: when the body's lowest point reaches the plane it is in `contacts` with
    (time of flight). `velocity`/`position`/`acceleration` with `at: { event: "land" }` read the instant _before_
    the impact. Give a projectile `"shape": { "kind": "point" }` so it lands when its centre reaches the plane
    (the default authoring box lands 0.1 m early).
  - `max_height`: highest point before landing (or the end of the simulation). `above: "ground"` (default) is
    the height above the body's contact plane, `above: "start"` the height above the starting position.
  - `range`: horizontal distance from the starting position to the landing point. Errors if the body never lands.
- Keys the solver computes (`normal`, `tension`, `acceleration`, `answer`, ...) are rejected anywhere in the JSON.
- `parseScene(json)` returns the SI scene or a list of `{ path, message }` issues, plus warnings.
- `examples/<name>.scene.json` pairs with `<name>.expected.json` (hand-computed values per query id).

## Authoring layer (schema v1.1)

A scene with `"version": 1.1` may use sugar that `parseScene` resolves into the canonical SI scene above
(`version: 1`). Canonical scenes validate exactly as before. An authoring scene holds only quantities that appear
in a word problem: no coordinates, quaternions, shape sizes, durations, or pulley/anchor positions.
Source: `packages/core/src/authoring`. JSON Schema: `pnpm schema:export` writes `schema/authoring.schema.json`.

- `body.shape` optional, default box `[0.4, 0.2, 0.4]`. `body.position` optional (origin, or resting on its contact surface).
- `body.placement`:
  - `{ on: <planeId>, at: "top" | "bottom" | <distance> }`: rest flush on the plane (`top` is the extent length along the slope).
    Position and orientation are computed. `{ on, offset: <distance> }` is the same for horizontal planes.
  - `{ hangingFrom: <connectionId>, above: <planeId>, gap: <distance> }`: straight below that end of a `pulley_string`.
- `body.velocity` may also be `{ speed, angle }` (above horizontal, toward +x) or `{ speed, along: <planeId>, direction: "up" | "down" }`.
- `pulley_string.pulley.position` may be `{ at: "edge_of", surface: <planeId> }` (far end of the surface's `extent`,
  level with the connected body resting on it). If omitted it is inferred the same way from a connected body's contact.
- `surfaces[].point` optional (origin). `spring.anchor` may be `{ fixed: true, stretch: <distance> }`: the anchor is
  fixed so the spring is at natural length at the body's placement, and the body starts displaced by `stretch`.
- `duration` optional: the latest time any query references (events included) + 1 s, at least 2 s. If a query
  waits for an event (a `time` until, `range`, `max_height`, or a `distance` with no `to`) the default is 60 s,
  so "when does it stop", "how far does it go" and "time of flight" need no window.
- A body that touches a plane while moving away from it (a launch) leaves the plane; it is not held on it.
- Every default or inference is returned in `parseScene(...).warnings`.

`pnpm solve <file>` accepts either form and prints `{ queryId: value }`; on a validation failure it prints the issues
to stderr and exits 1.

### Examples that cannot yet be written without coordinates

`examples/<name>.authoring.json` exist for floor-push, incline-frictionless, incline-sliding, incline-static,
projectile, sliding-stop and spring-block. Two examples are not expressible with the sugar above:

- **atwood**: two masses hang from a pulley with no surface. `hangingFrom` needs an `above` plane, and `edge_of`
  needs a surface, so there is no way to place the pulley or the two masses (and the separate start heights).
- **table-hanging**: the table is 1 m above the floor and its edge is at the pulley. A plane's height (`point`) is a
  coordinate, and `edge_of` needs a finite `extent` positioned by `point`; nothing says "this table is 1 m high"
  or "the cart starts 2 m from the edge". The pieces (`edge_of`, `hangingFrom`) work once the table's `point` is
  given (covered by a unit test), but that is a coordinate.

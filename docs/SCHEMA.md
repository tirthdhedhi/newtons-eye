# Scene schema (v1)

Source of truth: `packages/core/src/schema`. Scene JSON holds only givens.

- Numbers are SI, or strings with a unit (`"30 deg"`, `"5 kg"`, `"72 km/h"`); parsing converts to SI (`packages/core/src/units`).
- Y up, right-handed, vectors are `[x, y, z]`. Plain angle numbers are radians.
- Top level: `version`, `environment`, `frames`, `bodies`, `surfaces`, `contacts`, `forces`, `connections`, `events`, `queries`.
- Keys the solver computes (`normal`, `tension`, `acceleration`, `answer`, ...) are rejected anywhere in the JSON.
- `parseScene(json)` returns the SI scene or a list of `{ path, message }` issues, plus warnings (e.g. kinetic friction above static).
- `examples/<name>.scene.json` pairs with `<name>.expected.json` (hand-computed values per query id).

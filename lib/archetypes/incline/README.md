# Incline archetype

A block on an inclined plane with static and kinetic friction.

| File           | Owner area | Purpose                                                |
| -------------- | ---------- | ------------------------------------------------------ |
| `schema.ts`    | parser     | Zod schema for the structured input                    |
| `solver.ts`    | solver     | Pure, deterministic `solve(input) => SolveResult`      |
| `template.tsx` | renderer   | Turns input + solution into an interactive diagram     |
| `golden.json`  | everyone   | Real problems with verified answers (regression suite) |

## `golden.json` format

JSON has no comments, so the format lives here. The file is an array of
`GoldenCase` objects (see `GoldenCaseSchema` in `lib/schemas/common.ts`):

```json
[
  {
    "id": "incline-001",
    "problemText": "A 5.0 kg block rests on a 30° incline. μs = 0.6, μk = 0.4. Does it slide? What is its acceleration?",
    "expectedInput": { "archetype": "incline", "...": "fields from schema.ts" },
    "expected": {
      "regime": "static",
      "answers": {
        "acceleration": { "value": 0, "unit": "m/s^2", "relTol": 0.01 }
      }
    },
    "source": "Textbook ch. 5, problem 12 (optional)"
  }
]
```

Rules:

- `id` is unique and stable. Never renumber existing cases.
- `expected` answers must be verified by hand or with an independent source, not by our solver.
- `expectedInput` must pass `inclineInputSchema`.

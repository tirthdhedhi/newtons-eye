# Results so far

All numbers are `solver_match` unless noted: the model's scene is solved and its answers equal the
gold scene's answers (matched by query signature, relative tolerance 1e-3). Every row below also
passes `valid_json`, `schema_valid`, `solver_ok` and `grounded` unless a column says otherwise.
Raw per-item outputs live in `results/` (gitignored); rerun commands are in the README.

## Test sets

| set | items | what it is |
| --- | --- | --- |
| seed | 21 scored (27 incl. 6 pending) | hand-written questions, 3 phrasings of 7 examples |
| held-out generated | 300 of 1764 | generated problems whose *parent problem* was never trained on (v2 data) |
| hard | 15 | hand-written with deliberately unfamiliar wording, units (g, cm, km/h) and ask order; 3 are OpenStax University Physics problems quoted verbatim (CC BY 4.0). Every gold scene is checked against a closed form or the book's answer |

The seed and hard sets were written by the same author as the generator templates, so their
wording is not independent of the training distribution. Treat them as sanity checks, and add
questions in your own words (`data/hard.jsonl` format: `id, example, style, question, scene`).

## Models

| model | prompt | seed (21) | held-out generated | hard (15) |
| --- | --- | --- | --- | --- |
| qwen2.5-coder 7B, no tuning | schema + 3 examples | 9 | n/a | n/a |
| qwen2.5-coder 7B, no tuning, constrained decoding | schema + 3 examples | 9 | n/a | n/a |
| qwen3 4B, no tuning, constrained | schema + 3 examples | 7 | n/a | n/a |
| gemma3 4B, no tuning, constrained | schema + 3 examples | 0 | n/a | n/a |
| **v1**: Qwen2.5-Coder-3B LoRA, 3,174 examples (6 families) | short, no schema | 14 | 150 / 150 (generated test v1) | 11 |
| **v2**: Qwen2.5-Coder-3B LoRA, 6,306 examples (8 families, varied wording) | short, no schema | **21** | **300 / 300** | **15** |

v1's seed misses were all wording shifts: velocity given as horizontal and vertical *components*
(3), an "also find the minimum mu_s" ask dropped (3), "time to reach the edge?" dropped (1).
v2 adds ask framings, component-form velocities, mixed units, distractor sentences, and two
families (vertical force on a free body, force along a ramp).

## What the solver cannot be asked yet (found while building data)

* `time` events are only `stop`, `edge`, `slack`, `slide_start`: no "time to hit the ground",
  no "maximum height", no range.
* A `distance` query, and a `time until stop` longer than 2 s, only work if the simulation window
  is long enough, and the window comes from the latest query time. There is no "distance until it stops".
* No inverse problems (find the force or mu from a motion), no problems without a mass, no table
  with a pulley (atwood and table-hanging have no authoring twin).
* About 600 OpenStax Vol. 1 exercises in chapters 2 to 6 were scanned; only a handful (a vertical
  force on a body, a block on a smooth ramp, a force along a ramp) can be expressed.

## Not done / caveats

* The 7B comparison has not been run (Mac MLX 7B gave NaN losses; the free Colab T4 was far too slow).
* Only 15 hard items, all by one author. A larger independently written test would be better evidence.
* Training used synthetic data only; no textbook text.

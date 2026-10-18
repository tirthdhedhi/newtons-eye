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
| paraphrase | 300 | held-out generated problems rewritten by a different model (untuned Ollama qwen2.5-coder 7B) in six styles: exam question, chatty message, lab note, story, formal problem set, forum post. Kept only if the numbers are identical and the asks are present, so the source gold scene applies. This is the only test whose wording was not written by the generator's author |
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
| **v2 3B**: Qwen2.5-Coder-3B LoRA, 6,306 examples (8 families, varied wording) | short, no schema | **21** | **300 / 300** | **15** |
| v2 7B: Qwen2.5-Coder-7B LoRA, same data, float32 | short, no schema | 21 | 150 / 150 | 14 |

Paraphrase set (300 items, `solver_match`; other columns in parentheses):

| model | solver_match | valid_json | schema_valid | solver_ok | grounded |
| --- | --- | --- | --- | --- | --- |
| **v2 3B (chosen)** | **292 / 300 (97.3%)** | 300 | 298 | 296 | 297 |
| v2 7B | 291 / 300 (97.0%) | 300 | 299 | 295 | 298 |

The 3B and 7B are tied within noise on every test, so the 3B is the pick: about 2.5x faster to
train and run, 2 GB at 4-bit, and it needs no float32 workaround. Remaining 3B misses on the
paraphrase set (8): dropped a `velocity` or `time until edge` query (3), spring problems with the
spring fields placed on the surface (3), a `relativeTo` naming a surface that does not exist (1),
and a duplicate query id (1). The spring family is the weakest (37/40).

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

* The 7B was trained on the Mac in float32 after float16 gave NaN losses (see README). The free
  Colab T4 was far too slow, so that route was not used.
* The paraphrases come from one model, so their style is not human. Questions written by a person
  are still the best evidence; add them to `data/hard.jsonl`.
* The hard set is only 15 items, all by one author.
* Training used synthetic data only; no textbook text.

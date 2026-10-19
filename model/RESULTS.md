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


## v3 (wider scope + refusals) and what it showed

v3 adds: time of flight / max height / range / impact velocity, optional mass, constant-acceleration
kinematics, spring release, questions with one friction coefficient, and a refusal path
(`{"unsupported": reason}`) for questions the solver cannot do. Trained on 9,411 examples (12 families,
about 14% refusals), validation loss 0.072.

| test | v3 3B | v2 3B |
| --- | --- | --- |
| seed set (21) | 21 | 21 |
| hard set (15) | 14 (refused one lift problem as "apparent motion") | 15 |
| held-out generated (300, incl. refusals) | 297 | n/a (older families) |
| paraphrases (300, in-scope only) | 287 | 292 |
| **exam-style dev set: 30 questions written by the project owner** | **20** | not measured |

The 30-question set is the hardest test so far: in-scope questions (10) with hand-verified gold scenes,
and 20 that should be refused. v3 refused 16 of 20 correctly but got only 4 of 10 in-scope questions
right. Failures: dropped queries (velocity, time of flight), invented queries (`restoring`, `motion`),
a missing `until`, and a `position` key inside a surface. Unrefused: spring on an incline, speed at the
natural length, minimum stretch to start sliding, banked road. That set is now a *development* set
(the next round of data was written with its style in mind); a fresh batch is needed for a clean test.

Inference experiments on that set, same v3 model:

| setting | solver_match (30) | note |
| --- | --- | --- |
| greedy, MLX | 20 | |
| greedy, Ollama GGUF (Q8_0, exported) | 20 | the export is faithful |
| Ollama with a constrained-decoding grammar, scene or refusal | 20 | 10 in-scope questions wrongly refused |
| Ollama with a scene-only grammar (in-scope 10 only) | 0 / 10 | schema-valid but queries get dropped |
| self-consistency, greedy + 6 samples, keep valid, majority (`--vote 6`) | 22 | the remaining misses are systematic |

So: grammar-constrained decoding is not used (it fights the fine-tuned token habits), and voting gives a
small gain. The fix has to come from training data.

## Export for local running

`mlx_lm.fuse --dequantize` writes a standard HF model, `convert_hf_to_gguf.py` + `llama-quantize` make a
GGUF, and `ollama create` imports it (Ollama 0.40's own safetensors import does not support Qwen2).
The Modelfile bakes in the system prompt, so a client sends only `Problem: <question>\nJSON:`.


## v4 (wording variety + partial refusals): current best

v4 adds to v3: richer ask vocabulary ("normal reaction", "total time to reach the ground", "initial
restoring force", "whether the block moves and its acceleration"), a `partial` family (an in-scope
problem plus one ask the solver cannot compute, such as energy or momentum, which must be refused instead of
half-answered), and about 1,400 LLM paraphrases of training questions (gemma3:4b rewrote them; each kept
only if every number and every asked quantity survived, and 32 that changed the physics were dropped).
13,903 training examples, 3 000 iterations, validation loss 0.08.

| test | v2 | v3 | **v4** |
| --- | --- | --- | --- |
| seed set (21) | 21 | 21 | **21** |
| hard set (15) | 15 | 14 | 14 (one invented mass) |
| paraphrases of held-out problems (300, in-scope only) | 292 | 287 | **295 (98.3%)** |
| held-out generated problems, all 13 families (300) | n/a | 297 | **300** |
| exam-style dev set written by the project owner (30) | n/a | 20 | **25** |

On the 30-question dev set v4 refuses 18 of 20 out-of-scope questions correctly (v3: 16) and gets 7 of 10
in-scope questions right (v3: 4). Remaining misses: a dropped `time until land` query (two questions), a
dropped `velocity` query (one), and two unsupported questions it answered anyway (minimum stretch to start
sliding, a banked road). Every in-scope miss is a **dropped query, never a wrong value**.

Caveats: the 30 questions were used to steer v4's data, so 25/30 is optimistic; a fresh batch is the honest
test. The paraphrase and held-out sets share the generator's problem structure. Sleep interrupted the
overnight scoring on a battery-powered Mac; use `caffeinate` for long runs.

## What to do next

1. Count the asks: train the model to write a one-line "find: ..." summary first, and check the scene
   covers every asked quantity (resample if not). Targets the dropped-query failures.
2. More multi-ask training questions (three or four asks, odd orders).
3. A fresh, never-tuned test set written by someone else.
4. App-side pipeline (validate, solve, explain, retry, intent labels) around the model.
5. Widen the solver: relative motion, pulleys, series/parallel springs, circular motion.


## Correction: scoring bug that understated the owner's-question numbers

Bodies without a mass were matched by id, so a gold `car` and a model `body` counted as different bodies and correct
scenes scored as failures. With the fix (bodies without a mass are matched by position) the same saved outputs score:

| run | first reported | corrected |
| --- | --- | --- |
| v3, greedy | 20 / 30 | **22 / 30** |
| v3 + voting (greedy + 6 samples) | 22 / 30 | **25 / 30** |
| v4, greedy | 25 / 30 | **28 / 30** |
| v5, greedy | 26 / 30 | **29 / 30** |

The items u5, u8 and u10, which I had described as "dropped queries", were complete and right. The seed, hard,
paraphrase and held-out sets were not affected (their bodies carry a mass or share ids with the gold scene).

## v5 (the `find:` line, completeness check, multi-ask data): current best

The model writes `"title": "find: <every quantity asked>"` first and then one query per item; a scene that declares
more than it queries loses the vote. Trained 2,500 more iterations from the v4 weights on 22,492 examples (4,000 new
verified problems with three to five asks in shuffled order, the retitled v4 data, 1,400 paraphrases), validation
loss 0.066.

| test | v2 | v3 | v4 | **v5** |
| --- | --- | --- | --- | --- |
| seed set (21) | 21 | 21 | 21 | **21** |
| hard set (15) | 15 | 14 | 14 | **15** |
| paraphrases of held-out problems (300) | 292 | 287 | 295 | **297 (99.0%)** |
| held-out generated, 13 families (300) | n/a | 297 | 300 | **300** |
| owner's 30 questions (corrected) | n/a | 22 | 28 | **29** |

On the 30 questions v5 gets all 10 in-scope questions right and refuses 19 of 20 out-of-scope ones. The one miss
is u23 ("minimum extension required to start the block moving"): it answers with a scene, in every sample. Refusal
categories for thresholds to start moving or sliding were added afterwards and are not trained yet.

Exported to Ollama as `newtons-eye-3b-v5` (Q8_0, 3.3 GB, system prompt baked in): greedy 29/30, the same as MLX, and
voting (`--vote 6`) also 29/30, so the model is already consistent and voting adds nothing here.

Caveats: the owner's questions steered the data of v4 and v5, so 29/30 is optimistic. A fresh set of questions
written by someone else is the next honest test. The remaining paraphrase-set misses (3 of 300) are one invalid
JSON, one missing edge-time query, and one in-scope question refused; a fourth item has the right answer but
uses a speed that is not stated in the question (flagged by the grounding check only).

# Parser model: development log

What was built, in what order, what went wrong, and how each problem was handled. The numbers are in
[`model/RESULTS.md`](../model/RESULTS.md); how to run things is in [`model/README.md`](../model/README.md).
This file is the story behind them, so the same mistakes are not repeated.

## 1. The goal and the shape of the solution

A fine-tuned **small** language model turns a physics word problem into a JSON scene (the authoring format
in `schema/authoring.schema.json`). The TypeScript solver in `packages/core` does all the physics. The model
never computes anything; it only translates. When a question is beyond what the solver supports, the model
answers `{"unsupported": "<reason>"}`.

Rules that held the whole way through:

- The scene holds only givens (the repo rule). Answers, normal force, tension and the key `acceleration`
  are never written in a scene.
- Every claim about quality is measured by running the **real solver**, not by comparing text.
- Training data is generated or openly licensed. No copyrighted textbook text is used.
- Held-out problems never reach training (split by problem, with leakage checks).

## 2. Timeline

| phase                    | what was done                                                                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1. Harness               | Python package `parser_model`: prompts, an OpenAI-compatible client, a wrapper around `pnpm solve`, grounding check, metrics, `evaluate` CLI, 27-question seed set |
| 2. Baselines             | Untuned qwen2.5-coder 7B, qwen3 4B, gemma3 4B with the schema and three examples in the prompt                                                                     |
| 3. Data                  | Template generator with closed-form answers verified against the solver; OpenStax extractor; train/val/test splits                                                 |
| 4. Fine-tuning v1 and v2 | LoRA on Qwen2.5-Coder-3B with MLX; v2 added wording variety                                                                                                        |
| 5. The 7B model          | NaN losses, then a float32 fix; tied the 3B, so the 3B was chosen                                                                                                  |
| 6. Independent tests     | A hard set and an LLM-paraphrased set, because the first tests were too close to the training wording                                                              |
| 7. Solver extension      | Time of flight, max height, range, optional mass, constant acceleration, a launch bug fix                                                                          |
| 8. v3 and v4             | New families, refusals, partial refusals, 1,400 LLM-paraphrased training questions, export to Ollama                                                               |
| 9. Next                  | The dropped-query fix (section 8)                                                                                                                                  |

## 3. Results at a glance (`solver_match`)

| model                                             | seed (21) | hard (15) | paraphrases (300) | held-out generated | owner's 30 questions |
| ------------------------------------------------- | --------- | --------- | ----------------- | ------------------ | -------------------- |
| untuned 7B, best baseline                         | 9         | n/a       | n/a               | n/a                | n/a                  |
| v1 (3B, 6 families)                               | 14        | 11        | n/a               | 150/150            | n/a                  |
| v2 (3B, 8 families, varied wording)               | 21        | 15        | 292               | 300/300            | n/a                  |
| v2 7B                                             | 21        | 14        | 291               | 150/150            | n/a                  |
| v3 (3B, wider scope, refusals)                    | 21        | 14        | 287               | 297/300            | 22/30                |
| v4 (3B, more wording, partial refusals)           | 21        | 14        | 295               | 300/300            | 28/30                |
| **v5 (v4 + the `find:` line and multi-ask data)** | **21**    | **15**    | **297**           | **300/300**        | **29/30**            |

The "owner's 30 questions" column uses the corrected scoring (section 4, "answer matching"): the
numbers first reported were 20, 25 and 26 for v3, v4 and v5.

Choice: the **3B** model. It ties the 7B on everything, trains and runs about 2.5 times faster, needs no
float32 workaround, and exports to a 3 GB file. Caveat: the owner's 30 questions steered the data of
v4 and v5, so 29/30 is optimistic; a fresh set is needed for a clean number.

## 4. Problems and fixes, in the order they happened

### Environment and tooling

| problem                                    | cause                                            | fix                                                                                                                        |
| ------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `pnpm solve` crashed                       | default Node was 20; pnpm 11 needs 22 or later   | the solver wrapper puts the Node from `.nvmrc` (24, found under `~/.nvm`) first on `PATH`; `NEWTONS_NODE_BIN` overrides it |
| system Python was 3.9                      | macOS default                                    | a venv from Homebrew's Python 3.12                                                                                         |
| `AGENTS.md` missing                        | the prompt named a file the repo does not have   | followed `CLAUDE.md`                                                                                                       |
| the home folder was a git repo             | an empty stray `~/.git`                          | removed (it had no commits, no remote)                                                                                     |
| eslint and prettier failed on Python files | they scanned `model/.venv` and generated results | `model/**` added to the eslint ignores and `model` to `.prettierignore`                                                    |
| long jobs stalled overnight                | the laptop went to sleep on battery              | `caffeinate -dimsu`, plug in the charger, keep the lid open; jobs resume after sleep, nothing is lost                      |

### Baselines and the harness

| problem                                          | cause                                                                                                                             | fix                                                                                                                                                                                           |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| first baseline scores were meaningless           | the prompt (schema plus examples) is about 6.5k tokens; Ollama's default context is 4096, so it was silently truncated            | `num_ctx` 16384 model variants; the harness now reads `num_ctx` from Ollama and warns when the prompt cannot fit                                                                              |
| "constrained" run was identical to the plain run | Ollama rejects `items: false` in tuple arrays; the fallback chain then reached `guided_json`, which Ollama accepts and ignores    | `simplify_schema` rewrites tuple arrays for the grammar; a schema-conversion error now stops with a clear message instead of falling back                                                     |
| MLX server returned 404 for every request        | it treats the request's `model` as a Hugging Face repo name                                                                       | send `default_model`                                                                                                                                                                          |
| two of the nine examples could not be scored     | `atwood` and `table-hanging` have only canonical scenes (no authoring version: the sugar cannot place a pulley or a table height) | marked `pending` in the seed set and left out of the scores; a self-test feeds each gold authoring scene through every metric and all seven pass                                              |
| grounding flagged correct scenes                 | "20-degree" and LaTeX like `20^\circ` were not parsed as quantities                                                               | the question is cleaned of LaTeX and hyphenated units are accepted (11 false alarms out of 300 removed)                                                                                       |
| derived values failed grounding                  | a projectile written as "14.1 m/s at 45 degrees" from components 10 and 10                                                        | `hypot` and `atan2` of same-unit pairs are allowed; `90 degrees` ("straight up") and `g = 9.81` are documented defaults                                                                       |
| answers matched by query id, which is arbitrary  | models name queries differently                                                                                                   | answers are matched by a signature: ask, body, force, connection, `until`, `at`, `from`, `to`, `above`; bodies are named by mass, connections by the masses they join; a missing `at` means 0 |
| wrong paraphrases passed number checks           | `m/s^2` added a spurious "2"                                                                                                      | unit exponents are removed before numbers are compared                                                                                                                                        |

### The textbook data

| problem                                   | cause                                                                                                                               | fix                                                                                                                               |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| the uploaded Halliday and HC Verma PDFs   | the files came from OceanofPDF, a site of unauthorized copies; a "combined" PDF built from them later had the same origin           | not used, and the folder is gitignored; OpenStax University Physics (free, CC BY) was used instead, parsed from its CNXML sources |
| OpenStax yielded little                   | of about 600 exercises in chapters 2 to 6, most ask inverse questions, give no mass, need graphs, or need geometry the schema lacks | only a handful are expressible; three are used verbatim in the hard set, checked against the book's answers                       |
| solver gaps found while writing templates | `time` events were only stop, edge, slack, slide start; a `distance` query covered only the default 2 s window; mass was mandatory  | the solver was extended (section 5)                                                                                               |

### Training the 7B model

| problem                                                           | cause                                                                                                                                   | fix                                                                                                                                                |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| loss went to NaN after about 20 iterations at every learning rate | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` stores scales, biases and norms in float16, and Qwen2.5-7B overflows float16 activations | float32 activations (`train_mlx.py`, `generate_mlx.py`); bfloat16 trained unstably, a lower learning rate and gradient clipping did not help alone |
| generation ran out of memory                                      | training held most of the GPU memory                                                                                                    | do not run generation during training                                                                                                              |
| the stock MLX server would overflow too                           | it loads float16                                                                                                                        | generate with `generate_mlx.py` and score the outputs offline (`--outputs`)                                                                        |
| Colab free T4 showed a 15 hour estimate                           | 85 tokens per second for a 7B model with 4-bit dequantization and checkpointing                                                         | stopped; the notebook also runs on Kaggle with `EPOCHS = 1`, but the 3B was chosen instead                                                         |
| Colab `TypeError: warmup_ratio`                                   | newer `transformers` removed it                                                                                                         | `warmup_steps`                                                                                                                                     |
| Colab pip warning about `pyarrow` and `cudf`                      | preinstalled `cudf` is not used                                                                                                         | ignored                                                                                                                                            |

### Data and test design

| problem                                                                    | cause                                                                                                                 | fix                                                                                                                                                                 |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| tests were too easy                                                        | seed and hard sets were written by the same author as the templates, so their wording matched training                | an independent set: held-out problems rewritten by a different model (gemma3 or qwen2.5-coder via Ollama), kept only if every number and asked quantity survived    |
| v1 scored 14/21 on the seed set but 150/150 on held-out generated problems | it had learned the template wording, not the language                                                                 | v2: ask framings, synonyms, mixed units (g, cm, km/h), distractor sentences, component-form velocities, more object names                                           |
| the spring-block misses                                                    | first guessed to be a harness fairness issue (start height); wrong                                                    | the model had written no `contacts` entry, so the block was not on the floor                                                                                        |
| 11 of 12 in-scope questions in the owner's list failed on first contact    | out-of-scope questions got a confident wrong scene; one friction coefficient given (not two) produced an invented 0.1 | a refusal path with 23 categories of out-of-scope questions; friction questions that state only the kinetic or one generic coefficient (the scene uses it for both) |
| "1 seconds", "a 8 kg", outcome words like "slides" in questions            | template wording                                                                                                      | helper functions for plurals and articles, and a test that questions never leak outcomes                                                                            |
| the same question rendered twice with different parents                    | small parameter spaces at 6,000 problems                                                                              | the dataset builder keeps such questions in training only and reports how many it dropped                                                                           |
| paraphrases changed the physics                                            | for example "stretched" became "compressed"                                                                           | a drift filter (compress, bounce, ...) when merging; 32 dropped                                                                                                     |
| paraphrase tool rejected most outputs                                      | models add chatty framing ("Here is a rewrite:")                                                                      | `extract_problem` keeps the problem paragraph; the yield rose from roughly 40 to roughly 55 percent                                                                 |
| Ollama paraphrasing did not speed up with threads                          | one GPU serializes requests                                                                                           | ran sequentially, resumable; about 7 problems a minute                                                                                                              |

### The solver

| problem                                                        | cause                                                                   | fix                                                                                                                                   |
| -------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| a ball launched upward from the ground flew in a straight line | a body touching a plane was treated as held on it even when moving away | a touching body that moves away from the surface leaves it                                                                            |
| a projectile "lands" 0.1 m early                               | the default authoring shape is a 0.4 x 0.2 x 0.4 box                    | projectile scenes use `"shape": {"kind": "point"}`                                                                                    |
| "when does it stop" failed beyond 2 s                          | the default window was 2 s                                              | event-driven queries (time until, range, max height, open-ended distance) default to 60 s                                             |
| mass was required                                              | the schema needed it                                                    | optional, default 1 kg with a warning                                                                                                 |
| no way to say "accelerates at 3 m/s^2"                         | only forces move bodies                                                 | `constantAcceleration` adds the force `m (a - g)`; the key is not `acceleration` because the validator reserves that name for answers |
| impact velocity read as zero                                   | the event timestamp is after the body comes to rest                     | queries at `{event: land}` read the instant before impact                                                                             |

### Export and inference

| problem                                               | cause                                                                                                                                                                                   | fix                                                                                                                                                                                                                  |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ollama could not import the model                     | its safetensors importer does not support Qwen2, and `q8_0` is not an accepted quantization                                                                                             | `mlx_lm.fuse --dequantize`, then llama.cpp `convert_hf_to_gguf.py` and `llama-quantize` to Q8_0, then `ollama create` from the GGUF                                                                                  |
| the converter crashed                                 | `extra_special_tokens` was a list in the fused tokenizer config                                                                                                                         | removed it before converting                                                                                                                                                                                         |
| constrained decoding made things worse                | a grammar that allows a scene or a refusal made the model refuse 10 in-scope questions; a scene-only grammar scored 0/10 because queries were dropped                                   | not used; the exported model's plain output matched MLX exactly (20/30), so the export is faithful                                                                                                                   |
| the model sometimes drops or invents a query          | a small model under-attends to the second and third ask; samples make the same slip                                                                                                     | self-consistency voting (`--vote K`) gave 20 to 22 of 30; the real fix is in section 8                                                                                                                               |
| correct scenes were scored as failures                | with mass optional, a body has no mass to name it by, so the answer matching fell back to the body id and treated the gold `car` and the model's `body` as different bodies             | bodies without a mass are matched by position in the list; the owner's 30 questions went from 20/25/26 to 22/28/29 for v3/v4/v5, and the three items I had called "dropped queries" (u5, u8, u10) were never dropped |
| Hugging Face cache folders vanished mid-run           | the model snapshot folders were removed while the machine was unattended; the large weight files remained                                                                               | re-ran `snapshot_download` for the 3B base (the small files fetch in seconds and the weights are reused)                                                                                                             |
| unclear which Ollama blobs could go                   | the cache holds only `sha256-...` file names                                                                                                                                            | read Ollama's manifests to map each blob to its model; always remove with `ollama rm`, never by deleting blobs                                                                                                       |
| v7 training went NaN after about 400 iterations       | continued training of the 3B model from v6 at a learning rate of 3e-5 with no gradient clipping; the loss crept from 0.067 up to 0.33 and then NaN, and the saved adapter was corrupted | moved the broken adapter aside, retrained from v6 with gradient clipping (norm 1.0) and float32 LoRA weights (`train_mlx.py` with `BASE_FP32=0`) at 1.5e-5, with a watcher that alerts on a loss above 0.12          |
| a "wait until training ends" loop never ended         | `pgrep -f mlx_lm.lora` matched the shell that was running the loop (the text is in its own command line)                                                                                | wait on a line in the training log instead of on a process name                                                                                                                                                      |
| the model forgot `"shape": "point"` in a flight scene | a 0.4 m default box lands 0.1 m early, which changed max height by 0.1 m                                                                                                                | a body with a position or velocity and no placement now defaults to a point in the solver itself                                                                                                                     |
| two bodies meeting could not be asked                 | no event for it; also a pursuer that starts at once begins coincident with the leader                                                                                                   | a `meet` event (separation along the initial line, or along the relative velocity when they start together) with tests, and a `chase` training family                                                                |

## 5. Solver extension (TypeScript)

Branch `v3-flight-and-scope`, PR 4. New queries: `time until land`, `max_height` (`above: ground` or `start`),
`range`; velocity or position `at: {event: "land"}`. New behaviours: launches leave the surface, event-driven
default window of 60 s, optional mass, `constantAcceleration`. 125 Vitest tests, hand-computed values, three new
example pairs, updated `docs/SCHEMA.md` and `schema/authoring.schema.json`.

## 6. Process lessons

- Measure with the real solver. Comparing text hides scenes that look right and compute wrong.
- A test written by the author of the training data is a sanity check, not evidence. Keep a test nobody has tuned on.
- A silent fallback is worse than an error: both the context truncation and the constrained-decoding no-op produced
  plausible numbers that meant nothing.
- When a metric flags something, check whether the metric is wrong (grounding was, twice) before blaming the model.
- Saturated tests stop discriminating. When three models tie, build a harder test, not a bigger model.
- A refusal path matters as much as accuracy: a confident wrong answer is the worst failure for a tutor.
- Inspect real outputs before designing a fix, and re-score old runs when a metric bug is found: three earlier
  conclusions (dropped queries, the v3 and v4 numbers) were wrong because of one matching rule.

## 7. Open limits

- Only about a third of textbook problems are expressible: no vectors, circular motion, pulleys, connected bodies,
  relative motion, series or parallel springs, energy methods, collisions, or inverse problems.
- On the owner's 30 questions v5 gets all 10 in-scope questions right and refuses 19 of 20 out-of-scope ones; the
  one miss (a "minimum stretch to start sliding" question) is now covered by new refusal categories that are not
  trained yet.
- A true dropped query still shows up occasionally on the paraphrase set (3 misses of 300 for v5).
- The owner's 30 questions are a development set; a fresh set is needed for a clean number.
- Training used about 3 hours per version on a 16 GB Mac; there is no cloud route that is both free and fast enough.

## 8. The dropped-query fix (v5)

Diagnosis at the time: every in-scope miss on the owner's questions was a missing query (u5, u8, u10 looked like
a dropped velocity or time-of-flight query). Fix, three parts: (1) a `"title": "find: ..."` line the model writes
before the scene, listing every quantity asked; (2) a completeness check, so a scene that declares more things than
it queries loses the vote (`--vote K`); (3) more training questions with three to five asks, in shuffled order
(4,000 new verified problems). v5 was trained from the v4 weights on 22,492 examples.

What actually happened: v5 improved a little (owner's questions 28 to 29, hard set 14 to 15, paraphrases 295 to
297), but when its outputs for u5, u8 and u10 were inspected they were **complete and right**; those three had been
scored as failures by the body-id bug in section 4. The biggest single gain on the dev set came from fixing the
metric, not from the model change.

Lessons: look at the actual outputs before designing a fix (the `find:` line was built on a wrong diagnosis, and it
still helped, but not for the reason assumed); a metric that disagrees with your reading of the output is a
candidate bug.

Voting on top of v5 and the exported Ollama model: see `model/RESULTS.md`.

## 9. A clean test, a safety net, the pipeline

**Clean test.** The owner supplied 30 more, harder questions (numbers 31 to 60). They were scored on v5 before
any change, so the number is clean: **25/30** (the one in-scope question right, 24 of 29 refusals). It is a mostly
refusal test: vectors, two bodies meeting, calculus-defined motion, pulleys, contact forces, springs in series,
thresholds, and circular motion are all out of scope today.

**What the failures showed.** Five out-of-scope questions got a scene. In two of them the model's own `find:` line
named the problem ("separation", "equilibrium"): it noticed the question wanted something the solver cannot
compute, and wrote a scene anyway. That became a rule in plain code: if the declared asks include anything outside
the solver's vocabulary, treat the answer as a refusal (24 to 26 of 29, no retraining). The other three
(a cubic position function, deceleration growing with time, the largest extension at rest) look like ordinary asks,
so they need training data.

**New refusal categories (v6 data).** Position as a function of time, deceleration that changes with time, two
projectiles compared, a block pressed against a wall, the largest value at rest, a rough then smooth floor, maximum
spring compression, and thresholds to start moving or sliding. The refusal share of the training set was cut back to
about 16% so the model does not start refusing in-scope questions.

**App-side pipeline (`parser_model/pipeline.py`).** Question, model, checks, solver, explanation, with retries and
intent labels. The model stays a narrow translator; reliability lives in code that can be tested. Details in
`model/RESULTS.md`.

Hiccup worth recording: one of the new files tripped the linter on long template strings (fixed with a per-file
ignore for the refusal templates and wrapped lines elsewhere), and the pipeline's first draft wrote "Impact velocity
at the instant of land" (reworded to "Impact velocity").

## 10. v6, the `meet` event, and the v7 attempts

**v6** continued from v5 with 1,800 iterations on 29,446 examples (refusals cut back to about 16%), including 1,800
new refusal-focused problems and 1,500 in-scope problems to keep the balance. It refuses four more of the second
batch's out-of-scope questions (#38, #40, #41, #43) and scores 27/30 on that batch (v5: 25). Seed set 21/21, hard set
15/15.

**The `meet` event.** Many of the owner's questions (the police chase, cars overtaking, two balls) need "when do two
bodies reach the same place". That became a solver feature: an event that fires when the separation along the initial
line between two bodies reaches zero (or along their relative velocity when they start together), a `with` field on
the time query, positions at the meeting for either body, a validation check, tests against closed forms, and a
`chase` training family. "Two bodies meeting" was removed from the refusal categories, and the older refusal examples
of that reason are dropped when the data is built (`--drop-refusal`). The owner's questions #9 and #36 changed from
"should refuse" to in scope; #37 was removed from the scoring (its balls never meet).

**v7 diverged twice.** Resuming from v6 on the new data mix, the loss was fine for about 300 iterations and then
climbed to NaN: first at a learning rate of 3e-5, then with gradient clipping, float32 LoRA weights and 1.5e-5. The
data was inspected (no anomalies), and a checkpoint was checked in full precision (still bad), which ruled out float16
arithmetic as the sole cause. The healthy iteration-300 checkpoint learned chase (89/90) but stopped refusing things
v6 refused and regressed on the seed set, so it was not kept. Lesson: three resumed trainings in a row (v5, v6, v7)
are one long run with restarted optimizer state; when it goes wrong, train from scratch on the full data.

**v8** trains the same 31,144 examples from scratch (3,500 iterations, 1e-4, clipping). Results will be added here and
to `model/RESULTS.md`.

## 11. File map

| path                                                                                       | what it is                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model/src/parser_model/`                                                                  | prompts, inference client, solver wrapper, grounding, metrics, evaluate CLI, generator, phrasing, refusals, dataset builder, splits, OpenStax extractor, paraphrase tool, voting |
| `model/train_mlx.py`, `model/generate_mlx.py`                                              | float32 MLX training and generation                                                                                                                                              |
| `model/colab/`                                                                             | Colab/Kaggle notebook for 7B LoRA                                                                                                                                                |
| `model/data/seed.jsonl`, `model/data/hard.jsonl`                                           | the hand-written test sets                                                                                                                                                       |
| `model/RESULTS.md`                                                                         | all numbers                                                                                                                                                                      |
| `packages/core/src/solver`, `authoring`                                                    | the solver extension                                                                                                                                                             |
| `model/private/`, `model/data/ft*/`, `model/adapters/`, `model/exports/`, `model/results/` | gitignored: third-party material, generated data, weights, outputs                                                                                                               |

# model/: word problem -> authoring scene

The history of this work (every problem and fix) is in [`docs/MODEL_DEVELOPMENT.md`](../docs/MODEL_DEVELOPMENT.md); the numbers are in [`RESULTS.md`](RESULTS.md).

Python side of the project. This directory holds an **evaluation harness** and a **seed set** for
measuring how well off-the-shelf small models turn word problems into authoring scenes
(`schema/authoring.schema.json`, schema v1.1). No training yet. The TypeScript packages are not
touched; the harness only calls `pnpm solve`.

## Setup

Needs Python 3.11+, plus Node 24 and `pnpm install` done at the repo root (the solver is TypeScript).

```bash
cd model
python3.12 -m venv .venv          # any Python >= 3.11 (macOS system python3 is too old)
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                  # unit tests + a self-check of the real solver on the gold scenes
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

`pnpm` 11 refuses to start on Node 20. `parser_model.solve` therefore puts the Node named by the
repo's `.nvmrc` (found under `~/.nvm/versions/node`) first on `PATH`. To use something else, set
`NEWTONS_NODE_BIN=/path/to/node/bin` or `NEWTONS_SOLVE_CMD="pnpm --silent solve"`.
Tests marked `solver` are skipped when pnpm cannot run.

## Run a model locally with Ollama

The prompt holds the whole schema plus 3 worked examples, roughly 6-8k tokens. **Ollama's default
context is 4096 tokens, which silently truncates it** and makes the scores meaningless (the harness
reads the model's `num_ctx` from Ollama and warns when it is too small). Raise it:

```bash
OLLAMA_CONTEXT_LENGTH=16384 ollama serve      # or: ollama run <model>, then /set parameter num_ctx 16384
ollama pull qwen2.5:7b
```

To keep a server running as-is, bake the context into a model variant instead:
`printf 'FROM qwen2.5:7b\nPARAMETER num_ctx 16384\n' > Modelfile && ollama create qwen2.5-16k -f Modelfile`.

Any OpenAI-compatible server works: Ollama (`http://localhost:11434/v1`, the default),
llama.cpp (`llama-server -m model.gguf -c 16384 --port 8080`, then `--base-url http://localhost:8080/v1`),
vLLM (`vllm serve <model> --max-model-len 16384`, `--base-url http://localhost:8000/v1`).

## Run the eval

```bash
cd model
.venv/bin/python -m parser_model.evaluate --model qwen2.5:7b --seed data/seed.jsonl
```

Useful flags:

| flag | meaning |
| --- | --- |
| `--base-url`, `--api-key` | server to call (defaults to local Ollama) |
| `--temperature` | default 0 |
| `--no-think` | turn thinking off: appends `/no_think`, sends `chat_template_kwargs.enable_thinking=false` and `reasoning_effort=none` (dropped if the server rejects them), and strips `<think>` blocks |
| `--constrained` | JSON-schema constrained decoding. Tries `response_format: json_schema`; if the server answers 4xx it falls back to vLLM `guided_json`, llama.cpp `json_schema`, Ollama's native `/api/chat` `format`, and finally `json_object`. The mode that worked is saved in the results file |
| `--no-schema-in-prompt` | leave the schema text out of the prompt (pair with `--constrained`, or for small contexts) |
| `--shots N` | few-shot examples per prompt (default 3) |
| `--example`, `--style`, `--limit` | run a subset |

Few-shot examples are leave-one-out: a question's own example is never in its prompt. Items marked
`"pending": true` in the seed (atwood, table-hanging; no authoring twin yet) are skipped.

## The metrics

Each item is scored on five independent checks; the table shows `passed/total`.

| metric | passes when |
| --- | --- |
| `valid_json` | the output (after removing `<think>` blocks and one surrounding code fence) is a JSON object |
| `schema_valid` | it validates against the JSON Schema |
| `solver_ok` | `pnpm solve` exits 0 |
| `grounded` | every number in the scene (strings like `"30 deg"` are unit-converted to SI) is in the question, or is a default (`g = 9.81`, `0`), or is a derived pair (hypot/atan2 of two same-unit question values, so "10 m/s across and 10 m/s up" may be `14.14 m/s at 45 deg`). `title` and `version` are ignored. Signs are ignored |
| `solver_match` | solving the gold scene (`examples/<example>.scene.json`) and the model scene gives the same answers within relative tolerance 1e-3 |

`solver_match` pairs queries by a **signature**, never by query id: `(ask, body, force, connection,
until, at, from, to)`. `connection` and `from`/`to` go beyond the basic signature so tension and
work queries stay distinct. Bodies are named by their mass, and connections by the masses they
join, so `"box"` and `"block"` count as the same body. A model scene with extra queries is not
penalised; a missing or wrong gold query is.

## Reading the results file

`results/<model>-<timestamp>.json` (gitignored) holds:

- `meta`: model, all CLI args, `constrained_mode` actually used, schema file, prompt size estimate.
- `summary`: per example and `overall`, with `n`, `<metric>_count` and `<metric>` (rate).
- `items[]`: for every item `id`, `example`, `style`, `question`, `raw_output` (exactly what the
  model returned), `scene` (parsed, or null), the five booleans, `failure_reason` (the first failing
  stage) and `failures` (all of them), plus `schema_errors`, `ungrounded` (JSON paths and values),
  `mismatches` (per gold query), `solver` (exit code, answers, warnings, issues) and `infer`
  (mode, seconds, token usage, or `error`).

```bash
# every failing item with its first failure reason
jq -r '.items[] | select(.failure_reason != "") | "\(.id)\t\(.failure_reason)"' results/<file>.json
# the raw output of one item
jq -r '.items[] | select(.id == "floor-push/casual") | .raw_output' results/<file>.json
# which numbers models invent
jq -r '.items[] | .ungrounded[]? | "\(.path) = \(.value)"' results/<file>.json | sort | uniq -c | sort -rn
```

`failure_reason` starts with `invalid_json`, `schema`, `solver_exit_<n>`, `ungrounded`, `mismatch`,
or `infer_error`.

## Seed set

`data/seed.jsonl`: one record per line, `{id, example, style, question}` (+ `pending`). Three
phrasings (`textbook`, `casual`, `terse`) for each of the 9 examples. Every question gives all the
givens of its gold scene (including ones the gold scene carries but the title omits, such as
`mu_k` and the ramp length) and asks for exactly the quantities in that example's queries, without
saying what happens ("it slides"). **The questions are a first draft for review**; if you change a
given, check the gold scene still matches, and the tests will tell you if a gold authoring scene
stops being grounded in any phrasing.

## Layout

```
src/parser_model/  prompts.py infer.py solve.py grounding.py metrics.py evaluate.py paths.py
tests/             grounding, signatures, metrics (synthetic), infer fallbacks, real-solver self-check
data/seed.jsonl    27 questions
```

## Fine-tuning (LoRA on Apple silicon with MLX)

Training data is generated, not scraped: `parser_model.generate` has six template families
(floor-push, incline, sliding-stop, projectile, free-fall, spring-block). Each problem has three
phrasings (textbook, casual, terse), a gold authoring scene, and closed-form answers that are
**checked against the real solver** before the problem is kept. `parser_model.openstax` extracts
exercises from OpenStax University Physics (CC BY) into `private/` as a source of real textbook
phrasing for the held-out test set.

```bash
# 1. build the dataset (1500 verified problems -> train/val/test, split by problem)
.venv/bin/python -m parser_model.dataset --problems 1500 --seed 0 --out data/ft
mkdir -p data/ft/mlx && cp data/ft/train.jsonl data/ft/mlx/ && cp data/ft/val.jsonl data/ft/mlx/valid.jsonl

# 2. train (separate venv: python3.12 -m venv .venv-train && .venv-train/bin/pip install mlx-lm)
BASE=$(ls -d ~/.cache/huggingface/hub/models--mlx-community--Qwen2.5-Coder-7B-Instruct-4bit/snapshots/*)
.venv-train/bin/python -m mlx_lm.lora --model "$BASE" --train --data data/ft/mlx \
  --adapter-path adapters/qwen7b-v1 --iters 1200 --batch-size 4 --num-layers 16 \
  --learning-rate 1e-4 --max-seq-length 1280 --grad-checkpoint

# 3. serve the tuned model (OpenAI-compatible) and evaluate with the SAME short prompt as training
.venv-train/bin/python -m mlx_lm.server --model "$BASE" --adapter-path adapters/qwen7b-v1 --port 8081
.venv/bin/python -m parser_model.evaluate --model tuned --base-url http://localhost:8081/v1 \
  --shots 0 --no-schema-in-prompt --seed data/seed.jsonl           # the 27 hand-written questions
.venv/bin/python -m parser_model.evaluate --model tuned --base-url http://localhost:8081/v1 \
  --shots 0 --no-schema-in-prompt --seed data/ft/test.jsonl         # held-out generated problems
```

Rules the data pipeline enforces (`splits.py`, `dataset.py`):

* Split by *problem*: all phrasings of a problem share a split (about 70/10/20 train/val/test).
* The 27 seed questions and their gold scenes are never in train/val; a generated problem whose
  scene equals a hand-written example is dropped.
* The prompt is the same short one in training and at test time (`prompts.finetune_messages`),
  which has no schema text and no examples. The model has to have learned the schema.
* `data/ft/`, `adapters/` and `private/` are gitignored. Everything in `data/ft` is reproducible
  from the seed.

Known limits of what the solver can ask (found while writing the generator): the only `time`
events are `stop`, `edge`, `slack`, `slide_start`, so "time to hit the ground" and "maximum height"
cannot be asked; and a `distance` query covers only the simulation window, so stopping distance
needs a work window in the same scene to extend it.

### Training on Colab / Kaggle instead (7B)

`colab/train_qwen7b.ipynb` trains the same data with Hugging Face PEFT (4-bit LoRA) and writes the raw
model outputs to `outputs.json`. `colab/bundle.zip` (gitignored; rebuild it by zipping `data/ft/{train,val,test}.jsonl` and
`data/seed.jsonl` under `data/`) is the only upload. Back here, score the outputs with exactly the
same metrics as any other model (the solver runs locally, so Colab does not need Node):

```bash
.venv/bin/python -m parser_model.evaluate --model qwen7b-colab --outputs outputs.json --seed data/seed.jsonl
.venv/bin/python -m parser_model.evaluate --model qwen7b-colab --outputs outputs.json --seed data/ft/test.jsonl
```

Note: a free T4 has no bf16, so fp16 training can overflow (the MLX 7B run hit NaN losses). If the
notebook's loss goes NaN, use an L4/A100 runtime or lower the learning rate.

### 7B on a 16 GB Mac: the float16 NaN, and the fix

`mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` stores its scales, biases and norms in float16, and
Qwen2.5-7B overflows float16 activations: the loss goes NaN after ~20 iterations at any learning
rate (the 3B model is fine). bfloat16 trained unstably instead. What works is float32 activations
(the 4-bit weights stay packed):

```bash
# train (same flags as mlx_lm.lora; adds float32 cast + gradient clipping)
.venv-train/bin/python train_mlx.py --model "$BASE7" --train --data data/ft2/mlx \
  --adapter-path adapters/qwen7b-v2 --iters 900 --batch-size 4 --num-layers 16 \
  --learning-rate 5e-5 --max-seq-length 1280 --grad-checkpoint

# generate with the same dtype (the stock mlx_lm.server would load float16 and overflow),
# then score offline with the usual metrics
PYTHONPATH=src .venv-train/bin/python generate_mlx.py --base "$BASE7" --adapter adapters/qwen7b-v2 \
  --seed data/hard.jsonl --out results/qwen7b-hard-outputs.json
.venv/bin/python -m parser_model.evaluate --model qwen7b-v2 --outputs results/qwen7b-hard-outputs.json \
  --seed data/hard.jsonl
```

Speed on an M-series Mac with 16 GB: about 135 tokens/s, so roughly 10 s per iteration at batch 4.
Do not run generation while training: both want the GPU memory.


## v3: wider scope, and refusing what the solver cannot do

The solver gained (TypeScript, `packages/core`, see `docs/SCHEMA.md`): `time until land` (time of flight),
`max_height` (above the ground or the start), `range`, launches that leave the surface, an event-driven
default window of 60 s (so "when does it stop" and "how far does it go" need no window), an optional
`mass` (default 1 kg) and `constantAcceleration` (kinematics with no force and no mass). The generator
gained the matching families: `flight`, `spring-release` (initial net force and acceleration), `kinematics`,
questions that give only one friction coefficient (the scene uses it for both), and `unsupported`.

`unsupported` is a refusal path. For questions that cannot be written as a scene (vectors, relative
motion, pulleys, connected bodies, apparent weight, spring combinations, static spring extension,
circular motion, calculus-defined motion, inverse problems, energy methods, momentum, rotation, and
non-mechanics questions) the target output is `{"unsupported": "<reason>"}`. The metrics count a correct
refusal as a pass and a refusal of an in-scope question as a failure (`refused_in_scope`).

```bash
.venv/bin/python -m parser_model.dataset --problems 4500 --seed 2 --out data/ft3
mkdir -p data/ft3/mlx && cp data/ft3/train.jsonl data/ft3/mlx/ && cp data/ft3/val.jsonl data/ft3/mlx/valid.jsonl
.venv-train/bin/python -m mlx_lm.lora --model "$BASE3" --train --data data/ft3/mlx \
  --adapter-path adapters/qwen3b-v3 --iters 2000 --batch-size 4 --num-layers 16 \
  --learning-rate 1e-4 --max-seq-length 1280 --grad-checkpoint
```

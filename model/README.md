# model/: word problem -> authoring scene

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

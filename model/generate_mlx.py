"""Generate raw outputs from an MLX model + LoRA adapter, for offline scoring.

    python generate_mlx.py --base <model dir> --adapter adapters/qwen7b-v2 \
        --seed data/seed.jsonl --out results/qwen7b-seed-outputs.json
    python -m parser_model.evaluate --model qwen7b-v2 --outputs results/qwen7b-seed-outputs.json \
        --seed data/seed.jsonl

The model is loaded the way ``train_mlx.py`` trained it (float16 parameters cast to float32), because
the 4-bit Qwen2.5-7B overflows in float16. The prompt is the fine-tuning prompt (no schema, no examples).
"""

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
from mlx.utils import tree_map
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from parser_model.prompts import finetune_messages


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--adapter")
    p.add_argument(
        "--seed", required=True, help="jsonl with id and question (pending items skipped)"
    )
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--max-tokens", type=int, default=900)
    p.add_argument("--no-fp32", action="store_true", help="keep the checkpoint's float16 dtype")
    args = p.parse_args()

    model, tok = load(args.base, adapter_path=args.adapter)
    if not args.no_fp32:
        model.update(
            tree_map(
                lambda x: x.astype(mx.float32) if x.dtype == mx.float16 else x, model.parameters()
            )
        )
    items = [json.loads(line) for line in Path(args.seed).read_text().splitlines() if line.strip()]
    items = [i for i in items if not i.get("pending")][: args.limit]
    sampler = make_sampler(temp=0.0)
    outputs: dict[str, str] = {}
    start = time.time()
    for n, item in enumerate(items, 1):
        prompt = tok.apply_chat_template(
            finetune_messages(item["question"]), add_generation_prompt=True, tokenize=False
        )
        outputs[item["id"]] = generate(
            model, tok, prompt=prompt, max_tokens=args.max_tokens, sampler=sampler
        )
        if n % 10 == 0 or n == len(items):
            print(f"{n}/{len(items)} done, {time.time() - start:.0f}s", flush=True)
    Path(args.out).write_text(json.dumps(outputs))


if __name__ == "__main__":
    main()

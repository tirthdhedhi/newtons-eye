"""CLI: score a model on the seed set.

    python -m parser_model.evaluate --model qwen2.5:7b --seed data/seed.jsonl

Items marked ``"pending": true`` (no authoring twin yet) are skipped. Every other item gets a
leave-one-out prompt, one model call, and the five metrics from ``metrics``. A JSON file with
every raw output and failure reason is written to ``results/<model>-<timestamp>.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths
from .infer import ChatClient, InferConfig, InferError, detect_context_length
from .metrics import METRICS, GoldCache, ItemResult, evaluate_item, summarize
from .prompts import build_messages
from .solve import solve_scene


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="parser_model.evaluate", description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--seed", default=str(paths.model_dir() / "data" / "seed.jsonl"))
    p.add_argument("--base-url", default="http://localhost:11434/v1")
    p.add_argument("--api-key", default=None)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--no-think", action="store_true", help="disable thinking modes")
    p.add_argument("--constrained", action="store_true", help="JSON-schema constrained output")
    p.add_argument("--no-schema-in-prompt", action="store_true", help="omit the schema text")
    p.add_argument("--shots", type=int, default=3, help="few-shot examples per prompt")
    p.add_argument("--example", action="append", help="only these examples (repeatable)")
    p.add_argument("--style", action="append", help="only these styles (repeatable)")
    p.add_argument("--limit", type=int, help="stop after N items")
    p.add_argument(
        "--outputs",
        help="score a JSON file {item id: raw model output} instead of calling a model "
        "(e.g. outputs generated on Colab); --model then only labels the results",
    )
    p.add_argument("--out-dir", default=str(paths.model_dir() / "results"))
    return p.parse_args(argv)


def select_items(seed: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    items = [i for i in seed if not i.get("pending")]
    if args.example:
        items = [i for i in items if i["example"] in args.example]
    if args.style:
        items = [i for i in items if i["style"] in args.style]
    return items[: args.limit] if args.limit else items


def format_table(summary: dict[str, dict[str, Any]]) -> str:
    header = ["example", "n", *METRICS]
    rows = [header]
    for name in [k for k in summary if k != "overall"] + ["overall"]:
        s = summary[name]
        rows.append([name, str(s["n"])] + [f"{s[f'{m}_count']}/{s['n']}" for m in METRICS])
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    lines = [
        "  ".join(
            c.ljust(w) if i == 0 else c.rjust(w)
            for i, (c, w) in enumerate(zip(r, widths, strict=True))
        )
        for r in rows
    ]
    lines.insert(1, "  ".join("-" * w for w in widths))
    lines.insert(len(lines) - 1, lines[1])
    return "\n".join(lines)


def results_path(out_dir: str | Path, model: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    return Path(out_dir) / f"{safe}-{stamp}.json"


def run(args: argparse.Namespace) -> tuple[list[ItemResult], dict[str, Any]]:
    schema = paths.load_schema()
    items = select_items(paths.load_seed(args.seed), args)
    config = InferConfig(
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        no_think=args.no_think,
        constrained=args.constrained,
        api_key=args.api_key,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )
    client = ChatClient(config, schema=paths.constrained_schema() if args.constrained else None)
    offline = json.loads(Path(args.outputs).read_text()) if args.outputs else None
    prompt_chars = sum(
        len(m["content"])
        for m in build_messages("", None, k=args.shots, include_schema=not args.no_schema_in_prompt)
    )
    prompt_tokens = int(prompt_chars / 2.5)
    context = detect_context_length(args.base_url, args.model)
    if context is not None and context < prompt_tokens + args.max_tokens:
        print(
            f"warning: prompts are ~{prompt_tokens} tokens but the server context is {context}. "
            "Prompts get silently truncated and the scores are meaningless; raise the context "
            "(see model/README.md) or pass --no-schema-in-prompt.",
            file=sys.stderr,
        )
    gold = GoldCache(lambda ex: json.loads(paths.gold_scene_path(ex).read_text()), solve_scene)
    results: list[ItemResult] = []
    try:
        for n, item in enumerate(items, 1):
            if offline is not None:
                raw, info = offline.get(item["id"], ""), {"mode": "offline"}
                if item["id"] not in offline:
                    info = {"mode": "offline", "error": "no output for this item"}
                result = evaluate_item(item, raw, schema=schema, gold=gold, solver=solve_scene)
                result.infer = info
                if "error" in info:
                    result.failures.insert(0, f"infer_error: {info['error']}")
                results.append(result)
                flags = "".join("." if getattr(result, m) else "x" for m in METRICS)
                print(
                    f"[{n}/{len(items)}] {item['id']:<36} {flags}  {result.failure_reason[:80]}",
                    file=sys.stderr,
                )
                continue
            messages = build_messages(
                item["question"],
                item["example"],
                k=args.shots,
                include_schema=not args.no_schema_in_prompt,
            )
            try:
                completion = client.complete(messages)
                raw, info = (
                    completion.raw,
                    {
                        "mode": completion.mode,
                        "seconds": round(completion.seconds, 2),
                        "usage": completion.usage,
                    },
                )
            except InferError as e:
                raw, info = "", {"error": str(e)}
            result = evaluate_item(item, raw, schema=schema, gold=gold, solver=solve_scene)
            result.infer = info
            if "error" in info:
                result.failures.insert(0, f"infer_error: {info['error'][:200]}")
            results.append(result)
            flags = "".join("." if getattr(result, m) else "x" for m in METRICS)
            print(
                f"[{n}/{len(items)}] {item['id']:<36} {flags}  {result.failure_reason[:80]}",
                file=sys.stderr,
            )
    finally:
        client.close()
    meta = {
        "model": args.model,
        "args": vars(args),
        "constrained_mode": client.mode,
        "prompt_chars_estimate": prompt_chars,
        "server_context": context,
        "schema": str(paths.schema_path().relative_to(paths.repo_root())),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return results, meta


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results, meta = run(args)
    summary = summarize(results)
    print(format_table(summary))
    out = results_path(args.out_dir, args.model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"meta": meta, "summary": summary, "items": [r.to_dict() for r in results]},
            indent=2,
        )
    )
    print(f"\nresults: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

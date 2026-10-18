"""Build chat-format fine-tuning files from generated problems, with held-out splits.

    python -m parser_model.dataset --problems 1500 --seed 0 --out data/ft

Writes ``train.jsonl`` and ``val.jsonl`` (mlx-lm / OpenAI chat format) plus ``test.jsonl``, the
held-out problems in the evaluation-seed format (``id, example, style, question``) so
``parser_model.evaluate --seed data/ft/test.jsonl`` scores them. The gold scene of a test item is
its own ``scene``, so test records also carry it. Nothing from the 27-question seed set or its gold
scenes is ever in train/val.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import paths
from .generate import build
from .prompts import finetune_messages
from .splits import _normalise, assign, check_no_leakage


def compact(scene: dict[str, Any]) -> str:
    return json.dumps(scene, separators=(",", ":"), ensure_ascii=False)


def seed_scene_keys() -> set[str]:
    """Canonical form of every hand-written authoring scene, so no generated problem equals one."""
    keys = set()
    for path in paths.examples_dir().glob("*.authoring.json"):
        scene = json.loads(path.read_text())
        scene.pop("title", None)
        keys.add(json.dumps(scene, sort_keys=True))
    return keys


def chat_record(record: dict[str, Any]) -> dict[str, Any]:
    messages = finetune_messages(record["question"])
    messages.append({"role": "assistant", "content": compact(record["scene"])})
    return {"id": record["id"], "parent": record["parent"], "messages": messages}


def load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def make_dataset(
    records: list[dict[str, Any]], out_dir: Path, holdout_families: tuple[str, ...] = ()
) -> dict[str, Any]:
    forbidden = seed_scene_keys()
    kept = []
    for record in records:
        scene = dict(record["scene"])
        scene.pop("title", None)
        if json.dumps(scene, sort_keys=True) not in forbidden:
            kept.append(record)
    splits = assign(kept, holdout_families)
    # Two different problems can render the same question (same numbers): keep it in training only.
    train_questions = {_normalise(r["question"]) for r in splits["train"]}
    dropped_dupes = 0
    for name in ("val", "test"):
        unique = [r for r in splits[name] if _normalise(r["question"]) not in train_questions]
        dropped_dupes += len(splits[name]) - len(unique)
        splits[name] = unique
    check_no_leakage(splits)
    seed_questions = {
        r["question"] for r in paths.load_seed(paths.model_dir() / "data" / "seed.jsonl")
    }
    for name in ("train", "val"):
        if any(r["question"] in seed_questions for r in splits[name]):
            raise ValueError(f"a seed question leaked into {name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "train.jsonl", [chat_record(r) for r in splits["train"]])
    write_jsonl(out_dir / "val.jsonl", [chat_record(r) for r in splits["val"]])
    write_jsonl(
        out_dir / "test.jsonl",
        [
            {
                "id": r["id"],
                "example": r["family"],
                "style": r["style"],
                "question": r["question"],
                "scene": r["scene"],
                **({"expect": r["expect"]} if "expect" in r else {}),
            }
            for r in splits["test"]
        ],
    )
    return {
        "dropped_as_seed_duplicates": len(records) - len(kept),
        "dropped_val_test_questions_also_in_train": dropped_dupes,
        **{name: len(rows) for name, rows in splits.items()},
        "problems": {name: len({r["parent"] for r in rows}) for name, rows in splits.items()},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--problems", type=int, default=1500)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=str(paths.model_dir() / "data" / "ft"))
    p.add_argument("--holdout-family", action="append", default=[])
    p.add_argument("--workers", type=int, default=4)
    p.add_argument(
        "--reuse", action="store_true", help="use an existing synthetic.jsonl, do not regenerate"
    )
    p.add_argument(
        "--extra",
        action="append",
        default=[],
        help="more records to merge before splitting (e.g. paraphrases); split by their parent",
    )
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "synthetic.jsonl"
    if args.reuse and raw.exists():
        print(f"reusing {raw}")
    else:
        report = build(args.problems, args.seed, raw, args.workers)
        print(f"generated {report['kept']}/{report['requested']} verified problems")
        for pid, why in report["dropped"][:10]:
            print(f"  dropped {pid}: {why[:120]}")
    records = load_records(raw)
    for extra in args.extra:
        records += load_records(Path(extra))
    summary = make_dataset(records, out, tuple(args.holdout_family))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

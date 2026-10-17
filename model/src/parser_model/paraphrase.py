"""Independent test wording: have a different model rewrite held-out questions.

A paraphrase is kept only if it has exactly the original's numbers and the right asks, so the gold
scene of the source problem still applies. The paraphrasing model never saw the parser's training
data, so its wording is not the generator's.

    python -m parser_model.paraphrase --model qwen2.5-coder:7b --source data/ft2/test.jsonl \
        --out data/ft2/paraphrase.jsonl --n 300
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

from .infer import ChatClient, InferConfig, InferError
from .paths import load_seed

STYLES = [
    "a high-school physics teacher writing an exam question",
    "a chatty student messaging a friend for help",
    "a terse lab-notebook entry",
    "an engineering textbook problem with a short story around it",
    "a university problem set, formal and precise",
    "a casual forum post asking for help",
]

SYSTEM = (
    "You rewrite physics word problems. Rules: keep every number and its unit exactly as written "
    "(do not convert units or round); do not add any new number; do not solve the problem or hint "
    "at what happens; ask for exactly the same quantities; reply with the rewritten problem only."
)

ASK_WORDS = {
    "acceleration": r"accelerat|speeding up|how quickly",
    "velocity": r"velocit|speed|how fast",
    "position": r"position|where|coordinates|displacement|how far|height|located",
    "distance": r"distance|how far|travel|cover|go\b",
    "work": r"\bwork\b",
    "min_mu_s": r"minimum|least|smallest|lowest",
    "time": r"how long|time|when|how many seconds",
    "normal": r"normal",
    "friction": r"friction",
    "tension": r"tension",
    "net": r"net force",
}


def numbers(text: str) -> set[str]:
    text = re.sub(r"(?:m/s|s|m)(?:\^|\*\*)?[²2]\b", " ", text)  # unit exponents are not numbers
    return {str(float(n)) for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text)}


def asks_ok(question: str, scene: dict[str, Any]) -> bool:
    low = question.lower()
    for q in scene.get("queries", []):
        key = q.get("force") or q["ask"]
        if not re.search(ASK_WORDS.get(key, r"."), low):
            return False
    return True


def keep(original: str, candidate: str, scene: dict[str, Any]) -> str | None:
    """None if the paraphrase is acceptable, otherwise the reason it was rejected."""
    if len(candidate) < 30 or "\n\n" in candidate.strip():
        return "shape"
    if numbers(original) != numbers(candidate):
        return "numbers"
    if not asks_ok(candidate, scene):
        return "asks"
    if re.search(r"\b(slides?|sticks?|stays? put|doesn't move|does not move)\b", candidate.lower()):
        return "leak"
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="qwen2.5-coder:7b")
    p.add_argument("--base-url", default="http://localhost:11434/v1")
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    items = [i for i in load_seed(args.source) if "scene" in i]
    rng = random.Random(args.seed)
    rng.shuffle(items)
    client = ChatClient(
        InferConfig(base_url=args.base_url, model=args.model, temperature=0.8, max_tokens=400)
    )
    kept: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    tried = 0
    for item in items:
        if len(kept) >= args.n:
            break
        tried += 1
        style = rng.choice(STYLES)
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Rewrite this problem as {style}.\n\nProblem: {item['question']}",
            },
        ]
        try:
            text = client.complete(messages).text.strip().strip('"')
        except InferError as e:
            print(f"infer error: {e}", file=sys.stderr)
            continue
        reason = keep(item["question"], text, item["scene"])
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        kept.append(
            {
                "id": f"para/{item['id']}",
                "example": item["example"],
                "style": "paraphrase",
                "source": f"llm-paraphrase of {item['id']} by {args.model} ({style})",
                "question": text,
                "scene": item["scene"],
            }
        )
        if len(kept) % 25 == 0:
            print(f"{len(kept)} kept / {tried} tried, rejected {rejected}", file=sys.stderr)
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
    print(f"kept {len(kept)} of {tried} tried; rejected {rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

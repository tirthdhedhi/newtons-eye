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
    "an exam question that starts with 'Calculate' or 'Determine'",
    "a worksheet question for grade 11, possibly with parts (a) and (b)",
    "a physics olympiad question, concise and formal",
    "a short message from a student who forgot the exact wording",
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


_PREFACE = re.compile(
    r"^(?:okay|ok|sure|certainly|here|this |i |note|rewritten|---|\*\*note|let me)", re.IGNORECASE
)


def extract_problem(raw: str) -> str:
    """The rewritten problem without chatty framing, markdown or quotes."""
    text = raw.replace("**", "").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    keepers = [p for p in paragraphs if not _PREFACE.match(p) and len(p) >= 30]
    if not keepers:
        return text
    first = keepers[0]
    return re.sub(r"^[\"'`]+|[\"'`]+$", "", first).strip()


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


# A paraphrase must not bring in physics the original did not state.
DRIFT_WORDS = ("compress", "compression", "elastic", "bounce", "rebound", "air resistance")


def drifted(original: str, candidate: str) -> bool:
    low_o, low_c = original.lower(), candidate.lower()
    for word in DRIFT_WORDS:
        if word in low_c and word not in low_o:
            # "neglect/ignore air resistance" is a statement, not new physics
            if word == "air resistance" and re.search(r"(neglect|ignor|no|without)", low_c):
                continue
            return True
    return False


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
    if drifted(original, candidate):
        return "drift"
    return None


def main(argv: list[str] | None = None) -> int:
    from .splits import split_of

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="gemma3:4b")
    p.add_argument("--base-url", default="http://localhost:11434/v1")
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=300, help="stop after this many kept paraphrases")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--split", choices=["train", "val", "test"], help="only problems in this split")
    p.add_argument("--max-tries", type=int, default=3, help="attempts per source question")
    args = p.parse_args(argv)

    items = [
        i
        for i in load_seed(args.source)
        if "scene" in i and (args.split is None or split_of(i) == args.split)
    ]
    rng = random.Random(args.seed)
    rng.shuffle(items)
    out = Path(args.out)
    done = (
        {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    )
    client = ChatClient(
        InferConfig(base_url=args.base_url, model=args.model, temperature=0.9, max_tokens=400)
    )
    kept = len(done)
    rejected: dict[str, int] = {}
    tried = 0
    with out.open("a") as fh:
        for item in items:
            if kept >= args.n:
                break
            new_id = f"para/{item['id']}"
            if new_id in done:
                continue
            for _ in range(args.max_tries):
                tried += 1
                style = rng.choice(STYLES)
                messages = [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Rewrite this problem as {style}.\n\nProblem: {item['question']}"
                        ),
                    },
                ]
                try:
                    text = extract_problem(client.complete(messages).text)
                except InferError as e:
                    print(f"infer error: {e}", file=sys.stderr)
                    continue
                reason = keep(item["question"], text, item["scene"])
                if reason:
                    rejected[reason] = rejected.get(reason, 0) + 1
                    continue
                record = {
                    "id": new_id,
                    "parent": item.get("parent", item["id"]),
                    "family": item.get("family") or item.get("example"),
                    "example": item.get("example") or item.get("family"),
                    "style": "paraphrase",
                    "source": f"synthetic + paraphrase by {args.model} ({style})",
                    "question": text,
                    "scene": item["scene"],
                    "expected": item.get("expected", {}),
                    **({"expect": item["expect"]} if "expect" in item else {}),
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                kept += 1
                break
            if kept % 50 == 0 and kept:
                print(
                    f"{kept} kept / {tried} tried, rejected {rejected}", file=sys.stderr, flush=True
                )
    print(f"kept {kept} after {tried} tries; rejected {rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

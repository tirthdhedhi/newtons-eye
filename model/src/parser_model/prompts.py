"""Prompt construction: instructions + schema + leave-one-out few-shot examples."""

from __future__ import annotations

import json
import random
from functools import lru_cache
from typing import Any

from .paths import examples_dir, load_schema, load_seed, model_dir

INSTRUCTIONS = """\
You convert a physics word problem into a JSON scene for a mechanics solver.

Rules:
- Reply with ONE JSON object and nothing else: no prose, no markdown, no code fences.
- The JSON must follow the authoring scene schema and use "version": 1.1.
- Write only quantities given in the problem. Never write computed results (normal force,
  tension, friction force, accelerations, answers); the solver computes them.
- Quantities are numbers in SI units, or strings with a unit such as "5 kg", "30 deg", "2 s".
- Add one query for every quantity the problem asks for.
- Do not invent values the problem does not give.\
"""

SEED_PATH = model_dir() / "data" / "seed.jsonl"


@lru_cache(maxsize=1)
def _schema_text() -> str:
    return json.dumps(load_schema(), separators=(",", ":"))


@lru_cache(maxsize=1)
def _few_shot_pool() -> dict[str, tuple[str, str]]:
    """example -> (textbook question, compact authoring JSON), for examples with a twin."""
    questions = {
        r["example"]: r["question"] for r in load_seed(SEED_PATH) if r["style"] == "textbook"
    }
    pool = {}
    for path in sorted(examples_dir().glob("*.authoring.json")):
        name = path.name.removesuffix(".authoring.json")
        if name in questions:
            pool[name] = (
                questions[name],
                json.dumps(json.loads(path.read_text()), separators=(",", ":")),
            )
    return pool


def pick_few_shots(exclude_example: str | None, k: int = 3) -> list[str]:
    """Deterministic leave-one-out choice: never includes ``exclude_example``."""
    names = [n for n in _few_shot_pool() if n != exclude_example]
    rng = random.Random(f"few-shot:{exclude_example}")
    return sorted(rng.sample(names, min(k, len(names))))


def build_system_prompt(
    exclude_example: str | None, k: int = 3, include_schema: bool = True
) -> str:
    parts = [INSTRUCTIONS]
    if include_schema:
        parts.append(f"JSON Schema:\n{_schema_text()}")
    shots = []
    for name in pick_few_shots(exclude_example, k):
        question, scene = _few_shot_pool()[name]
        shots.append(f"Problem: {question}\nJSON: {scene}")
    if shots:
        parts.append("Examples:\n\n" + "\n\n".join(shots))
    return "\n\n".join(parts)


def finetune_messages(question: str) -> list[dict[str, Any]]:
    """The prompt a fine-tuned model sees in training and at test time: no schema, no examples.

    Evaluate a tuned model with ``--shots 0 --no-schema-in-prompt``, which builds the same prompt.
    """
    return build_messages(question, None, k=0, include_schema=False)


def build_messages(
    question: str, exclude_example: str | None, k: int = 3, include_schema: bool = True
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": build_system_prompt(exclude_example, k, include_schema)},
        {"role": "user", "content": f"Problem: {question}\nJSON:"},
    ]

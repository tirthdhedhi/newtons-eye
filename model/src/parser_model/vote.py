"""Self-consistency: sample several scenes, keep the valid ones, return the majority answer.

A small model sometimes drops a query or writes a malformed one. Those slips are random, so they
are usually outvoted. A candidate is *valid* when it is a refusal, or a scene that passes the JSON
Schema and solves (exit 0). Candidates are grouped by what they ask and what the solver answers
(query signatures + rounded answers), so two scenes that differ only in ids or wording vote
together. The greedy output breaks ties and is the fallback when nothing is valid.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import jsonschema

from .infer import ChatClient
from .metrics import Solver, parse_scene, signatures


def _key(scene: dict[str, Any], answers: dict[str, Any]) -> str:
    sigs = signatures(scene)
    rounded = {
        qid: ([round(x, 4) for x in v] if isinstance(v, list) else round(v, 4))
        for qid, v in answers.items()
        if v is not None
    }
    return json.dumps(sorted((repr(sigs[q]), json.dumps(rounded.get(q))) for q in sigs))


def candidate_key(raw: str, schema: dict[str, Any], solver: Solver) -> str | None:
    """A grouping key for a valid candidate, ``"REFUSE"`` for a refusal, ``None`` if invalid."""
    scene, _ = parse_scene(raw)
    if scene is None:
        return None
    if set(scene) == {"unsupported"} and isinstance(scene["unsupported"], str):
        return "REFUSE"
    if not jsonschema.Draft202012Validator(schema).is_valid(scene):
        return None
    solved = solver(scene)
    if not solved.ok or solved.answers is None:
        return None
    return _key(scene, solved.answers)


def choose(
    client: ChatClient,
    messages: list[dict[str, Any]],
    *,
    k: int,
    temperature: float,
    schema: dict[str, Any],
    solver: Solver,
) -> tuple[str, dict[str, Any]]:
    """The greedy output plus ``k`` samples; returns the winning raw output and vote details."""
    base_temperature = client.config.temperature
    outputs = [client.complete(messages).raw]  # greedy first
    client.config.temperature = temperature
    try:
        for _ in range(k):
            outputs.append(client.complete(messages).raw)
    finally:
        client.config.temperature = base_temperature
    keys = [candidate_key(raw, schema, solver) for raw in outputs]
    votes = Counter(key for key in keys if key is not None)
    info: dict[str, Any] = {
        "samples": len(outputs),
        "valid": sum(votes.values()),
        "groups": sorted(votes.values(), reverse=True),
    }
    if not votes:
        return outputs[0], {**info, "chose": "greedy (nothing valid)"}
    best = max(votes.values())
    winners = {key for key, n in votes.items() if n == best}
    for raw, key in zip(outputs, keys, strict=True):  # greedy comes first, so it wins ties
        if key in winners:
            return raw, {**info, "chose": f"majority {best}/{len(outputs)}"}
    return outputs[0], info

"""Per-item and per-example metrics.

valid_json    the output (minus think blocks / a code fence) parses to a JSON object
schema_valid  it validates against the authoring JSON Schema
solver_ok     ``pnpm solve`` exits 0
grounded      every number in the scene comes from the question (see ``grounding``)
solver_match  the solver's answers equal the gold scene's, query by query, matched by a canonical
              signature rather than by query id

A signature is ``(ask, body, force, connection, until, at, from, to)``. ``connection`` and
``from``/``to`` are added to the signature so tension and work queries stay distinct. Bodies are
named by mass (SI) when the scene gives one, so ``"box"`` and ``"block"`` are the same body; a
connection is named by the masses of the bodies it joins. Quantity strings are converted to SI.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import jsonschema

from .grounding import check_grounding, parse_quantity_string
from .infer import clean_output
from .solve import SolveResult

REL_TOL = 1e-3
ABS_TOL = 1e-9
METRICS = ("valid_json", "schema_valid", "solver_ok", "grounded", "solver_match")

Signature = tuple[Any, ...]
Solver = Callable[[Any], SolveResult]


# --- signatures -------------------------------------------------------------------------------


def _si(value: Any) -> Any:
    """A number or quantity string as a rounded SI float; anything else unchanged."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        parsed = parse_quantity_string(value)
        if parsed:
            value = parsed[0]
    if isinstance(value, (int, float)):
        return float(f"{value:.6g}")
    return value


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _canon(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_canon(v) for v in value)
    return _si(value)


def _body_names(scene: dict[str, Any]) -> dict[str, Any]:
    names: dict[str, Any] = {}
    for body in scene.get("bodies") or []:
        if isinstance(body, dict) and "id" in body:
            mass = _si(body.get("mass"))
            names[body["id"]] = mass if isinstance(mass, float) else body["id"]
    return names


def _connection_names(scene: dict[str, Any], bodies: dict[str, Any]) -> dict[str, Any]:
    names: dict[str, Any] = {}
    for conn in scene.get("connections") or []:
        if isinstance(conn, dict) and "id" in conn:
            ends = sorted(str(bodies.get(conn.get(k), conn.get(k))) for k in ("a", "b"))
            names[conn["id"]] = tuple(ends)
    return names


def query_signature(query: dict[str, Any], scene: dict[str, Any] | None = None) -> Signature:
    scene = scene or {}
    bodies = _body_names(scene)
    conns = _connection_names(scene, bodies)
    body = query.get("body")
    conn = query.get("connection")
    ask = query.get("ask")
    above = query.get("above") or ("ground" if ask == "max_height" else None)
    return (
        ask,
        bodies.get(body, body),
        query.get("force"),
        conns.get(conn, conn),
        _canon(query.get("until")),
        _canon(query.get("at")),
        _si(query.get("from")),
        _si(query.get("to")),
        above,
    )


def signatures(scene: dict[str, Any]) -> dict[str, Signature]:
    """Query id -> signature, for every query in the scene."""
    return {
        q["id"]: query_signature(q, scene)
        for q in scene.get("queries") or []
        if isinstance(q, dict) and "id" in q
    }


# --- answer comparison -------------------------------------------------------------------------


def values_close(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    if isinstance(a, list) or isinstance(b, list):
        return (
            isinstance(a, list)
            and isinstance(b, list)
            and len(a) == len(b)
            and all(values_close(x, y) for x, y in zip(a, b, strict=True))
        )
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def compare_answers(
    gold_scene: dict[str, Any],
    gold_answers: dict[str, Any],
    model_scene: dict[str, Any],
    model_answers: dict[str, Any],
) -> list[str]:
    """Mismatch descriptions; empty when every gold query has a matching model answer."""
    by_sig: dict[Signature, list[Any]] = {}
    for qid, sig in signatures(model_scene).items():
        by_sig.setdefault(sig, []).append(model_answers.get(qid))
    problems = []
    for qid, sig in signatures(gold_scene).items():
        want = gold_answers.get(qid)
        candidates = by_sig.get(sig)
        if candidates is None:
            problems.append(f"missing query {sig[0]} {_describe(sig)} (gold {qid!r})")
        elif not any(values_close(got, want) for got in candidates):
            problems.append(f"{qid}: {_describe(sig)} got {candidates[0]!r}, want {want!r}")
    return problems


def _describe(sig: Signature) -> str:
    return " ".join(
        f"{k}={v}"
        for k, v in zip(
            ("ask", "body", "force", "conn", "until", "at", "from", "to", "above"),
            sig,
            strict=True,
        )
        if v is not None
    )


# --- items -------------------------------------------------------------------------------------


@dataclass
class ItemResult:
    id: str
    example: str
    style: str
    question: str
    raw_output: str = ""
    scene: dict[str, Any] | None = None
    valid_json: bool = False
    schema_valid: bool = False
    solver_ok: bool = False
    grounded: bool = False
    solver_match: bool = False
    failures: list[str] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)
    ungrounded: list[dict[str, Any]] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)
    solver: dict[str, Any] | None = None
    infer: dict[str, Any] = field(default_factory=dict)

    @property
    def failure_reason(self) -> str:
        return self.failures[0] if self.failures else ""

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["failure_reason"] = self.failure_reason
        return out


class GoldCache:
    """Solves each example's gold scene once."""

    def __init__(self, loader: Callable[[str], dict[str, Any]], solver: Solver) -> None:
        self._loader = loader
        self._solver = solver
        self._cache: dict[str, tuple[dict[str, Any], SolveResult]] = {}

    def put(self, key: str, scene: dict[str, Any]) -> None:
        """Use ``scene`` as the gold for ``key`` (synthetic items carry their own gold scene)."""
        if key not in self._cache:
            self._cache[key] = (scene, self._solver(scene))

    def get(self, example: str) -> tuple[dict[str, Any], SolveResult]:
        if example not in self._cache:
            scene = self._loader(example)
            self._cache[example] = (scene, self._solver(scene))
        return self._cache[example]


def parse_scene(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    text = clean_output(raw)
    try:
        scene = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"invalid_json: {e.msg} (line {e.lineno} col {e.colno})"
    if not isinstance(scene, dict):
        return None, f"invalid_json: top level is {type(scene).__name__}, not an object"
    return scene, None


def evaluate_item(
    item: dict[str, Any],
    raw_output: str,
    *,
    schema: dict[str, Any],
    gold: GoldCache,
    solver: Solver,
) -> ItemResult:
    result = ItemResult(
        id=item["id"],
        example=item["example"],
        style=item["style"],
        question=item["question"],
        raw_output=raw_output,
    )
    scene, error = parse_scene(raw_output)
    if scene is None:
        result.failures.append(error or "invalid_json")
        return result
    result.scene = scene
    result.valid_json = True

    refused = set(scene) == {"unsupported"}
    if item.get("expect") == "unsupported":
        # Out of scope: the only correct answer is a refusal; every check passes with it.
        if refused:
            result.schema_valid = result.solver_ok = result.grounded = result.solver_match = True
        else:
            result.failures.append("should_refuse: produced a scene for an unsupported question")
        return result
    if "unsupported" in scene:
        result.failures.append(f"refused_in_scope: {scene.get('unsupported')}")
        return result

    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(scene), key=lambda e: list(e.path)
    )
    result.schema_valid = not errors
    result.schema_errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}" for e in errors[:5]
    ]
    if errors:
        result.failures.append(f"schema: {result.schema_errors[0]}")

    solved = solver(scene)
    result.solver = solved.to_dict()
    result.solver_ok = solved.ok
    if not solved.ok:
        detail = solved.issues[:1] or solved.errors[:1] or [solved.stderr[:200]]
        result.failures.append(f"solver_exit_{solved.exit_code}: {detail[0]}")

    grounding = check_grounding(item["question"], scene)
    result.grounded = grounding.grounded
    result.ungrounded = grounding.ungrounded
    if not grounding.grounded:
        shown = ", ".join(f"{u['path']}={u['value']:g}" for u in grounding.ungrounded[:5])
        result.failures.append(f"ungrounded: {shown}")

    if solved.ok and solved.answers is not None:
        gold_key = item["example"]
        if "scene" in item:  # generated items carry their own gold scene
            gold_key = item["id"]
            gold.put(gold_key, item["scene"])
        gold_scene, gold_solved = gold.get(gold_key)
        if not gold_solved.ok or gold_solved.answers is None:
            result.failures.append(f"gold_unsolvable: exit {gold_solved.exit_code}")
        else:
            result.mismatches = compare_answers(
                gold_scene, gold_solved.answers, scene, solved.answers
            )
            result.solver_match = not result.mismatches
            if result.mismatches:
                result.failures.append(f"mismatch: {result.mismatches[0]}")
    return result


# --- aggregation -------------------------------------------------------------------------------


def summarize(results: list[ItemResult]) -> dict[str, dict[str, Any]]:
    """Per-example and overall counts and rates. The key ``"overall"`` covers every item."""
    groups: dict[str, list[ItemResult]] = {}
    for r in results:
        groups.setdefault(r.example, []).append(r)
    groups["overall"] = list(results)
    summary = {}
    for name, items in groups.items():
        n = len(items)
        counts = {m: sum(getattr(r, m) for r in items) for m in METRICS}
        summary[name] = {
            "n": n,
            **{f"{m}_count": c for m, c in counts.items()},
            **{m: (c / n if n else 0.0) for m, c in counts.items()},
        }
    return summary

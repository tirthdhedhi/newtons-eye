"""Question in, answer out: the app-side pipeline around the parser model.

    question -> model -> check -> solver -> explanation

The model only translates. Everything that makes the product reliable is here, in plain code:

* a refusal from the model (``{"unsupported": reason}``) becomes status ``unsupported`` (or
  ``not_physics``);
* an output that is not valid JSON, does not match the schema, does not solve, or declares more
  things than it queries is retried (greedy first, then sampled);
* a scene whose ``find:`` line lists something the solver cannot compute (``separation``,
  ``equilibrium``) is treated as a refusal, whatever scene came with it;
* a scene that solves is explained in words, with the assumptions the solver made (default mass,
  default shape) listed so the user can see them.

    python -m parser_model.pipeline "A car at 20 m/s speeds up at 3 m/s^2 for 8 s. Final velocity?"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

import jsonschema

from .asks import ask_label, asks_complete, unknown_asks
from .infer import ChatClient, InferConfig, InferError
from .metrics import parse_scene
from .paths import load_schema
from .prompts import finetune_messages
from .solve import SolveResult, solve_scene

UNITS = {
    "acceleration": "m/s^2",
    "velocity": "m/s",
    "position": "m",
    "relative_velocity": "m/s",
    "distance": "m",
    "work": "J",
    "max_height": "m",
    "range": "m",
    "time": "s",
    "force": "N",
    "min_mu_s": "",
}
NOT_PHYSICS = ("not a mechanics problem", "not physics", "not a physics")


@dataclass
class Answer:
    id: str
    label: str
    when: str
    value: Any
    unit: str
    text: str


@dataclass
class PipelineResult:
    status: str  # answered | unsupported | not_physics | failed
    question: str
    reason: str | None = None
    scene: dict[str, Any] | None = None
    answers: list[Answer] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    explanation: str = ""
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- explanation --------------------------------------------------------------------------------


def _fmt(x: float) -> str:
    if x == 0:
        return "0"
    return f"{x:.4g}"


def _when(q: dict[str, Any]) -> str:
    at = q.get("at")
    if isinstance(at, dict):
        event = at.get("event", "the event")
        return "at landing" if event == "land" else f"at the instant of {event}"
    if isinstance(at, (int, float)):
        return f"at t = {_fmt(float(at))} s"
    if q.get("ask") in ("acceleration", "velocity", "position", "force") and q.get("until") is None:
        return "at t = 0"
    return ""


def describe(q: dict[str, Any], value: Any) -> tuple[str, str]:
    """(unit, text) for one query's answer."""
    ask = q.get("ask", "")
    unit = UNITS.get(ask, "")
    label = ask_label(q).capitalize()
    when = _when(q)
    suffix = f" {when}" if when and "impact" not in label.lower() else ""
    if value is None:
        return unit, f"{label}{suffix}: the solver could not compute it"
    if isinstance(value, list):
        magnitude = math.hypot(*value)
        comps = ", ".join(_fmt(x) for x in value)
        return unit, f"{label}{suffix}: {_fmt(magnitude)} {unit} (components [{comps}] {unit})"
    return unit, f"{label}{suffix}: {_fmt(value)}{(' ' + unit) if unit else ''}"


def explain(scene: dict[str, Any], solved: SolveResult) -> tuple[list[Answer], list[str], str]:
    answers: list[Answer] = []
    for q in scene.get("queries", []):
        value = (solved.answers or {}).get(q["id"])
        unit, text = describe(q, value)
        answers.append(Answer(q["id"], ask_label(q), _when(q), value, unit, text))
    assumptions = [w for w in solved.warnings if "no duration" not in w]
    lines = [a.text for a in answers]
    if assumptions:
        lines += ["", "Assumptions made:"] + [f"- {a}" for a in assumptions]
    return answers, assumptions, "\n".join(lines)


# --- checking one model output ------------------------------------------------------------------


@dataclass
class Checked:
    kind: str  # refusal | scene | invalid
    scene: dict[str, Any] | None = None
    solved: SolveResult | None = None
    note: str = ""


def check_output(raw: str, schema: dict[str, Any], solver=solve_scene) -> Checked:
    scene, error = parse_scene(raw)
    if scene is None:
        return Checked("invalid", note=error or "not JSON")
    if set(scene) == {"unsupported"} and isinstance(scene["unsupported"], str):
        return Checked("refusal", scene, note=scene["unsupported"])
    unknown = unknown_asks(scene)
    if unknown:
        return Checked("refusal", scene, note="asks for " + ", ".join(unknown))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(scene))
    if errors:
        return Checked("invalid", scene, note="schema: " + errors[0].message[:120])
    if not asks_complete(scene):
        return Checked("invalid", scene, note="fewer queries than the find: line declares")
    solved = solver(scene)
    if not solved.ok:
        detail = (solved.issues or solved.errors or [solved.stderr[:120]])[0]
        return Checked("invalid", scene, solved, note=f"solver: {detail}")
    return Checked("scene", scene, solved)


# --- the pipeline -------------------------------------------------------------------------------


def answer_question(
    client: ChatClient,
    question: str,
    *,
    retries: int = 4,
    retry_temperature: float = 0.7,
    solver=solve_scene,
    schema: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run one question through model, checks and solver. Never raises on model failures."""
    schema = schema or load_schema()
    result = PipelineResult(status="failed", question=question)
    messages = finetune_messages(question)
    base_temperature = client.config.temperature
    try:
        for attempt in range(retries + 1):
            client.config.temperature = base_temperature if attempt == 0 else retry_temperature
            try:
                raw = client.complete(messages).raw
            except InferError as e:
                result.attempts.append(
                    {"attempt": attempt, "status": "model error", "note": str(e)[:200]}
                )
                continue
            checked = check_output(raw, schema, solver)
            result.attempts.append(
                {"attempt": attempt, "status": checked.kind, "note": checked.note, "raw": raw}
            )
            if checked.kind == "refusal":
                reason = checked.note
                result.status = (
                    "not_physics"
                    if any(n in reason.lower() for n in NOT_PHYSICS)
                    else "unsupported"
                )
                result.reason = reason
                result.explanation = (
                    "This is not a mechanics problem."
                    if result.status == "not_physics"
                    else f"I can't solve this one yet ({reason}): it needs something the solver "
                    "does not support."
                )
                return result
            if checked.kind == "scene" and checked.scene and checked.solved:
                result.status = "answered"
                result.scene = checked.scene
                result.answers, result.assumptions, result.explanation = explain(
                    checked.scene, checked.solved
                )
                return result
    finally:
        client.config.temperature = base_temperature
    result.reason = result.attempts[-1]["note"] if result.attempts else "no output"
    result.explanation = "I could not turn this into a valid problem. Try rephrasing it."
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("question")
    p.add_argument("--model", default="newtons-eye-3b-v5")
    p.add_argument("--base-url", default="http://localhost:11434/v1")
    p.add_argument("--retries", type=int, default=4)
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = p.parse_args(argv)
    client = ChatClient(
        InferConfig(base_url=args.base_url, model=args.model, temperature=0.0, max_tokens=1500)
    )
    result = answer_question(client, args.question, retries=args.retries)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"[{result.status}]")
        print(result.explanation)
    return 0 if result.status in ("answered", "unsupported", "not_physics") else 1


if __name__ == "__main__":
    sys.exit(main())
